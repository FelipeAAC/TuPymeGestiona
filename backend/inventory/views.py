from django.core.exceptions import ValidationError
from django.db.models import Q

from rest_framework import status
from rest_framework.decorators import (
    api_view,
    permission_classes,
)
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from inventory.models import (
    InventoryMovement,
    InventoryStock,
    InventoryTransfer,
)

from inventory.serializers import (
    InventoryMovementCreateSerializer,
    InventoryMovementSerializer,
    InventoryStockCreateSerializer,
    InventoryStockSerializer,
    InventoryTransferCreateSerializer,
    InventoryTransferSerializer,
)

from inventory.services import (
    apply_inventory_movement,
    create_inventory_transfer,
)

from organizations.authorization import has_permission

from organizations.models import (
    CompanyMembership,
    RoleAssignment,
)


INVENTORY_STOCKS_MANAGE_PERMISSION_CODE = (
    "inventory.stocks.manage"
)

INVENTORY_MOVEMENTS_MANAGE_PERMISSION_CODE = (
    "inventory.movements.manage"
)

INVENTORY_TRANSFERS_MANAGE_PERMISSION_CODE = (
    "inventory.transfers.manage"
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

    if assignments.filter(
        branch__isnull=True,
    ).exists():

        return InventoryStock.objects.filter(
            warehouse__company=company,
        )

    branch_ids = assignments.values_list(
        "branch_id",
        flat=True,
    )

    return InventoryStock.objects.filter(
        warehouse__company=company,
        warehouse__branch_id__in=branch_ids,
    )



def _get_authorized_movements(*, user, company):

    assignments = RoleAssignment.objects.filter(
        membership__user=user,
        membership__company=company,
        membership__status=CompanyMembership.Status.ACTIVE,
        role__permission_links__permission__code=(
            INVENTORY_MOVEMENTS_MANAGE_PERMISSION_CODE
        ),
        role__status="ACTIVE",
    ).distinct()

    if not assignments.exists():
        return InventoryMovement.objects.none()

    if assignments.filter(
        branch__isnull=True,
    ).exists():

        return InventoryMovement.objects.filter(
            warehouse__company=company,
        )

    branch_ids = assignments.values_list(
        "branch_id",
        flat=True,
    )

    return InventoryMovement.objects.filter(
        warehouse__company=company,
        warehouse__branch_id__in=branch_ids,
    )


def _get_authorized_transfers(*, user, company):

    assignments = RoleAssignment.objects.filter(
        membership__user=user,
        membership__company=company,
        membership__status=CompanyMembership.Status.ACTIVE,
        role__permission_links__permission__code=(
            INVENTORY_TRANSFERS_MANAGE_PERMISSION_CODE
        ),
        role__status="ACTIVE",
    ).distinct()


    if not assignments.exists():
        return InventoryTransfer.objects.none()


    if assignments.filter(
        branch__isnull=True,
    ).exists():

        return InventoryTransfer.objects.filter(
            company=company,
        )


    branch_ids = assignments.values_list(
        "branch_id",
        flat=True,
    )


    return InventoryTransfer.objects.filter(
        company=company,
    ).filter(
        Q(
            source_warehouse__branch_id__in=branch_ids
        )
        |
        Q(
            destination_warehouse__branch_id__in=branch_ids
        )
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



@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def movement_list_create_view(request):

    if request.method == "POST":
        return _create_movement(request)

    return _list_movements(request)



def _list_movements(request):

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

    movements = _get_authorized_movements(
        user=request.user,
        company=membership.company,
    )

    movements = _filter_movements(
        movements=movements,
        request=request,
    )

    return Response(
        {
            "movements": InventoryMovementSerializer(
                movements,
                many=True,
            ).data,
        }
    )


def _filter_movements(
    *,
    movements,
    request,
):

    warehouse_id = request.query_params.get(
        "warehouse",
    )

    if warehouse_id not in (None, ""):
        movements = movements.filter(
            warehouse_id=warehouse_id,
        )


    variant_id = request.query_params.get(
        "variant",
    )

    if variant_id not in (None, ""):
        movements = movements.filter(
            variant_id=variant_id,
        )


    movement_type = request.query_params.get(
        "movement_type",
    )

    if movement_type not in (None, ""):
        movements = movements.filter(
            movement_type=movement_type,
        )


    return movements


def _create_movement(request):

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

    serializer = InventoryMovementCreateSerializer(
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
            INVENTORY_MOVEMENTS_MANAGE_PERMISSION_CODE
        ),
        branch=warehouse.branch,
    ):
        return Response(
            {
                "detail": (
                    "No tienes permiso para administrar "
                    "movimientos de inventario."
                ),
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    try:
        movement, stock = apply_inventory_movement(
            warehouse=warehouse,
            variant=serializer.validated_data["variant"],
            movement_type=serializer.validated_data["movement_type"],
            quantity_delta=serializer.validated_data["quantity_delta"],
            created_by=request.user,
        )

    except ValidationError as error:

        return Response(
            {
                "detail": error.message_dict,
            },
            status=status.HTTP_400_BAD_REQUEST,
        )


    return Response(
        {
            "movement": InventoryMovementSerializer(
                movement,
            ).data,
            "stock": InventoryStockSerializer(
                stock,
            ).data,
        },
        status=status.HTTP_201_CREATED,
    )


def _create_transfer(request):

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

    serializer = InventoryTransferCreateSerializer(
        data=request.data,
        context={
            "company": company,
        },
    )

    serializer.is_valid(
        raise_exception=True,
    )

    source = serializer.validated_data[
        "source_warehouse"
    ]

    destination = serializer.validated_data[
        "destination_warehouse"
    ]

    if not has_permission(
        user=request.user,
        company=company,
        permission_code=(
            INVENTORY_TRANSFERS_MANAGE_PERMISSION_CODE
        ),
        branch=source.branch,
    ):
        return Response(
            {
                "detail": (
                    "No tienes permiso para realizar "
                    "transferencias desde esta sucursal."
                ),
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    if not has_permission(
        user=request.user,
        company=company,
        permission_code=(
            INVENTORY_TRANSFERS_MANAGE_PERMISSION_CODE
        ),
        branch=destination.branch,
    ):
        return Response(
            {
                "detail": (
                    "No tienes permiso para realizar "
                    "transferencias hacia esta sucursal."
                ),
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    try:

        transfer = create_inventory_transfer(
            company=company,
            source_warehouse=source,
            destination_warehouse=destination,
            items=serializer.validated_data["items"],
            created_by=request.user,
        )

    except ValidationError as error:

        return Response(
            {
                "detail": error.message_dict,
            },
            status=status.HTTP_400_BAD_REQUEST,
        )


    return Response(
        {
            "transfer": InventoryTransferSerializer(
                transfer,
            ).data,
        },
        status=status.HTTP_201_CREATED,
    )


def _list_transfers(request):

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

    transfers = _get_authorized_transfers(
        user=request.user,
        company=membership.company,
    )

    return Response(
        {
            "transfers": InventoryTransferSerializer(
                transfers,
                many=True,
            ).data,
        }
    )


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def transfer_list_create_view(request):

    if request.method == "POST":
        return _create_transfer(request)

    return _list_transfers(request)
