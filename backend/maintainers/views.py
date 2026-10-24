from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.models import User
from administration.models import CompanySettings, OrderStatusConfiguration, PaymentMethod
from catalog.models import Brand, Category, Product, ProductVariant, Supplier
from organizations.models import (
    Branch,
    Company,
    CompanyMembership,
    CompanyRole,
    CompanyRolePermission,
    Permission,
    RoleAssignment,
    Warehouse,
    normalize_role_name,
)

from administration.services import ADMIN_PERMISSION_CODE, replace_membership_access
from maintainers.access import IsPlatformAdmin
from maintainers.serializers import (
    AdministrationEventSerializer,
    BranchAdminSerializer,
    CategoryWriteSerializer,
    CompanyAdminSerializer,
    CompanySettingsSerializer,
    CompanySummarySerializer,
    MaintainerAuditEventSerializer,
    MaintainerCategorySerializer,
    MaintainerUserSerializer,
    MaintainerWarehouseSerializer,
    MembershipUserSerializer,
    OrderStatusConfigurationSerializer,
    PaymentMethodSerializer,
    PermissionAdminSerializer,
    ProductVariantWriteSerializer,
    ProductWriteSerializer,
    RoleAdminSerializer,
    RoleWriteSerializer,
    SupplierWriteSerializer,
    UserCreateSerializer,
    UserUpdateSerializer,
    WarehouseWriteSerializer,
)
from maintainers.models import MaintainerAuditEvent
from maintainers.lifecycle import (
    LifecycleError,
    change_state,
    create_challenge,
    execute_challenge,
    preview as lifecycle_preview,
)
from catalog.serializers import (
    BrandSummarySerializer,
    ProductSerializer,
    SupplierSerializer,
)
from maintainers.services import build_context, company_queryset, get_company, prepare_company, record_event


PLATFORM_PERMISSIONS = [IsAuthenticated, IsPlatformAdmin]


def _company_or_404(company_id):
    company = get_company(company_id)
    if company is None:
        return None, Response({"detail": "Empresa no encontrada."}, status=status.HTTP_404_NOT_FOUND)
    return company, None


def _without_company(data):
    payload = data.copy()
    payload.pop("company", None)
    return payload


def _save_event(*, company, actor, event_type, resource_type, resource_id="", metadata=None):
    record_event(
        company=company,
        actor=actor,
        event_type=event_type,
        resource_type=resource_type,
        resource_id=resource_id,
        metadata=metadata,
    )


@api_view(["GET"])
@permission_classes(PLATFORM_PERMISSIONS)
def context_view(request):
    companies, summary = build_context()
    return Response(
        {
            "user": MaintainerUserSerializer(request.user).data,
            "companies": CompanySummarySerializer(companies, many=True).data,
            "summary": summary,
        }
    )


def _overview(company):
    prepare_company(company)
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
@permission_classes(PLATFORM_PERMISSIONS)
def overview_view(request, company_id):
    company, error = _company_or_404(company_id)
    if error:
        return error
    return Response(_overview(company))


@api_view(["GET", "POST"])
@permission_classes(PLATFORM_PERMISSIONS)
def company_create_view(request):
    if request.method == "GET":
        return Response({"companies": CompanySummarySerializer(company_queryset(), many=True).data})
    serializer = CompanyAdminSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    company = Company.objects.create(**serializer.validated_data)
    prepare_company(company)
    _save_event(company=company, actor=request.user, event_type="COMPANY_CREATED", resource_type="company", resource_id=company.id)
    return Response({"company": CompanyAdminSerializer(company).data}, status=status.HTTP_201_CREATED)


@api_view(["GET", "PATCH"])
@permission_classes(PLATFORM_PERMISSIONS)
def company_detail_view(request, company_id):
    company, error = _company_or_404(company_id)
    if error:
        return error
    if request.method == "GET":
        return Response({"company": CompanyAdminSerializer(company).data})
    serializer = CompanyAdminSerializer(company, data=_without_company(request.data), partial=True)
    serializer.is_valid(raise_exception=True)
    company = serializer.save()
    _save_event(company=company, actor=request.user, event_type="COMPANY_UPDATED", resource_type="company", resource_id=company.id)
    return Response({"company": CompanyAdminSerializer(company).data})


@api_view(["GET", "POST"])
@permission_classes(PLATFORM_PERMISSIONS)
def branch_list_create_view(request, company_id):
    company, error = _company_or_404(company_id)
    if error:
        return error
    if request.method == "GET":
        return Response({"branches": BranchAdminSerializer(company.branches.all(), many=True).data})
    serializer = BranchAdminSerializer(
        data=_without_company(request.data),
        context={"company": company},
    )
    serializer.is_valid(raise_exception=True)
    branch = serializer.save(company=company)
    _save_event(company=company, actor=request.user, event_type="BRANCH_CREATED", resource_type="branch", resource_id=branch.id)
    return Response({"branch": BranchAdminSerializer(branch).data}, status=status.HTTP_201_CREATED)


@api_view(["PATCH"])
@permission_classes(PLATFORM_PERMISSIONS)
def branch_detail_view(request, company_id, branch_id):
    company, error = _company_or_404(company_id)
    if error:
        return error
    branch = company.branches.filter(pk=branch_id).first()
    if branch is None:
        return Response({"detail": "Sucursal no encontrada en esta empresa."}, status=status.HTTP_404_NOT_FOUND)
    serializer = BranchAdminSerializer(
        branch,
        data=_without_company(request.data),
        partial=True,
        context={"company": company},
    )
    serializer.is_valid(raise_exception=True)
    branch = serializer.save()
    _save_event(company=company, actor=request.user, event_type="BRANCH_UPDATED", resource_type="branch", resource_id=branch.id)
    return Response({"branch": BranchAdminSerializer(branch).data})


@api_view(["GET", "POST"])
@permission_classes(PLATFORM_PERMISSIONS)
def user_list_create_view(request, company_id):
    company, error = _company_or_404(company_id)
    if error:
        return error
    if request.method == "GET":
        memberships = company.memberships.select_related("user").prefetch_related(
            "branch_memberships", "role_assignments__role"
        )
        return Response({"users": MembershipUserSerializer(memberships, many=True).data})
    serializer = UserCreateSerializer(data=_without_company(request.data), context={"company": company})
    serializer.is_valid(raise_exception=True)
    membership = serializer.save()
    _save_event(company=company, actor=request.user, event_type="USER_ADDED", resource_type="membership", resource_id=membership.id)
    return Response({"user": MembershipUserSerializer(membership).data}, status=status.HTTP_201_CREATED)


@api_view(["PATCH"])
@permission_classes(PLATFORM_PERMISSIONS)
def user_detail_view(request, company_id, membership_id):
    company, error = _company_or_404(company_id)
    if error:
        return error
    membership = company.memberships.select_related("user").filter(pk=membership_id).first()
    if membership is None:
        return Response({"detail": "Usuario no encontrado en esta empresa."}, status=status.HTTP_404_NOT_FOUND)
    serializer = UserUpdateSerializer(
        data=_without_company(request.data), partial=True, context={"company": company}
    )
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    branch_ids = data.get("branch_ids", list(membership.branch_memberships.values_list("branch_id", flat=True)))
    role_ids = data.get("role_ids", list(membership.role_assignments.values_list("role_id", flat=True).distinct()))
    try:
        with transaction.atomic():
            user = membership.user
            if "first_name" in data or "last_name" in data:
                user.first_name = data.get("first_name", user.first_name).strip()
                user.last_name = data.get("last_name", user.last_name).strip()
                user.save(update_fields=["first_name", "last_name"])
            if "status" in data:
                membership.status = data["status"]
                membership.save(update_fields=["status", "updated_at"])
            replace_membership_access(membership=membership, branch_ids=branch_ids, role_ids=role_ids)
            _save_event(company=company, actor=request.user, event_type="USER_UPDATED", resource_type="membership", resource_id=membership.id)
    except ValueError as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    membership.refresh_from_db()
    return Response({"user": MembershipUserSerializer(membership).data})


@api_view(["POST"])
@permission_classes(PLATFORM_PERMISSIONS)
def user_revoke_access_view(request, company_id, membership_id):
    company, error = _company_or_404(company_id)
    if error:
        return error
    membership = company.memberships.select_related("user").filter(pk=membership_id).first()
    if membership is None:
        return Response({"detail": "Usuario no encontrado en esta empresa."}, status=status.HTTP_404_NOT_FOUND)
    if membership.status == CompanyMembership.Status.LEFT:
        return Response({"detail": "El usuario ya está desvinculado de esta empresa."}, status=status.HTTP_400_BAD_REQUEST)
    with transaction.atomic():
        removed_roles = list(membership.role_assignments.values_list("role__name", flat=True).distinct())
        removed_branches = list(membership.branch_memberships.values_list("branch__name", flat=True))
        membership.role_assignments.all().delete()
        membership.branch_memberships.all().delete()
        membership.status = CompanyMembership.Status.LEFT
        membership.save(update_fields=["status", "updated_at"])
        _save_event(
            company=company,
            actor=request.user,
            event_type="USER_ACCESS_REVOKED",
            resource_type="membership",
            resource_id=membership.id,
            metadata={"roles": removed_roles, "branches": removed_branches},
        )
    membership.refresh_from_db()
    return Response({"user": MembershipUserSerializer(membership).data})


@api_view(["GET", "POST"])
@permission_classes(PLATFORM_PERMISSIONS)
def role_list_create_view(request, company_id):
    company, error = _company_or_404(company_id)
    if error:
        return error
    if request.method == "GET":
        return Response({"roles": RoleAdminSerializer(company.roles.prefetch_related("permission_links__permission"), many=True).data})
    serializer = RoleWriteSerializer(data=_without_company(request.data))
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
        _save_event(company=company, actor=request.user, event_type="ROLE_CREATED", resource_type="role", resource_id=role.id)
    return Response({"role": RoleAdminSerializer(role).data}, status=status.HTTP_201_CREATED)


@api_view(["PATCH"])
@permission_classes(PLATFORM_PERMISSIONS)
def role_detail_view(request, company_id, role_id):
    company, error = _company_or_404(company_id)
    if error:
        return error
    role = company.roles.prefetch_related("permission_links__permission").filter(pk=role_id).first()
    if role is None:
        return Response({"detail": "Rol no encontrado en esta empresa."}, status=status.HTTP_404_NOT_FOUND)
    payload = _without_company(request.data)
    payload.setdefault("name", role.name)
    payload.setdefault("status", role.status)
    payload.setdefault("permission_codes", list(role.permission_links.values_list("permission__code", flat=True)))
    serializer = RoleWriteSerializer(data=payload)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    if company.roles.exclude(pk=role.id).filter(name_normalized=normalize_role_name(data["name"])).exists():
        return Response({"name": ["Ya existe un rol con ese nombre."]}, status=status.HTTP_400_BAD_REQUEST)
    permissions = list(Permission.objects.filter(code__in=data["permission_codes"]))
    with transaction.atomic():
        role.name = data["name"]
        role.status = data["status"]
        role.save()
        role.permission_links.all().delete()
        CompanyRolePermission.objects.bulk_create(
            [CompanyRolePermission(role=role, permission=permission) for permission in permissions]
        )
        _save_event(company=company, actor=request.user, event_type="ROLE_UPDATED", resource_type="role", resource_id=role.id)
    return Response({"role": RoleAdminSerializer(role).data})


@api_view(["GET", "POST"])
@permission_classes(PLATFORM_PERMISSIONS)
def payment_method_list_create_view(request, company_id):
    company, error = _company_or_404(company_id)
    if error:
        return error
    prepare_company(company)
    if request.method == "GET":
        return Response({"payment_methods": PaymentMethodSerializer(company.payment_methods.all(), many=True).data})
    serializer = PaymentMethodSerializer(data=_without_company(request.data), context={"company": company})
    serializer.is_valid(raise_exception=True)
    method = serializer.save(company=company)
    _save_event(company=company, actor=request.user, event_type="PAYMENT_METHOD_CREATED", resource_type="payment_method", resource_id=method.id)
    return Response({"payment_method": PaymentMethodSerializer(method).data}, status=status.HTTP_201_CREATED)


@api_view(["PATCH"])
@permission_classes(PLATFORM_PERMISSIONS)
def payment_method_detail_view(request, company_id, method_id):
    company, error = _company_or_404(company_id)
    if error:
        return error
    method = company.payment_methods.filter(pk=method_id).first()
    if method is None:
        return Response({"detail": "Metodo de pago no encontrado en esta empresa."}, status=status.HTTP_404_NOT_FOUND)
    serializer = PaymentMethodSerializer(method, data=_without_company(request.data), partial=True, context={"company": company})
    serializer.is_valid(raise_exception=True)
    method = serializer.save()
    _save_event(company=company, actor=request.user, event_type="PAYMENT_METHOD_UPDATED", resource_type="payment_method", resource_id=method.id)
    return Response({"payment_method": PaymentMethodSerializer(method).data})


@api_view(["PATCH"])
@permission_classes(PLATFORM_PERMISSIONS)
def order_status_detail_view(request, company_id, status_id):
    company, error = _company_or_404(company_id)
    if error:
        return error
    prepare_company(company)
    item = company.order_status_configurations.filter(pk=status_id).first()
    if item is None:
        return Response({"detail": "Estado de pedido no encontrado en esta empresa."}, status=status.HTTP_404_NOT_FOUND)
    serializer = OrderStatusConfigurationSerializer(item, data=_without_company(request.data), partial=True)
    serializer.is_valid(raise_exception=True)
    item = serializer.save()
    _save_event(company=company, actor=request.user, event_type="ORDER_STATUS_UPDATED", resource_type="order_status", resource_id=item.id)
    return Response({"order_status": OrderStatusConfigurationSerializer(item).data})


@api_view(["GET", "PATCH"])
@permission_classes(PLATFORM_PERMISSIONS)
def settings_view(request, company_id):
    company, error = _company_or_404(company_id)
    if error:
        return error
    prepare_company(company)
    settings_object = company.general_settings
    if request.method == "GET":
        return Response({"settings": CompanySettingsSerializer(settings_object).data})
    serializer = CompanySettingsSerializer(settings_object, data=_without_company(request.data), partial=True)
    serializer.is_valid(raise_exception=True)
    settings_object = serializer.save()
    _save_event(company=company, actor=request.user, event_type="SETTINGS_UPDATED", resource_type="company_settings", resource_id=settings_object.id)
    return Response({"settings": CompanySettingsSerializer(settings_object).data})


@api_view(["GET", "POST"])
@permission_classes(PLATFORM_PERMISSIONS)
def lifecycle_view(request, company_id, resource_type, resource_id):
    """Preview, archive/reactivate, or permanently remove one resource."""
    try:
        if request.method == "GET":
            return Response(
                lifecycle_preview(
                    actor=request.user,
                    company_id=company_id,
                    resource_type=resource_type,
                    resource_id=resource_id,
                )
            )

        action = str(request.data.get("action", "")).strip().lower()
        if action in {"deactivate", "activate"}:
            resource = change_state(
                actor=request.user,
                company_id=company_id,
                resource_type=resource_type,
                resource_id=resource_id,
                active=action == "activate",
            )
            return Response(
                {
                    "detail": "Recurso reactivado." if action == "activate" else "Recurso desactivado.",
                    "resource_id": resource.id,
                    "resource_type": resource_type,
                }
            )

        if action == "challenge":
            challenge, token, details = create_challenge(
                actor=request.user,
                company_id=company_id,
                resource_type=resource_type,
                resource_id=resource_id,
                confirmation=str(request.data.get("confirmation", "")),
                reason=str(request.data.get("reason", "")),
            )
            return Response(
                {
                    "challenge_id": challenge.id,
                    "token": token,
                    "expires_at": challenge.expires_at,
                    "resource": details,
                },
                status=status.HTTP_201_CREATED,
            )

        if action == "execute":
            deleted = execute_challenge(
                actor=request.user,
                challenge_id=int(request.data.get("challenge_id")),
                token=str(request.data.get("token", "")),
                confirmation=str(request.data.get("confirmation", "")),
            )
            return Response({"detail": "Recurso eliminado permanentemente.", "resource": deleted})

        return Response(
            {"detail": "Acción no válida. Usa activate, deactivate, challenge o execute."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    except (TypeError, ValueError):
        return Response({"detail": "Los datos de la operación no son válidos."}, status=status.HTTP_400_BAD_REQUEST)
    except LifecycleError as exc:
        return Response({"detail": str(exc)}, status=exc.status_code)


@api_view(["GET"])
@permission_classes(PLATFORM_PERMISSIONS)
def audit_view(request):
    events = MaintainerAuditEvent.objects.select_related("actor").all()
    company_id = request.query_params.get("company_id", "").strip()
    if company_id:
        try:
            events = events.filter(company_id_snapshot=int(company_id))
        except ValueError:
            return Response({"detail": "company_id debe ser numérico."}, status=status.HTTP_400_BAD_REQUEST)

    actor = request.query_params.get("actor", "").strip()
    if actor:
        events = events.filter(
            Q(actor__email__icontains=actor)
            | Q(actor__username__icontains=actor)
            | Q(actor__first_name__icontains=actor)
            | Q(actor__last_name__icontains=actor)
        )
    event_type = request.query_params.get("event_type", "").strip()
    if event_type:
        events = events.filter(event_type=event_type)
    resource_type = request.query_params.get("resource_type", "").strip()
    if resource_type:
        events = events.filter(resource_type=resource_type)
    search = request.query_params.get("q", "").strip()
    if search:
        events = events.filter(
            Q(event_type__icontains=search)
            | Q(resource_type__icontains=search)
            | Q(resource_id__icontains=search)
            | Q(actor__email__icontains=search)
            | Q(actor__username__icontains=search)
        )

    for parameter, lookup in (("from", "created_at__gte"), ("to", "created_at__lt")):
        raw_value = request.query_params.get(parameter, "").strip()
        if not raw_value:
            continue
        parsed = parse_datetime(raw_value)
        if parsed is None:
            return Response(
                {"detail": f"El parámetro {parameter} debe ser una fecha ISO válida."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if timezone.is_naive(parsed):
            parsed = timezone.make_aware(parsed)
        events = events.filter(**{lookup: parsed})

    try:
        page = max(1, int(request.query_params.get("page", "1")))
        page_size = min(200, max(1, int(request.query_params.get("page_size", "50"))))
    except ValueError:
        return Response({"detail": "page y page_size deben ser numéricos."}, status=status.HTTP_400_BAD_REQUEST)

    total = events.count()
    start = (page - 1) * page_size
    page_events = events.order_by("-created_at", "-id")[start : start + page_size]
    return Response(
        {
            "events": MaintainerAuditEventSerializer(page_events, many=True).data,
            "total": total,
            "page": page,
            "page_size": page_size,
            "has_next": start + page_size < total,
        }
    )


@api_view(["GET"])
@permission_classes(PLATFORM_PERMISSIONS)
def catalog_view(request, company_id):
    company, error = _company_or_404(company_id)
    if error:
        return error
    categories = company.categories.select_related("parent").all()
    brands = company.brands.all()
    products = company.products.select_related("category", "brand").prefetch_related("variants").all()
    return Response(
        {
            "categories": MaintainerCategorySerializer(categories, many=True).data,
            "brands": BrandSummarySerializer(brands, many=True).data,
            "products": ProductSerializer(products, many=True).data,
        }
    )


@api_view(["GET", "POST"])
@permission_classes(PLATFORM_PERMISSIONS)
def category_list_create_view(request, company_id):
    company, error = _company_or_404(company_id)
    if error:
        return error
    if request.method == "GET":
        return Response({"categories": MaintainerCategorySerializer(company.categories.select_related("parent"), many=True).data})
    serializer = CategoryWriteSerializer(data=_without_company(request.data), context={"company": company})
    serializer.is_valid(raise_exception=True)
    category = serializer.save()
    _save_event(company=company, actor=request.user, event_type="CATEGORY_CREATED", resource_type="category", resource_id=category.id)
    return Response({"category": MaintainerCategorySerializer(category).data}, status=status.HTTP_201_CREATED)


@api_view(["PATCH"])
@permission_classes(PLATFORM_PERMISSIONS)
def category_detail_view(request, company_id, category_id):
    company, error = _company_or_404(company_id)
    if error:
        return error
    category = company.categories.select_related("parent").filter(pk=category_id).first()
    if category is None:
        return Response({"detail": "Categoria no encontrada en esta empresa."}, status=status.HTTP_404_NOT_FOUND)
    serializer = CategoryWriteSerializer(category, data=_without_company(request.data), partial=True, context={"company": company})
    serializer.is_valid(raise_exception=True)
    category = serializer.save()
    category = Category.objects.select_related("parent").get(pk=category.id)
    _save_event(company=company, actor=request.user, event_type="CATEGORY_UPDATED", resource_type="category", resource_id=category.id)
    return Response({"category": MaintainerCategorySerializer(category).data})


@api_view(["POST", "PATCH"])
@permission_classes(PLATFORM_PERMISSIONS)
def category_toggle_view(request, company_id, category_id):
    company, error = _company_or_404(company_id)
    if error:
        return error
    category = company.categories.filter(pk=category_id).first()
    if category is None:
        return Response({"detail": "Categoria no encontrada en esta empresa."}, status=status.HTTP_404_NOT_FOUND)
    requested_status = request.data.get("status")
    if requested_status not in {choice[0] for choice in Category.Status.choices}:
        requested_status = Category.Status.INACTIVE if category.status == Category.Status.ACTIVE else Category.Status.ACTIVE
    category.status = requested_status
    category.save(update_fields=["status"])
    _save_event(
        company=company,
        actor=request.user,
        event_type="CATEGORY_STATUS_UPDATED",
        resource_type="category",
        resource_id=category.id,
        metadata={"status": category.status},
    )
    return Response({"category": MaintainerCategorySerializer(category).data})


@api_view(["GET", "POST"])
@permission_classes(PLATFORM_PERMISSIONS)
def brand_list_create_view(request, company_id):
    company, error = _company_or_404(company_id)
    if error:
        return error
    if request.method == "GET":
        return Response({"brands": BrandSummarySerializer(company.brands.all(), many=True).data})
    from maintainers.serializers import BrandWriteSerializer

    serializer = BrandWriteSerializer(data=_without_company(request.data), context={"company": company})
    serializer.is_valid(raise_exception=True)
    brand = serializer.save()
    _save_event(company=company, actor=request.user, event_type="BRAND_CREATED", resource_type="brand", resource_id=brand.id)
    return Response({"brand": BrandSummarySerializer(brand).data}, status=status.HTTP_201_CREATED)


@api_view(["PATCH"])
@permission_classes(PLATFORM_PERMISSIONS)
def brand_detail_view(request, company_id, brand_id):
    company, error = _company_or_404(company_id)
    if error:
        return error
    brand = company.brands.filter(pk=brand_id).first()
    if brand is None:
        return Response({"detail": "Marca no encontrada en esta empresa."}, status=status.HTTP_404_NOT_FOUND)
    from maintainers.serializers import BrandWriteSerializer

    serializer = BrandWriteSerializer(brand, data=_without_company(request.data), partial=True, context={"company": company})
    serializer.is_valid(raise_exception=True)
    brand = serializer.save()
    _save_event(company=company, actor=request.user, event_type="BRAND_UPDATED", resource_type="brand", resource_id=brand.id)
    return Response({"brand": BrandSummarySerializer(brand).data})


@api_view(["GET", "POST"])
@permission_classes(PLATFORM_PERMISSIONS)
def product_list_create_view(request, company_id):
    company, error = _company_or_404(company_id)
    if error:
        return error
    if request.method == "GET":
        products = company.products.select_related("category", "brand").prefetch_related("variants")
        return Response({"products": ProductSerializer(products, many=True).data})
    serializer = ProductWriteSerializer(data=_without_company(request.data), context={"company": company})
    serializer.is_valid(raise_exception=True)
    product = serializer.save()
    product = Product.objects.select_related("category", "brand").prefetch_related("variants").get(pk=product.pk)
    _save_event(company=company, actor=request.user, event_type="PRODUCT_CREATED", resource_type="product", resource_id=product.id)
    return Response({"product": ProductSerializer(product).data}, status=status.HTTP_201_CREATED)


@api_view(["GET", "PATCH"])
@permission_classes(PLATFORM_PERMISSIONS)
def product_detail_view(request, company_id, product_id):
    company, error = _company_or_404(company_id)
    if error:
        return error
    product = company.products.select_related("category", "brand").prefetch_related("variants").filter(pk=product_id).first()
    if product is None:
        return Response({"detail": "Producto no encontrado en esta empresa."}, status=status.HTTP_404_NOT_FOUND)
    if request.method == "GET":
        return Response({"product": ProductSerializer(product).data})
    serializer = ProductWriteSerializer(product, data=_without_company(request.data), partial=True, context={"company": company})
    serializer.is_valid(raise_exception=True)
    product = serializer.save()
    product = Product.objects.select_related("category", "brand").prefetch_related("variants").get(pk=product.pk)
    _save_event(company=company, actor=request.user, event_type="PRODUCT_UPDATED", resource_type="product", resource_id=product.id)
    return Response({"product": ProductSerializer(product).data})


@api_view(["POST", "PATCH"])
@permission_classes(PLATFORM_PERMISSIONS)
def product_toggle_view(request, company_id, product_id):
    company, error = _company_or_404(company_id)
    if error:
        return error
    product = company.products.select_related("category", "brand").prefetch_related("variants").filter(pk=product_id).first()
    if product is None:
        return Response({"detail": "Producto no encontrado en esta empresa."}, status=status.HTTP_404_NOT_FOUND)
    requested_status = request.data.get("status")
    if requested_status not in {choice[0] for choice in Product.Status.choices}:
        requested_status = Product.Status.INACTIVE if product.status == Product.Status.ACTIVE else Product.Status.ACTIVE
    product.status = requested_status
    product.save(update_fields=["status"])
    _save_event(
        company=company,
        actor=request.user,
        event_type="PRODUCT_STATUS_UPDATED",
        resource_type="product",
        resource_id=product.id,
        metadata={"status": product.status},
    )
    return Response({"product": ProductSerializer(product).data})


@api_view(["GET", "POST"])
@permission_classes(PLATFORM_PERMISSIONS)
def variant_list_create_view(request, company_id, product_id):
    company, error = _company_or_404(company_id)
    if error:
        return error
    product = company.products.filter(pk=product_id).first()
    if product is None:
        return Response({"detail": "Producto no encontrado en esta empresa."}, status=status.HTTP_404_NOT_FOUND)
    if request.method == "GET":
        from catalog.serializers import ProductVariantSerializer

        return Response({"variants": ProductVariantSerializer(product.variants.all(), many=True).data})
    serializer = ProductVariantWriteSerializer(data=_without_company(request.data), context={"product": product})
    serializer.is_valid(raise_exception=True)
    variant = serializer.save()
    _save_event(company=company, actor=request.user, event_type="VARIANT_CREATED", resource_type="product_variant", resource_id=variant.id)
    from catalog.serializers import ProductVariantSerializer

    return Response({"variant": ProductVariantSerializer(variant).data}, status=status.HTTP_201_CREATED)


@api_view(["GET", "PATCH"])
@permission_classes(PLATFORM_PERMISSIONS)
def variant_detail_view(request, company_id, product_id, variant_id):
    company, error = _company_or_404(company_id)
    if error:
        return error
    product = company.products.filter(pk=product_id).first()
    if product is None:
        return Response({"detail": "Producto no encontrado en esta empresa."}, status=status.HTTP_404_NOT_FOUND)
    variant = product.variants.filter(pk=variant_id).first()
    if variant is None:
        return Response({"detail": "Variante no encontrada en este producto."}, status=status.HTTP_404_NOT_FOUND)
    from catalog.serializers import ProductVariantSerializer

    if request.method == "GET":
        return Response({"variant": ProductVariantSerializer(variant).data})
    serializer = ProductVariantWriteSerializer(variant, data=_without_company(request.data), partial=True, context={"product": product})
    serializer.is_valid(raise_exception=True)
    variant = serializer.save()
    _save_event(company=company, actor=request.user, event_type="VARIANT_UPDATED", resource_type="product_variant", resource_id=variant.id)
    return Response({"variant": ProductVariantSerializer(variant).data})


@api_view(["POST", "PATCH"])
@permission_classes(PLATFORM_PERMISSIONS)
def variant_toggle_view(request, company_id, product_id, variant_id):
    company, error = _company_or_404(company_id)
    if error:
        return error
    product = company.products.filter(pk=product_id).first()
    variant = product.variants.filter(pk=variant_id).first() if product is not None else None
    if variant is None:
        return Response({"detail": "Variante no encontrada en este producto."}, status=status.HTTP_404_NOT_FOUND)
    requested_status = request.data.get("status")
    if requested_status not in {choice[0] for choice in ProductVariant.Status.choices}:
        requested_status = ProductVariant.Status.INACTIVE if variant.status == ProductVariant.Status.ACTIVE else ProductVariant.Status.ACTIVE
    variant.status = requested_status
    variant.save(update_fields=["status"])
    _save_event(
        company=company,
        actor=request.user,
        event_type="VARIANT_STATUS_UPDATED",
        resource_type="product_variant",
        resource_id=variant.id,
        metadata={"status": variant.status},
    )
    from catalog.serializers import ProductVariantSerializer

    return Response({"variant": ProductVariantSerializer(variant).data})


@api_view(["GET"])
@permission_classes(PLATFORM_PERMISSIONS)
def directories_view(request, company_id):
    company, error = _company_or_404(company_id)
    if error:
        return error
    suppliers = company.suppliers.all()
    warehouses = company.warehouses.select_related("branch").all()
    return Response(
        {
            "suppliers": SupplierSerializer(suppliers, many=True).data,
            "warehouses": MaintainerWarehouseSerializer(warehouses, many=True).data,
        }
    )


@api_view(["GET", "POST"])
@permission_classes(PLATFORM_PERMISSIONS)
def supplier_list_create_view(request, company_id):
    company, error = _company_or_404(company_id)
    if error:
        return error
    if request.method == "GET":
        return Response({"suppliers": SupplierSerializer(company.suppliers.all(), many=True).data})
    serializer = SupplierWriteSerializer(data=_without_company(request.data), context={"company": company})
    serializer.is_valid(raise_exception=True)
    supplier = serializer.save()
    _save_event(company=company, actor=request.user, event_type="SUPPLIER_CREATED", resource_type="supplier", resource_id=supplier.id)
    return Response({"supplier": SupplierSerializer(supplier).data}, status=status.HTTP_201_CREATED)


@api_view(["PATCH"])
@permission_classes(PLATFORM_PERMISSIONS)
def supplier_detail_view(request, company_id, supplier_id):
    company, error = _company_or_404(company_id)
    if error:
        return error
    supplier = company.suppliers.filter(pk=supplier_id).first()
    if supplier is None:
        return Response({"detail": "Proveedor no encontrado en esta empresa."}, status=status.HTTP_404_NOT_FOUND)
    serializer = SupplierWriteSerializer(supplier, data=_without_company(request.data), partial=True, context={"company": company})
    serializer.is_valid(raise_exception=True)
    supplier = serializer.save()
    _save_event(company=company, actor=request.user, event_type="SUPPLIER_UPDATED", resource_type="supplier", resource_id=supplier.id)
    return Response({"supplier": SupplierSerializer(supplier).data})


@api_view(["POST", "PATCH"])
@permission_classes(PLATFORM_PERMISSIONS)
def supplier_toggle_view(request, company_id, supplier_id):
    company, error = _company_or_404(company_id)
    if error:
        return error
    supplier = company.suppliers.filter(pk=supplier_id).first()
    if supplier is None:
        return Response({"detail": "Proveedor no encontrado en esta empresa."}, status=status.HTTP_404_NOT_FOUND)
    requested_status = request.data.get("status")
    if requested_status not in {choice[0] for choice in Supplier.Status.choices}:
        requested_status = Supplier.Status.INACTIVE if supplier.status == Supplier.Status.ACTIVE else Supplier.Status.ACTIVE
    supplier.status = requested_status
    supplier.save(update_fields=["status"])
    _save_event(
        company=company,
        actor=request.user,
        event_type="SUPPLIER_STATUS_UPDATED",
        resource_type="supplier",
        resource_id=supplier.id,
        metadata={"status": supplier.status},
    )
    return Response({"supplier": SupplierSerializer(supplier).data})


@api_view(["GET", "POST"])
@permission_classes(PLATFORM_PERMISSIONS)
def warehouse_list_create_view(request, company_id):
    company, error = _company_or_404(company_id)
    if error:
        return error
    if request.method == "GET":
        warehouses = company.warehouses.select_related("branch")
        return Response({"warehouses": MaintainerWarehouseSerializer(warehouses, many=True).data})
    serializer = WarehouseWriteSerializer(data=_without_company(request.data), context={"company": company})
    serializer.is_valid(raise_exception=True)
    warehouse = serializer.save()
    _save_event(company=company, actor=request.user, event_type="WAREHOUSE_CREATED", resource_type="warehouse", resource_id=warehouse.id)
    return Response({"warehouse": MaintainerWarehouseSerializer(warehouse).data}, status=status.HTTP_201_CREATED)


@api_view(["PATCH"])
@permission_classes(PLATFORM_PERMISSIONS)
def warehouse_detail_view(request, company_id, warehouse_id):
    company, error = _company_or_404(company_id)
    if error:
        return error
    warehouse = company.warehouses.select_related("branch").filter(pk=warehouse_id).first()
    if warehouse is None:
        return Response({"detail": "Bodega no encontrada en esta empresa."}, status=status.HTTP_404_NOT_FOUND)
    serializer = WarehouseWriteSerializer(warehouse, data=_without_company(request.data), partial=True, context={"company": company})
    serializer.is_valid(raise_exception=True)
    warehouse = serializer.save()
    _save_event(company=company, actor=request.user, event_type="WAREHOUSE_UPDATED", resource_type="warehouse", resource_id=warehouse.id)
    return Response({"warehouse": MaintainerWarehouseSerializer(warehouse).data})
