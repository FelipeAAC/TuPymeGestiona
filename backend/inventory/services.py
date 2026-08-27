from django.core.exceptions import ValidationError
from django.db import transaction

from .models import (
    InventoryMovement,
    InventoryStock,
    InventoryTransfer,
    InventoryTransferItem,
)


@transaction.atomic
def apply_inventory_movement(
    *,
    warehouse,
    variant,
    movement_type,
    quantity_delta,
    created_by,
):
    movement = InventoryMovement(
        warehouse=warehouse,
        variant=variant,
        movement_type=movement_type,
        quantity_delta=quantity_delta,
        created_by=created_by,
    )

    movement.full_clean()

    try:
        stock = (
            InventoryStock.objects
            .select_for_update()
            .get(
                warehouse=warehouse,
                variant=variant,
            )
        )
    except InventoryStock.DoesNotExist:
        if quantity_delta < 0:
            raise ValidationError(
                {
                    "quantity_delta": (
                        "No existe stock suficiente "
                        "para realizar este movimiento."
                    )
                }
            )

        stock = InventoryStock.objects.create(
            warehouse=warehouse,
            variant=variant,
            quantity=0,
        )

    new_quantity = stock.quantity + quantity_delta

    if new_quantity < 0:
        raise ValidationError(
            {
                "quantity_delta": (
                    "El movimiento no puede dejar "
                    "el inventario con cantidad negativa."
                )
            }
        )

    stock.quantity = new_quantity
    stock.save()

    movement.save()

    return movement, stock


@transaction.atomic
def create_inventory_transfer(
    *,
    company,
    source_warehouse,
    destination_warehouse,
    items,
    created_by,
):
    if source_warehouse == destination_warehouse:
        raise ValidationError(
            {
                "destination_warehouse": (
                    "La bodega destino debe "
                    "ser diferente a la bodega origen."
                )
            }
        )

    if (
        source_warehouse.company_id != company.id
        or destination_warehouse.company_id != company.id
    ):
        raise ValidationError(
            {
                "company": (
                    "Las bodegas deben pertenecer "
                    "a la misma empresa."
                )
            }
        )

    transfer = InventoryTransfer.objects.create(
        company=company,
        source_warehouse=source_warehouse,
        destination_warehouse=destination_warehouse,
        created_by=created_by,
    )

    for item in items:

        variant = item["variant"]
        quantity = item["quantity"]

        InventoryTransferItem.objects.create(
            transfer=transfer,
            variant=variant,
            quantity=quantity,
        )

        apply_inventory_movement(
            warehouse=source_warehouse,
            variant=variant,
            movement_type=(
                InventoryMovement.MovementType.EXIT
            ),
            quantity_delta=-quantity,
            created_by=created_by,
        )

        apply_inventory_movement(
            warehouse=destination_warehouse,
            variant=variant,
            movement_type=(
                InventoryMovement.MovementType.ENTRY
            ),
            quantity_delta=quantity,
            created_by=created_by,
        )

    return transfer
