from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from organizations.authorization import has_permission
from organizations.models import (
    CompanyMembership,
    RoleAssignment,
    Warehouse,
)
from organizations.serializers import (
    OrganizationContextMembershipSerializer,
    WarehouseCreateSerializer,
    WarehouseSerializer,
)


WAREHOUSES_MANAGE_PERMISSION_CODE = (
    "organizations.warehouses.manage"
)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def organization_context_view(request):
    memberships = (
        CompanyMembership.objects.filter(
            user=request.user,
            status=CompanyMembership.Status.ACTIVE,
        )
        .select_related("company")
        .prefetch_related("branch_memberships__branch")
    )

    return Response(
        {
            "memberships": OrganizationContextMembershipSerializer(
                memberships,
                many=True,
            ).data,
        }
    )


def _parse_company_id(raw_company_id):
    if isinstance(raw_company_id, bool):
        return None

    if isinstance(raw_company_id, int):
        company_id = raw_company_id

    elif isinstance(raw_company_id, str):
        raw_company_id = raw_company_id.strip()

        if not raw_company_id.isdecimal():
            return None

        company_id = int(raw_company_id)

    else:
        return None

    if company_id <= 0:
        return None

    return company_id


def _get_active_membership(*, user, company_id):
    return (
        CompanyMembership.objects.filter(
            user=user,
            company_id=company_id,
            status=CompanyMembership.Status.ACTIVE,
        )
        .select_related("company")
        .first()
    )


def _get_authorized_warehouses(
    *,
    user,
    company,
):
    if not has_permission(
        user=user,
        company=company,
        permission_code=WAREHOUSES_MANAGE_PERMISSION_CODE,
    ):
        return Warehouse.objects.none()

    assignments = RoleAssignment.objects.filter(
        membership__user=user,
        membership__company=company,
        membership__status=CompanyMembership.Status.ACTIVE,
        role__permission_links__permission__code=(
            WAREHOUSES_MANAGE_PERMISSION_CODE
        ),
    )

    if assignments.filter(
        branch__isnull=True,
    ).exists():
        return Warehouse.objects.filter(
            company=company,
        )

    branch_ids = assignments.values_list(
        "branch_id",
        flat=True,
    )

    return Warehouse.objects.filter(
        company=company,
        branch_id__in=branch_ids,
    )


def _can_manage_warehouse_branch(
    *,
    user,
    company,
    branch,
):
    return has_permission(
        user=user,
        company=company,
        permission_code=WAREHOUSES_MANAGE_PERMISSION_CODE,
        branch=branch,
    )


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def warehouse_list_create_view(request):
    if request.method == "POST":
        return _create_warehouse(request)

    return _list_warehouses(request)


def _list_warehouses(request):
    raw_company_id = request.query_params.get("company")

    if raw_company_id in (None, ""):
        return Response(
            {
                "detail": "El parametro company es obligatorio.",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    company_id = _parse_company_id(raw_company_id)

    if company_id is None:
        return Response(
            {
                "detail": "El parametro company debe ser un entero valido.",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    membership = _get_active_membership(
        user=request.user,
        company_id=company_id,
    )

    if membership is None:
        return Response(
            {
                "detail": "No tienes acceso a esta empresa.",
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    warehouses = _get_authorized_warehouses(
        user=request.user,
        company=membership.company,
    )

    if not warehouses.exists():
        if not has_permission(
            user=request.user,
            company=membership.company,
            permission_code=WAREHOUSES_MANAGE_PERMISSION_CODE,
        ):
            return Response(
                {
                    "detail": (
                        "No tienes permiso para administrar las bodegas."
                    ),
                },
                status=status.HTTP_403_FORBIDDEN,
            )

    return Response(
        {
            "warehouses": WarehouseSerializer(
                warehouses,
                many=True,
            ).data,
        }
    )


def _create_warehouse(request):
    raw_company_id = request.data.get("company")

    if raw_company_id in (None, ""):
        return Response(
            {
                "detail": "El campo company es obligatorio.",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    company_id = _parse_company_id(raw_company_id)

    if company_id is None:
        return Response(
            {
                "detail": "El campo company debe ser un entero valido.",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    membership = _get_active_membership(
        user=request.user,
        company_id=company_id,
    )

    if membership is None:
        return Response(
            {
                "detail": "No tienes acceso a esta empresa.",
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    company = membership.company

    serializer = WarehouseCreateSerializer(
        data=request.data,
        context={
            "company": company,
        },
    )

    serializer.is_valid(
        raise_exception=True,
    )

    branch = serializer.validated_data.get("branch")

    if not _can_manage_warehouse_branch(
        user=request.user,
        company=company,
        branch=branch,
    ):
        return Response(
            {
                "detail": (
                    "No tienes permiso para administrar "
                    "esta sucursal de la bodega."
                ),
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    warehouse = serializer.save()

    return Response(
        {
            "warehouse": WarehouseSerializer(
                warehouse,
            ).data,
        },
        status=status.HTTP_201_CREATED,
    )
