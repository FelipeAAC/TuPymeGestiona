from django.core.paginator import EmptyPage, Paginator

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from organizations.authorization import has_permission
from organizations.models import CompanyMembership, RoleAssignment
from sales.models import Sale

from .models import ElectronicTaxDocument, ElectronicTaxEvent, FolioAuthorization
from .serializers import (
    ElectronicTaxDocumentCreateSerializer,
    ElectronicTaxDocumentSerializer,
    ElectronicTaxListQuerySerializer,
    ElectronicTaxMutationSerializer,
    ElectronicTaxNoteCreateSerializer,
)
from .sii_adapter import import_caf
from .services import (
    DTEAlreadyExistsError,
    DTECommercialAdjustmentRequiredError,
    DTEError,
    DTEIdempotencyConflictError,
    DTEInvalidStateError,
    DTEProviderNotConfiguredError,
    DTERefundRequiredError,
    DTEValidationError,
    DTEVersionConflictError,
    create_base_document,
    create_credit_note,
    create_debit_note,
    discard_document,
    issue_document,
    record_event,
    record_version_conflict,
    refresh_document_status,
    validate_document,
)


VIEW_PERMISSION = "electronic_tax_document.view"
CREATE_PERMISSION = "electronic_tax_document.create"
VALIDATE_PERMISSION = "electronic_tax_document.validate"
ISSUE_PERMISSION = "electronic_tax_document.issue"
ADJUST_PERMISSION = "electronic_tax_document.adjust"
FOLIO_PERMISSION = "electronic_tax_folio.manage"


ERROR_STATUS = {
    DTEValidationError: status.HTTP_400_BAD_REQUEST,
    DTEAlreadyExistsError: status.HTTP_409_CONFLICT,
    DTEInvalidStateError: status.HTTP_409_CONFLICT,
    DTEVersionConflictError: status.HTTP_409_CONFLICT,
    DTEIdempotencyConflictError: status.HTTP_409_CONFLICT,
    DTERefundRequiredError: status.HTTP_409_CONFLICT,
    DTEProviderNotConfiguredError: status.HTTP_409_CONFLICT,
    DTECommercialAdjustmentRequiredError: status.HTTP_409_CONFLICT,
}


def _error_response(error):
    http_status = ERROR_STATUS.get(type(error), status.HTTP_409_CONFLICT)
    return Response({"code": error.code, "detail": error.detail}, status=http_status)


def _parse_company_id(raw):
    if isinstance(raw, bool):
        return None
    if isinstance(raw, int):
        return raw if raw > 0 else None
    if isinstance(raw, str) and raw.strip().isdecimal():
        value = int(raw.strip())
        return value if value > 0 else None
    return None


def _resolve_membership(*, request, source):
    raw_company = source.get("company")
    if raw_company in (None, ""):
        return None, Response(
            {"code": "DTE_VALIDATION_ERROR", "detail": "company es obligatorio."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    company_id = _parse_company_id(raw_company)
    if company_id is None:
        return None, Response(
            {"code": "DTE_VALIDATION_ERROR", "detail": "company debe ser un entero valido."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    membership = (
        CompanyMembership.objects.filter(
            user=request.user,
            company_id=company_id,
            status=CompanyMembership.Status.ACTIVE,
        )
        .select_related("company")
        .first()
    )
    if membership is None:
        return None, Response(
            {"code": "DTE_PERMISSION_DENIED", "detail": "No tienes acceso a esta empresa."},
            status=status.HTTP_403_FORBIDDEN,
        )
    return membership, None


def _idempotency_key(request):
    key = (request.headers.get("Idempotency-Key") or "").strip()
    if not key:
        return None, Response(
            {"code": "DTE_VALIDATION_ERROR", "detail": "Idempotency-Key es obligatorio."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if len(key) > 100:
        return None, Response(
            {"code": "DTE_VALIDATION_ERROR", "detail": "Idempotency-Key no puede superar 100 caracteres."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    return key, None


def _permission_assignments(*, user, company, permission_code):
    return RoleAssignment.objects.filter(
        membership__user=user,
        membership__company=company,
        membership__status=CompanyMembership.Status.ACTIVE,
        role__company=company,
        role__status="ACTIVE",
        role__permission_links__permission__code=permission_code,
    ).distinct()


def _authorized_documents(*, user, company, permission_code=VIEW_PERMISSION):
    assignments = _permission_assignments(user=user, company=company, permission_code=permission_code)
    queryset = ElectronicTaxDocument.objects.filter(company=company)
    if not assignments.exists():
        return queryset.none()
    if not assignments.filter(branch__isnull=True).exists():
        branch_ids = assignments.values_list("branch_id", flat=True)
        queryset = queryset.filter(branch_id__in=branch_ids)
    return queryset.select_related("company", "branch", "sale", "created_by").prefetch_related(
        "lines", "references", "events"
    )


def _get_document_for_action(*, request, company, document_id, permission_code):
    document = (
        ElectronicTaxDocument.objects.filter(company=company, pk=document_id)
        .select_related("company", "branch", "sale")
        .first()
    )
    if document is None:
        foreign_document = (
            ElectronicTaxDocument.objects.filter(pk=document_id)
            .select_related("company", "branch")
            .first()
        )
        if foreign_document is not None:
            record_event(
                document=foreign_document,
                event_type=ElectronicTaxEvent.EventType.CROSS_TENANT_BLOCKED,
                actor=request.user,
                code="DTE_NOT_FOUND",
                metadata={"requested_company_id": company.id},
            )
        return None, Response(
            {"code": "DTE_NOT_FOUND", "detail": "El DTE no existe en el alcance autorizado."},
            status=status.HTTP_404_NOT_FOUND,
        )
    if not has_permission(
        user=request.user,
        company=company,
        permission_code=permission_code,
        branch=document.branch,
    ):
        record_event(
            document=document,
            event_type=ElectronicTaxEvent.EventType.ACCESS_DENIED,
            actor=request.user,
            code="DTE_PERMISSION_DENIED",
            metadata={"permission": permission_code},
        )
        return None, Response(
            {"code": "DTE_PERMISSION_DENIED", "detail": "No tienes el permiso requerido para este DTE."},
            status=status.HTTP_403_FORBIDDEN,
        )
    return document, None


def _handle_service_error(*, error, document=None, actor=None, expected_version=None):
    if isinstance(error, DTEVersionConflictError) and document is not None and actor is not None:
        record_version_conflict(
            document=document,
            actor=actor,
            expected_version=expected_version,
        )
    return _error_response(error)


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def document_list_create_view(request):
    if request.method == "POST":
        membership, error = _resolve_membership(request=request, source=request.data)
        if error:
            return error
        key, error = _idempotency_key(request)
        if error:
            return error
        serializer = ElectronicTaxDocumentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        company = membership.company
        sale = (
            Sale.objects.filter(company=company, pk=serializer.validated_data["sale_id"])
            .select_related("branch", "order__customer")
            .first()
        )
        if sale is None:
            return Response(
                {"code": "DTE_NOT_FOUND", "detail": "La venta no existe en la empresa activa."},
                status=status.HTTP_404_NOT_FOUND,
            )
        if not has_permission(
            user=request.user,
            company=company,
            permission_code=CREATE_PERMISSION,
            branch=sale.branch,
        ):
            return Response(
                {"code": "DTE_PERMISSION_DENIED", "detail": "No tienes permiso para crear DTE en esta sucursal."},
                status=status.HTTP_403_FORBIDDEN,
            )
        try:
            document, created = create_base_document(
                company=company,
                sale=sale,
                type_code=serializer.validated_data["type_code"],
                idempotency_key=key,
                created_by=request.user,
            )
        except DTEError as service_error:
            return _error_response(service_error)
        document = _authorized_documents(user=request.user, company=company).get(pk=document.pk)
        return Response(
            {"document": ElectronicTaxDocumentSerializer(document).data, "idempotent_replay": not created},
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    membership, error = _resolve_membership(request=request, source=request.query_params)
    if error:
        return error
    company = membership.company
    assignments = _permission_assignments(user=request.user, company=company, permission_code=VIEW_PERMISSION)
    if not assignments.exists():
        return Response(
            {"code": "DTE_PERMISSION_DENIED", "detail": "No tienes permiso para consultar DTE."},
            status=status.HTTP_403_FORBIDDEN,
        )
    query_serializer = ElectronicTaxListQuerySerializer(data=request.query_params)
    query_serializer.is_valid(raise_exception=True)
    query = query_serializer.validated_data
    documents = _authorized_documents(user=request.user, company=company)
    for field in ("branch", "type_code", "state", "folio"):
        if field in query:
            documents = documents.filter(**{field: query[field]})
    if query.get("receiver_rut"):
        documents = documents.filter(receiver_rut__iexact=query["receiver_rut"].strip())
    if query.get("issue_date_from"):
        documents = documents.filter(issue_date__gte=query["issue_date_from"])
    if query.get("issue_date_to"):
        documents = documents.filter(issue_date__lte=query["issue_date_to"])
    paginator = Paginator(documents.order_by("-created_at", "-id"), query["page_size"])
    try:
        page = paginator.page(query["page"])
    except EmptyPage:
        return Response(
            {"code": "DTE_VALIDATION_ERROR", "detail": "La pagina solicitada no existe."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    return Response(
        {
            "documents": ElectronicTaxDocumentSerializer(page.object_list, many=True).data,
            "pagination": {
                "count": paginator.count,
                "page": page.number,
                "page_size": query["page_size"],
                "total_pages": paginator.num_pages,
            },
        }
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def document_detail_view(request, document_id):
    membership, error = _resolve_membership(request=request, source=request.query_params)
    if error:
        return error
    document, error = _get_document_for_action(
        request=request,
        company=membership.company,
        document_id=document_id,
        permission_code=VIEW_PERMISSION,
    )
    if error:
        return error
    document = _authorized_documents(
        user=request.user,
        company=membership.company,
        permission_code=VIEW_PERMISSION,
    ).get(pk=document.pk)
    return Response({"document": ElectronicTaxDocumentSerializer(document).data})


def _mutation_context(request, document_id, permission_code):
    membership, error = _resolve_membership(request=request, source=request.data)
    if error:
        return None, None, None, error
    key, error = _idempotency_key(request)
    if error:
        return None, None, None, error
    document, error = _get_document_for_action(
        request=request,
        company=membership.company,
        document_id=document_id,
        permission_code=permission_code,
    )
    return membership, key, document, error


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def document_validate_view(request, document_id):
    membership, key, document, error = _mutation_context(request, document_id, VALIDATE_PERMISSION)
    if error:
        return error
    serializer = ElectronicTaxMutationSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    expected_version = serializer.validated_data["version"]
    try:
        document, changed = validate_document(
            document=document,
            expected_version=expected_version,
            idempotency_key=key,
            actor=request.user,
        )
    except DTEError as service_error:
        return _handle_service_error(
            error=service_error,
            document=document,
            actor=request.user,
            expected_version=expected_version,
        )
    document = _authorized_documents(user=request.user, company=membership.company).get(pk=document.pk)
    return Response({"document": ElectronicTaxDocumentSerializer(document).data, "idempotent_replay": not changed})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def document_discard_view(request, document_id):
    membership, key, document, error = _mutation_context(request, document_id, CREATE_PERMISSION)
    if error:
        return error
    serializer = ElectronicTaxMutationSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    expected_version = serializer.validated_data["version"]
    try:
        document, changed = discard_document(
            document=document,
            expected_version=expected_version,
            idempotency_key=key,
            actor=request.user,
        )
    except DTEError as service_error:
        return _handle_service_error(
            error=service_error,
            document=document,
            actor=request.user,
            expected_version=expected_version,
        )
    document = ElectronicTaxDocument.objects.prefetch_related("lines", "references", "events").get(pk=document.pk)
    return Response({"document": ElectronicTaxDocumentSerializer(document).data, "idempotent_replay": not changed})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def document_credit_note_view(request, document_id):
    membership, key, document, error = _mutation_context(request, document_id, ADJUST_PERMISSION)
    if error:
        return error
    serializer = ElectronicTaxNoteCreateSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    expected_version = serializer.validated_data["version"]
    try:
        note, created = create_credit_note(
            source_document=document,
            reason=serializer.validated_data["reason"],
            description=serializer.validated_data["description"],
            correction=serializer.validated_data.get("correction", {}),
            expected_version=expected_version,
            idempotency_key=key,
            actor=request.user,
        )
    except DTEError as service_error:
        return _handle_service_error(
            error=service_error,
            document=document,
            actor=request.user,
            expected_version=expected_version,
        )
    note = ElectronicTaxDocument.objects.prefetch_related("lines", "references", "events").get(pk=note.pk)
    return Response(
        {"document": ElectronicTaxDocumentSerializer(note).data, "idempotent_replay": not created},
        status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def document_debit_note_view(request, document_id):
    membership, key, document, error = _mutation_context(request, document_id, ADJUST_PERMISSION)
    if error:
        return error
    serializer = ElectronicTaxNoteCreateSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    expected_version = serializer.validated_data["version"]
    try:
        note, created = create_debit_note(
            source_document=document,
            reason=serializer.validated_data["reason"],
            description=serializer.validated_data["description"],
            expected_version=expected_version,
            idempotency_key=key,
            actor=request.user,
        )
    except DTEError as service_error:
        return _handle_service_error(
            error=service_error,
            document=document,
            actor=request.user,
            expected_version=expected_version,
        )
    note = ElectronicTaxDocument.objects.prefetch_related("lines", "references", "events").get(pk=note.pk)
    return Response(
        {"document": ElectronicTaxDocumentSerializer(note).data, "idempotent_replay": not created},
        status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def document_issue_view(request, document_id):
    membership, key, document, error = _mutation_context(request, document_id, ISSUE_PERMISSION)
    if error:
        return error
    serializer = ElectronicTaxMutationSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    expected_version = serializer.validated_data["version"]
    try:
        issued, changed = issue_document(
            document=document,
            expected_version=expected_version,
            idempotency_key=key,
            actor=request.user,
        )
    except DTEError as service_error:
        return _handle_service_error(
            error=service_error,
            document=document,
            actor=request.user,
            expected_version=expected_version,
        )
    return Response({"document": ElectronicTaxDocumentSerializer(issued).data, "idempotent_replay": not changed})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def document_refresh_status_view(request, document_id):
    membership, key, document, error = _mutation_context(request, document_id, ISSUE_PERMISSION)
    if error:
        return error
    serializer = ElectronicTaxMutationSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    expected_version = serializer.validated_data["version"]
    try:
        refreshed, changed = refresh_document_status(
            document=document,
            expected_version=expected_version,
            idempotency_key=key,
            actor=request.user,
        )
    except DTEError as service_error:
        return _handle_service_error(
            error=service_error,
            document=document,
            actor=request.user,
            expected_version=expected_version,
        )
    return Response({"document": ElectronicTaxDocumentSerializer(refreshed).data, "idempotent_replay": not changed})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def folio_summary_view(request):
    membership, error = _resolve_membership(request=request, source=request.query_params)
    if error:
        return error
    company = membership.company
    if not (
        has_permission(user=request.user, company=company, permission_code=VIEW_PERMISSION)
        or has_permission(user=request.user, company=company, permission_code=FOLIO_PERMISSION)
    ):
        return Response(
            {"code": "DTE_PERMISSION_DENIED", "detail": "No tienes permiso para consultar folios."},
            status=status.HTTP_403_FORBIDDEN,
        )
    authorizations = FolioAuthorization.objects.filter(company=company).order_by("type_code", "start_folio")
    return Response(
        {
            "authorizations": [
                {
                    "type_code": item.type_code,
                    "status": item.status,
                    "start_folio": item.start_folio,
                    "end_folio": item.end_folio,
                    "next_folio": item.next_folio,
                    "available": max(0, item.end_folio - item.next_folio + 1)
                    if item.status == FolioAuthorization.Status.ACTIVE
                    else 0,
                }
                for item in authorizations
            ]
        }
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def folio_import_view(request):
    membership, error = _resolve_membership(request=request, source=request.data)
    if error:
        return error
    key, error = _idempotency_key(request)
    if error:
        return error
    if not has_permission(
        user=request.user,
        company=membership.company,
        permission_code=FOLIO_PERMISSION,
    ):
        return Response(
            {"code": "DTE_PERMISSION_DENIED", "detail": "No tienes permiso para administrar folios."},
            status=status.HTTP_403_FORBIDDEN,
        )
    uploaded = request.FILES.get("caf_file")
    if uploaded is None:
        return Response(
            {"code": "DTE_VALIDATION_ERROR", "detail": "caf_file es obligatorio (multipart/form-data)."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    try:
        authorization, created = import_caf(
            company=membership.company,
            caf_bytes=uploaded.read(),
            idempotency_key=key,
            actor=request.user,
            source_label=uploaded.name,
        )
    except DTEError as service_error:
        return _handle_service_error(error=service_error, document=None, actor=request.user)
    return Response(
        {
            "authorization": {
                "id": authorization.id,
                "type_code": authorization.type_code,
                "status": authorization.status,
                "start_folio": authorization.start_folio,
                "end_folio": authorization.end_folio,
                "next_folio": authorization.next_folio,
                "caf_hash": authorization.caf_hash,
            },
            "idempotent_replay": not created,
        },
        status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
    )
