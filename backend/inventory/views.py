from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from inventory.models import InventoryStock
from inventory.serializers import (
    InventoryStockCreateSerializer,
    InventoryStockSerializer,
)

from organizations.authorization import has_permission
from organizations.models import (
    CompanyMembership,
    RoleAssignment,
)


INVENTORY_STOCKS_MANAGE_PERMISSION_CODE = (
    "inventory.stocks.manage"
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


def _get_authorized_stocks(*, user, company):

    assignments = RoleAssignment.objects.filter(
        membership__user=user,
        membership__company=company,
        membership__status=CompanyMembership.Status.ACTIVE,
        role__permission_links__permission__code=(
            INVENTORY_STOCKS_MANAGE_PERMISSION_CODE
        ),
        role__status="ACTIVE",
    ).distinct()


    if not assignments.exists():
        return InventoryStock.objects.none()


    # Permiso global de empresa
    if assignments.filter(
        branch__isnull=True,
    ).exists():

        return InventoryStock.objects.filter(
            warehouse__company=company,
        )


    # Permiso por sucursales asignadas
    branch_ids = assignments.values_list(
        "branch_id",
        flat=True,
    )


    return InventoryStock.objects.filter(
        warehouse__company=company,
        warehouse__branch_id__in=branch_ids,
    )


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def stock_list_create_view(request):

    if request.method == "POST":
        return _create_stock(request)

    return _list_stocks(request)


def _list_stocks(request):

    raw_company_id = request.query_params.get(
        "company",
    )


    if raw_company_id in (None, ""):

        return Response(
            {
                "detail": (
                    "El parametro company es obligatorio."
                ),
            },
            status=status.HTTP_400_BAD_REQUEST,
        )


    company_id = _parse_company_id(
        raw_company_id,
    )


    if company_id is None:

        return Response(
            {
                "detail": (
                    "El parametro company debe ser un entero valido."
                ),
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
                "detail": (
                    "No tienes acceso a esta empresa."
                ),
            },
            status=status.HTTP_403_FORBIDDEN,
        )


    stocks = _get_authorized_stocks(
        user=request.user,
        company=membership.company,
    )


    return Response(
        {
            "stocks": InventoryStockSerializer(
                stocks,
                many=True,
            ).data,
        }
    )


def _create_stock(request):

    raw_company_id = request.data.get(
        "company",
    )


    if raw_company_id in (None, ""):

        return Response(
            {
                "detail": (
                    "El campo company es obligatorio."
                ),
            },
            status=status.HTTP_400_BAD_REQUEST,
        )


    company_id = _parse_company_id(
        raw_company_id,
    )


    if company_id is None:

        return Response(
            {
                "detail": (
                    "El campo company debe ser un entero valido."
                ),
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
                "detail": (
                    "No tienes acceso a esta empresa."
                ),
            },
            status=status.HTTP_403_FORBIDDEN,
        )


    company = membership.company


    serializer = InventoryStockCreateSerializer(
        data=request.data,
        context={
            "company": company,
        },
    )


    serializer.is_valid(
        raise_exception=True,
    )


    warehouse = serializer.validated_data["warehouse"]


    if not has_permission(
        user=request.user,
        company=company,
        permission_code=(
            INVENTORY_STOCKS_MANAGE_PERMISSION_CODE
        ),
        branch=warehouse.branch,
    ):

        return Response(
            {
                "detail": (
                    "No tienes permiso para administrar "
                    "el inventario de esta sucursal."
                ),
            },
            status=status.HTTP_403_FORBIDDEN,
        )


    stock = serializer.save()


    return Response(
        {
            "stock": InventoryStockSerializer(
                stock,
            ).data,
        },
        status=status.HTTP_201_CREATED,
    )
