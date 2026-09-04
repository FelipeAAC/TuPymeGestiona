from django.db import transaction
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from organizations.models import (
    Branch,
    Company,
    CompanyMembership,
    CompanyRole,
    CompanyRolePermission,
    Permission,
    RoleAssignment,
    normalize_role_name,
)

from administration.models import AdministrationEvent, OrderStatusConfiguration, PaymentMethod
from administration.serializers import (
    AdministrationEventSerializer,
    BranchAdminSerializer,
    CompanyAdminSerializer,
    CompanySettingsSerializer,
    MembershipUserSerializer,
    OrderStatusConfigurationSerializer,
    PaymentMethodSerializer,
    PermissionAdminSerializer,
    RoleAdminSerializer,
    RoleWriteSerializer,
    UserCreateSerializer,
    UserUpdateSerializer,
)
from administration.services import (
    ADMIN_PERMISSION_CODE,
    create_company_for_user,
    ensure_company_configuration,
    get_managed_company,
    log_admin_event,
    membership_has_admin_access,
    replace_membership_access,
    user_can_create_company,
)


def _parse_company_id(raw):
    if isinstance(raw, bool):
        return None
    try:
        value = int(str(raw).strip())
    except (TypeError, ValueError):
        return None
    return value if value > 0 else None


def _company_from_request(request, *, source="query"):
    raw = request.query_params.get("company") if source == "query" else request.data.get("company")
    company_id = _parse_company_id(raw)
    if company_id is None:
        return None, Response(
            {"detail": "El identificador de empresa es obligatorio y debe ser valido."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    company = get_managed_company(user=request.user, company_id=company_id)
    if company is None:
        return None, Response(
            {"detail": "Empresa no encontrada o sin permiso de administracion."},
            status=status.HTTP_404_NOT_FOUND,
        )
    return company, None


def _serialize_overview(company):
    ensure_company_configuration(company)
    memberships = (
        company.memberships.select_related("user")
        .prefetch_related("branch_memberships", "role_assignments__role")
        .order_by("user__first_name", "user__last_name", "user__username")
    )
    roles = company.roles.prefetch_related("permission_links__permission").all()
    return {
        "company": CompanyAdminSerializer(company).data,
        "branches": BranchAdminSerializer(company.branches.all(), many=True).data,
        "users": MembershipUserSerializer(memberships, many=True).data,
        "roles": RoleAdminSerializer(roles, many=True).data,
        "permissions": PermissionAdminSerializer(Permission.objects.all(), many=True).data,
        "payment_methods": PaymentMethodSerializer(company.payment_methods.all(), many=True).data,
        "order_statuses": OrderStatusConfigurationSerializer(
            company.order_status_configurations.all(), many=True
        ).data,
        "settings": CompanySettingsSerializer(company.general_settings).data,
        "events": AdministrationEventSerializer(
            company.administration_events.select_related("actor")[:20], many=True
        ).data,
    }


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def overview_view(request):
    company, error = _company_from_request(request)
    if error:
        return error
    return Response(_serialize_overview(company))


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def company_create_view(request):
    if not user_can_create_company(user=request.user):
        return Response({"detail": "No tienes permiso para crear empresas."}, status=status.HTTP_403_FORBIDDEN)
    serializer = CompanyAdminSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    company = create_company_for_user(user=request.user, company_data=serializer.validated_data)
    return Response({"company": CompanyAdminSerializer(company).data}, status=status.HTTP_201_CREATED)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def self_service_company_create_view(request):
    serializer = CompanyAdminSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    company = create_company_for_user(
        user=request.user,
        company_data=serializer.validated_data,
    )
    Branch.objects.create(
        company=company,
        code="CASA",
        name="Casa Matriz",
        address=company.address,
        commune=company.commune,
        city=company.city,
        phone=company.phone,
        is_active=True,
    )
    return Response(
        {"company": CompanyAdminSerializer(company).data},
        status=status.HTTP_201_CREATED,
    )


@api_view(["PATCH"])
@permission_classes([IsAuthenticated])
def company_detail_view(request, company_id):
    company = get_managed_company(user=request.user, company_id=company_id)
    if company is None:
        return Response({"detail": "Empresa no encontrada."}, status=status.HTTP_404_NOT_FOUND)
    serializer = CompanyAdminSerializer(company, data=request.data, partial=True)
    serializer.is_valid(raise_exception=True)
    company = serializer.save()
    log_admin_event(
        company=company,
        actor=request.user,
        event_type="COMPANY_UPDATED",
        resource_type="company",
        resource_id=company.id,
    )
    return Response({"company": CompanyAdminSerializer(company).data})


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def user_list_create_view(request):
    company, error = _company_from_request(request, source="query" if request.method == "GET" else "data")
    if error:
        return error
    if request.method == "GET":
        users = company.memberships.select_related("user").prefetch_related(
            "branch_memberships", "role_assignments__role"
        )
        return Response({"users": MembershipUserSerializer(users, many=True).data})
    serializer = UserCreateSerializer(data=request.data, context={"company": company})
    serializer.is_valid(raise_exception=True)
    membership = serializer.save()
    log_admin_event(
        company=company,
        actor=request.user,
        event_type="USER_ADDED",
        resource_type="membership",
        resource_id=membership.id,
        metadata={"email": membership.user.email, "identity_created": bool(getattr(membership, "_created_identity", False))},
    )
    return Response({"user": MembershipUserSerializer(membership).data}, status=status.HTTP_201_CREATED)


@api_view(["PATCH"])
@permission_classes([IsAuthenticated])
def user_detail_view(request, membership_id):
    company, error = _company_from_request(request, source="data")
    if error:
        return error
    membership = company.memberships.select_related("user").filter(pk=membership_id).first()
    if membership is None:
        return Response({"detail": "Usuario no encontrado en esta empresa."}, status=status.HTTP_404_NOT_FOUND)
    serializer = UserUpdateSerializer(data=request.data, partial=True, context={"company": company})
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    if membership.user_id == request.user.id and data.get("status") in {
        CompanyMembership.Status.SUSPENDED,
        CompanyMembership.Status.LEFT,
    }:
        return Response({"detail": "No puedes suspender o desvincular tu propia membresia administrativa."}, status=status.HTTP_409_CONFLICT)

    branch_ids = data.get(
        "branch_ids",
        list(membership.branch_memberships.values_list("branch_id", flat=True)),
    )
    role_ids = data.get(
        "role_ids",
        list(membership.role_assignments.values_list("role_id", flat=True).distinct()),
    )
    desired_status = data.get("status", membership.status)
    if membership.user_id == request.user.id:
        keeps_admin_role = company.roles.filter(
            id__in=role_ids,
            status=CompanyRole.Status.ACTIVE,
            permission_links__permission__code=ADMIN_PERMISSION_CODE,
        ).exists()
        if desired_status != CompanyMembership.Status.ACTIVE or not keeps_admin_role:
            return Response(
                {"detail": "No puedes eliminar tu ultimo acceso de administracion."},
                status=status.HTTP_409_CONFLICT,
            )

    with transaction.atomic():
        user = membership.user
        if "first_name" in data:
            user.first_name = data["first_name"].strip()
        if "last_name" in data:
            user.last_name = data["last_name"].strip()
        user.save(update_fields=["first_name", "last_name"])
        if "status" in data:
            membership.status = data["status"]
            membership.save(update_fields=["status", "updated_at"])
        replace_membership_access(membership=membership, branch_ids=branch_ids, role_ids=role_ids)
        log_admin_event(
            company=company,
            actor=request.user,
            event_type="USER_UPDATED",
            resource_type="membership",
            resource_id=membership.id,
        )
    membership.refresh_from_db()
    return Response({"user": MembershipUserSerializer(membership).data})


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def role_list_create_view(request):
    company, error = _company_from_request(request, source="query" if request.method == "GET" else "data")
    if error:
        return error
    if request.method == "GET":
        return Response({"roles": RoleAdminSerializer(company.roles.all(), many=True).data})
    serializer = RoleWriteSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    if company.roles.filter(name_normalized=normalize_role_name(data["name"])).exists():
        return Response({"name": ["Ya existe un rol con ese nombre."]}, status=status.HTTP_400_BAD_REQUEST)
    with transaction.atomic():
        role = CompanyRole.objects.create(company=company, name=data["name"], status=data["status"])
        permissions = Permission.objects.filter(code__in=data["permission_codes"])
        CompanyRolePermission.objects.bulk_create(
            [CompanyRolePermission(role=role, permission=permission) for permission in permissions]
        )
        log_admin_event(
            company=company,
            actor=request.user,
            event_type="ROLE_CREATED",
            resource_type="role",
            resource_id=role.id,
            metadata={"name": role.name},
        )
    return Response({"role": RoleAdminSerializer(role).data}, status=status.HTTP_201_CREATED)


@api_view(["PATCH"])
@permission_classes([IsAuthenticated])
def role_detail_view(request, role_id):
    company, error = _company_from_request(request, source="data")
    if error:
        return error
    role = company.roles.prefetch_related("permission_links__permission").filter(pk=role_id).first()
    if role is None:
        return Response({"detail": "Rol no encontrado."}, status=status.HTTP_404_NOT_FOUND)
    serializer = RoleWriteSerializer(data={
        "name": request.data.get("name", role.name),
        "status": request.data.get("status", role.status),
        "permission_codes": request.data.get(
            "permission_codes",
            list(role.permission_links.values_list("permission__code", flat=True)),
        ),
    })
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    if company.roles.exclude(pk=role.id).filter(
        name_normalized=normalize_role_name(data["name"])
    ).exists():
        return Response(
            {"name": ["Ya existe un rol con ese nombre."]},
            status=status.HTTP_400_BAD_REQUEST,
        )
    permissions = list(Permission.objects.filter(code__in=data["permission_codes"]))
    has_company_only = any(p.scope_behavior == Permission.ScopeBehavior.COMPANY_ONLY for p in permissions)
    if has_company_only and role.assignments.filter(branch__isnull=False).exists():
        return Response(
            {"detail": "Este rol tiene asignaciones por sucursal. Ajusta los usuarios antes de agregar permisos de empresa."},
            status=status.HTTP_409_CONFLICT,
        )
    current_membership = company.memberships.filter(user=request.user, status=CompanyMembership.Status.ACTIVE).first()
    removing_admin = ADMIN_PERMISSION_CODE not in data["permission_codes"] or data["status"] != CompanyRole.Status.ACTIVE
    if current_membership and removing_admin:
        current_admin_roles = set(
            current_membership.role_assignments.filter(
                role__status=CompanyRole.Status.ACTIVE,
                role__permission_links__permission__code=ADMIN_PERMISSION_CODE,
            ).values_list("role_id", flat=True)
        )
        if current_admin_roles == {role.id}:
            return Response({"detail": "No puedes eliminar tu ultimo acceso de administracion."}, status=status.HTTP_409_CONFLICT)
    with transaction.atomic():
        role.name = data["name"]
        role.status = data["status"]
        role.save()
        role.permission_links.all().delete()
        CompanyRolePermission.objects.bulk_create(
            [CompanyRolePermission(role=role, permission=permission) for permission in permissions]
        )
        log_admin_event(
            company=company,
            actor=request.user,
            event_type="ROLE_UPDATED",
            resource_type="role",
            resource_id=role.id,
        )
    return Response({"role": RoleAdminSerializer(role).data})


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def branch_list_create_view(request):
    company, error = _company_from_request(request, source="query" if request.method == "GET" else "data")
    if error:
        return error
    if request.method == "GET":
        return Response({"branches": BranchAdminSerializer(company.branches.all(), many=True).data})
    serializer = BranchAdminSerializer(data=request.data, context={"company": company})
    serializer.is_valid(raise_exception=True)
    branch = serializer.save(company=company)
    membership = company.memberships.filter(user=request.user, status=CompanyMembership.Status.ACTIVE).first()
    if membership and not membership.role_assignments.filter(branch__isnull=True).exists():
        membership.branch_memberships.get_or_create(branch=branch)
    log_admin_event(
        company=company,
        actor=request.user,
        event_type="BRANCH_CREATED",
        resource_type="branch",
        resource_id=branch.id,
        metadata={"code": branch.code, "name": branch.name},
    )
    return Response({"branch": BranchAdminSerializer(branch).data}, status=status.HTTP_201_CREATED)


@api_view(["PATCH"])
@permission_classes([IsAuthenticated])
def branch_detail_view(request, branch_id):
    company, error = _company_from_request(request, source="data")
    if error:
        return error
    branch = company.branches.filter(pk=branch_id).first()
    if branch is None:
        return Response({"detail": "Sucursal no encontrada."}, status=status.HTTP_404_NOT_FOUND)
    serializer = BranchAdminSerializer(branch, data=request.data, partial=True, context={"company": company})
    serializer.is_valid(raise_exception=True)
    branch = serializer.save()
    log_admin_event(company=company, actor=request.user, event_type="BRANCH_UPDATED", resource_type="branch", resource_id=branch.id)
    return Response({"branch": BranchAdminSerializer(branch).data})


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def payment_method_list_create_view(request):
    company, error = _company_from_request(request, source="query" if request.method == "GET" else "data")
    if error:
        return error
    ensure_company_configuration(company)
    if request.method == "GET":
        return Response({"payment_methods": PaymentMethodSerializer(company.payment_methods.all(), many=True).data})
    serializer = PaymentMethodSerializer(data=request.data, context={"company": company})
    serializer.is_valid(raise_exception=True)
    method = serializer.save(company=company)
    log_admin_event(company=company, actor=request.user, event_type="PAYMENT_METHOD_CREATED", resource_type="payment_method", resource_id=method.id)
    return Response({"payment_method": PaymentMethodSerializer(method).data}, status=status.HTTP_201_CREATED)


@api_view(["PATCH"])
@permission_classes([IsAuthenticated])
def payment_method_detail_view(request, method_id):
    company, error = _company_from_request(request, source="data")
    if error:
        return error
    method = company.payment_methods.filter(pk=method_id).first()
    if method is None:
        return Response({"detail": "Metodo de pago no encontrado."}, status=status.HTTP_404_NOT_FOUND)
    serializer = PaymentMethodSerializer(method, data=request.data, partial=True, context={"company": company})
    serializer.is_valid(raise_exception=True)
    method = serializer.save()
    log_admin_event(company=company, actor=request.user, event_type="PAYMENT_METHOD_UPDATED", resource_type="payment_method", resource_id=method.id)
    return Response({"payment_method": PaymentMethodSerializer(method).data})


@api_view(["PATCH"])
@permission_classes([IsAuthenticated])
def order_status_detail_view(request, status_id):
    company, error = _company_from_request(request, source="data")
    if error:
        return error
    ensure_company_configuration(company)
    item = company.order_status_configurations.filter(pk=status_id).first()
    if item is None:
        return Response({"detail": "Estado de pedido no encontrado."}, status=status.HTTP_404_NOT_FOUND)
    serializer = OrderStatusConfigurationSerializer(item, data=request.data, partial=True)
    serializer.is_valid(raise_exception=True)
    item = serializer.save()
    log_admin_event(company=company, actor=request.user, event_type="ORDER_STATUS_UPDATED", resource_type="order_status", resource_id=item.id, metadata={"code": item.code})
    return Response({"order_status": OrderStatusConfigurationSerializer(item).data})


@api_view(["GET", "PATCH"])
@permission_classes([IsAuthenticated])
def company_settings_view(request):
    company, error = _company_from_request(request, source="query" if request.method == "GET" else "data")
    if error:
        return error
    ensure_company_configuration(company)
    settings_object = company.general_settings
    if request.method == "GET":
        return Response({"settings": CompanySettingsSerializer(settings_object).data})
    serializer = CompanySettingsSerializer(settings_object, data=request.data, partial=True)
    serializer.is_valid(raise_exception=True)
    settings_object = serializer.save()
    log_admin_event(company=company, actor=request.user, event_type="SETTINGS_UPDATED", resource_type="company_settings", resource_id=settings_object.id)
    return Response({"settings": CompanySettingsSerializer(settings_object).data})
