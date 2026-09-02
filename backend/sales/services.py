from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from orders.models import Order
from organizations.models import Company

from .models import Payment, Sale, SaleEvent, SaleNumberSequence


class SaleTransitionError(Exception):
    def __init__(self, detail):
        self.detail = detail
        super().__init__(detail)


class SaleIdempotencyConflictError(Exception):
    def __init__(self, detail):
        self.detail = detail
        super().__init__(detail)


def _next_sale_number(*, company):
    sequence, _ = SaleNumberSequence.objects.get_or_create(
        company=company,
        defaults={"next_number": 1},
    )
    number = sequence.next_number
    sequence.next_number += 1
    sequence.save(update_fields=("next_number",))
    return number


def _lock_sale(sale):
    return (
        Sale.objects.select_for_update()
        .select_related(
            "company",
            "branch",
            "order__customer",
        )
        .get(pk=sale.pk)
    )


@transaction.atomic
def create_sale(
    *,
    company,
    order,
    idempotency_key,
    created_by,
):
    locked_company = Company.objects.select_for_update().get(pk=company.pk)
    normalized_key = idempotency_key.strip()

    existing = Sale.objects.filter(
        company=locked_company,
        idempotency_key=normalized_key,
    ).first()

    if existing is not None:
        if existing.order_id != order.id:
            raise SaleIdempotencyConflictError(
                "La clave de idempotencia ya fue usada para otra venta."
            )
        return existing, False

    locked_order = (
        Order.objects.select_for_update()
        .select_related("company", "branch", "customer")
        .get(pk=order.pk)
    )

    if locked_order.company_id != locked_company.id:
        raise ValidationError(
            {"order": "El pedido debe pertenecer a la empresa de la venta."}
        )

    if locked_order.status != Order.Status.DELIVERED:
        raise SaleTransitionError(
            "Solo se puede crear una venta desde un pedido entregado."
        )

    if Sale.objects.filter(order=locked_order).exists():
        raise SaleTransitionError(
            "El pedido entregado ya tiene una venta asociada."
        )

    total_amount = locked_order.total
    initial_status = (
        Sale.Status.PAID
        if total_amount == 0
        else Sale.Status.PENDING
    )
    sale = Sale.objects.create(
        company=locked_company,
        branch=locked_order.branch,
        order=locked_order,
        number=_next_sale_number(company=locked_company),
        status=initial_status,
        total_amount=total_amount,
        paid_amount=total_amount if total_amount == 0 else 0,
        idempotency_key=normalized_key,
        created_by=created_by,
    )
    SaleEvent.objects.create(
        sale=sale,
        event_type=SaleEvent.EventType.CREATED,
        new_status=sale.status,
        performed_by=created_by,
    )
    return sale, True


@transaction.atomic
def record_payment(
    *,
    sale,
    amount,
    reference,
    idempotency_key,
    performed_by,
):
    locked_sale = _lock_sale(sale)
    normalized_reference = reference.strip()
    normalized_key = idempotency_key.strip()

    existing = Payment.objects.filter(
        sale=locked_sale,
        idempotency_key=normalized_key,
    ).first()

    if existing is not None:
        if (
            existing.amount != amount
            or existing.reference != normalized_reference
        ):
            raise SaleIdempotencyConflictError(
                "La clave de idempotencia ya fue usada con otro pago."
            )
        return locked_sale, existing, False

    if locked_sale.status == Sale.Status.CANCELLED:
        raise SaleTransitionError(
            "No se pueden registrar pagos en una venta anulada."
        )

    if locked_sale.status == Sale.Status.PAID:
        raise SaleTransitionError(
            "La venta ya se encuentra completamente pagada."
        )

    if amount > locked_sale.balance:
        raise SaleTransitionError(
            "El pago no puede superar el saldo pendiente de la venta."
        )

    payment = Payment.objects.create(
        sale=locked_sale,
        amount=amount,
        reference=normalized_reference,
        idempotency_key=normalized_key,
        recorded_by=performed_by,
    )
    previous_status = locked_sale.status
    locked_sale.paid_amount += amount
    locked_sale.status = (
        Sale.Status.PAID
        if locked_sale.paid_amount == locked_sale.total_amount
        else Sale.Status.PARTIAL
    )
    locked_sale.save(
        update_fields=("paid_amount", "status", "updated_at"),
    )
    SaleEvent.objects.create(
        sale=locked_sale,
        event_type=SaleEvent.EventType.PAYMENT_RECORDED,
        previous_status=previous_status,
        new_status=locked_sale.status,
        payment=payment,
        amount=payment.amount,
        reference=payment.reference,
        performed_by=performed_by,
    )
    return locked_sale, payment, True


@transaction.atomic
def cancel_sale(*, sale, performed_by):
    locked_sale = _lock_sale(sale)

    if locked_sale.status == Sale.Status.CANCELLED:
        return locked_sale, False

    if locked_sale.paid_amount != 0:
        raise SaleTransitionError(
            "No se puede anular una venta que ya registra pagos."
        )

    if locked_sale.status != Sale.Status.PENDING:
        raise SaleTransitionError(
            "Solo se pueden anular ventas pendientes y sin pagos."
        )

    previous_status = locked_sale.status
    locked_sale.status = Sale.Status.CANCELLED
    locked_sale.cancelled_by = performed_by
    locked_sale.cancelled_at = timezone.now()
    locked_sale.save(
        update_fields=(
            "status",
            "cancelled_by",
            "cancelled_at",
            "updated_at",
        ),
    )
    SaleEvent.objects.create(
        sale=locked_sale,
        event_type=SaleEvent.EventType.CANCELLED,
        previous_status=previous_status,
        new_status=locked_sale.status,
        performed_by=performed_by,
    )
    return locked_sale, True
