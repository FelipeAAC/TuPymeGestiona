from django.core.exceptions import ValidationError
from django.db import transaction

from inventory.models import InventoryMovement
from inventory.services import apply_inventory_movement

from organizations.models import Company

from .models import (
    Order,
    OrderInventoryMovement,
    OrderItem,
    OrderNumberSequence,
)


class OrderNotEditableError(Exception):
    pass


class OrderTransitionError(Exception):
    def __init__(self, detail):
        self.detail = detail
        super().__init__(detail)


def _create_items(*, order, items):
    for item in items:
        OrderItem.objects.create(
            order=order,
            variant=item["variant"],
            quantity=item["quantity"],
            unit_price=item["unit_price"],
        )


@transaction.atomic
def create_draft_order(
    *,
    company,
    branch,
    warehouse,
    customer,
    notes,
    items,
    created_by,
):
    locked_company = (
        Company.objects.select_for_update().get(
            pk=company.pk,
        )
    )

    sequence, _ = OrderNumberSequence.objects.get_or_create(
        company=locked_company,
        defaults={
            "next_number": 1,
        },
    )

    number = sequence.next_number
    sequence.next_number += 1
    sequence.save(update_fields=("next_number",))

    order = Order.objects.create(
        company=locked_company,
        branch=branch,
        warehouse=warehouse,
        customer=customer,
        number=number,
        status=Order.Status.DRAFT,
        notes=notes,
        created_by=created_by,
    )

    _create_items(
        order=order,
        items=items,
    )

    return order


@transaction.atomic
def update_draft_order(
    *,
    order,
    validated_data,
    replace_items,
):
    locked_order = (
        Order.objects.select_for_update()
        .select_related(
            "company",
            "branch",
            "warehouse",
            "customer",
        )
        .get(pk=order.pk)
    )

    if locked_order.status != Order.Status.DRAFT:
        raise OrderNotEditableError

    items = validated_data.pop("items", None)

    for field, value in validated_data.items():
        setattr(locked_order, field, value)

    locked_order.save()

    if replace_items:
        locked_order.items.all().delete()
        _create_items(
            order=locked_order,
            items=items or [],
        )

    return locked_order


def _lock_order(order):
    return (
        Order.objects.select_for_update()
        .select_related(
            "company",
            "branch",
            "warehouse",
            "customer",
        )
        .get(pk=order.pk)
    )


def _set_order_status(*, order, new_status):
    order.status = new_status
    order.save(update_fields=("status", "updated_at"))

    # Outbox transaccional: se registra dentro de la misma transacción de
    # negocio, pero el SMTP real se procesa de forma asíncrona/separada.
    from transactional_notifications.services import enqueue_order_status_notification

    enqueue_order_status_notification(order=order)


@transaction.atomic
def confirm_order(*, order, performed_by):
    locked_order = _lock_order(order)

    if locked_order.status != Order.Status.DRAFT:
        raise OrderTransitionError(
            "Solo se pueden confirmar pedidos en borrador."
        )

    items = list(
        locked_order.items.select_related(
            "variant__product",
        ).order_by(
            "variant_id",
            "id",
        )
    )

    if not items:
        raise ValidationError(
            {
                "items": (
                    "El pedido debe contener al menos un item "
                    "antes de confirmarse."
                )
            }
        )

    for item in items:
        movement, _ = apply_inventory_movement(
            warehouse=locked_order.warehouse,
            variant=item.variant,
            movement_type=InventoryMovement.MovementType.EXIT,
            quantity_delta=-item.quantity,
            created_by=performed_by,
        )

        OrderInventoryMovement.objects.create(
            order_item=item,
            inventory_movement=movement,
            kind=OrderInventoryMovement.Kind.CONFIRMATION,
        )

    _set_order_status(
        order=locked_order,
        new_status=Order.Status.CONFIRMED,
    )

    return locked_order


@transaction.atomic
def prepare_order(*, order, performed_by):
    locked_order = _lock_order(order)

    if locked_order.status != Order.Status.CONFIRMED:
        raise OrderTransitionError(
            "Solo se pueden preparar pedidos confirmados."
        )

    _set_order_status(
        order=locked_order,
        new_status=Order.Status.PREPARED,
    )

    return locked_order


@transaction.atomic
def deliver_order(*, order, performed_by):
    locked_order = _lock_order(order)

    if locked_order.status != Order.Status.PREPARED:
        raise OrderTransitionError(
            "Solo se pueden entregar pedidos preparados."
        )

    # Un checkout de Mercado Pago iniciado obliga a confirmar el pago antes
    # de entregar. Los pedidos sin checkout conservan el flujo existente.
    from external_payments.services import (
        has_incomplete_external_checkout,
        reconcile_delivered_order,
    )

    if has_incomplete_external_checkout(order=locked_order):
        raise OrderTransitionError(
            "El pedido tiene un pago Mercado Pago pendiente o no confirmado."
        )

    _set_order_status(
        order=locked_order,
        new_status=Order.Status.DELIVERED,
    )

    reconcile_delivered_order(order=locked_order)
    return locked_order


@transaction.atomic
def cancel_order(*, order, performed_by):
    locked_order = _lock_order(order)

    from external_payments.services import has_approved_external_payment

    if has_approved_external_payment(order=locked_order):
        raise OrderTransitionError(
            "El pedido tiene un pago Mercado Pago aprobado; requiere devolución antes de anular."
        )

    if locked_order.status == Order.Status.DRAFT:
        _set_order_status(
            order=locked_order,
            new_status=Order.Status.CANCELLED,
        )
        return locked_order

    if locked_order.status not in (
        Order.Status.CONFIRMED,
        Order.Status.PREPARED,
    ):
        raise OrderTransitionError(
            (
                "Solo se pueden anular pedidos en borrador, "
                "confirmados o preparados."
            )
        )

    confirmation_links = list(
        OrderInventoryMovement.objects.filter(
            order_item__order=locked_order,
            kind=OrderInventoryMovement.Kind.CONFIRMATION,
        )
        .select_related(
            "order_item__variant",
            "inventory_movement",
        )
        .order_by(
            "order_item__variant_id",
            "order_item_id",
        )
    )

    if len(confirmation_links) != locked_order.items.count():
        raise ValidationError(
            {
                "inventory": (
                    "No se puede anular el pedido porque su trazabilidad "
                    "de inventario esta incompleta."
                )
            }
        )

    for link in confirmation_links:
        quantity = -link.inventory_movement.quantity_delta

        movement, _ = apply_inventory_movement(
            warehouse=locked_order.warehouse,
            variant=link.order_item.variant,
            movement_type=InventoryMovement.MovementType.ENTRY,
            quantity_delta=quantity,
            created_by=performed_by,
        )

        OrderInventoryMovement.objects.create(
            order_item=link.order_item,
            inventory_movement=movement,
            kind=OrderInventoryMovement.Kind.CANCELLATION,
        )

    _set_order_status(
        order=locked_order,
        new_status=Order.Status.CANCELLED,
    )

    return locked_order
