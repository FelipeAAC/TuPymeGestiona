from django.core.exceptions import ValidationError
from django.db import transaction

from .models import (
    InventoryMovement,
    InventoryStock,
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
