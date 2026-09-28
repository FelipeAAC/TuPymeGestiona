from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from administration.models import PaymentMethod
from catalog.models import Product, ProductVariant
from customers.models import Customer
from inventory.models import InventoryMovement, InventoryStock
from orders.models import Order
from organizations.models import Branch, Company, Warehouse

from .models import (
    Payment,
    Sale,
    SaleEvent,
    SaleInventoryMovement,
    SaleItem,
    SaleNumberSequence,
    SaleReversal,
)


_CENT = Decimal("0.01")
_THOUSANDTH = Decimal("0.001")
_POS_PAYMENT_KINDS = {
    PaymentMethod.Kind.CASH,
    PaymentMethod.Kind.TRANSFER,
}
_CONSUMER_FINAL_CODE = "CONSUMIDOR_FINAL"


class SaleTransitionError(Exception):
    def __init__(self, detail):
        self.detail = detail
        super().__init__(detail)


class SaleIdempotencyConflictError(Exception):
    def __init__(self, detail):
        self.detail = detail
        super().__init__(detail)


def _primary_key(value):
    return getattr(value, "pk", value)


def _normalize_text(value, *, field, max_length=None):
    normalized = str(value or "").strip()
    if not normalized:
        raise ValidationError({field: f"{field} no puede estar vacio."})
    if max_length and len(normalized) > max_length:
        raise ValidationError(
            {field: f"{field} no puede superar {max_length} caracteres."}
        )
    return normalized


def _money(value, *, field="amount"):
    try:
        amount = Decimal(str(value)).quantize(_CENT)
    except (InvalidOperation, TypeError, ValueError):
        raise ValidationError({field: "El monto debe ser un numero valido."})
    if not amount.is_finite():
        raise ValidationError({field: "El monto debe ser finito."})
    return amount


def _quantity(value, *, field="quantity"):
    try:
        quantity = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ValidationError({field: "La cantidad debe ser un numero valido."})
    if not quantity.is_finite() or quantity <= 0:
        raise ValidationError({field: "La cantidad debe ser mayor a cero."})
    if quantity.quantize(_THOUSANDTH) != quantity:
        raise ValidationError(
            {field: "La cantidad no puede tener mas de tres decimales."}
        )
    return quantity


def _load_company(company):
    company_id = _primary_key(company)
    try:
        locked_company = Company.objects.select_for_update().get(pk=company_id)
    except (Company.DoesNotExist, TypeError, ValueError):
        raise ValidationError({"company": "La empresa no existe."})
    if not locked_company.is_active:
        raise ValidationError({"company": "La empresa no esta activa."})
    return locked_company


def _load_branch(*, branch, company):
    try:
        resolved = Branch.objects.get(pk=_primary_key(branch))
    except (Branch.DoesNotExist, TypeError, ValueError):
        raise ValidationError({"branch": "La sucursal no existe."})
    if resolved.company_id != company.id or not resolved.is_active:
        raise ValidationError(
            {"branch": "La sucursal no pertenece a la empresa activa."}
        )
    return resolved


def _load_warehouse(*, warehouse, company, branch):
    try:
        resolved = Warehouse.objects.get(pk=_primary_key(warehouse))
    except (Warehouse.DoesNotExist, TypeError, ValueError):
        raise ValidationError({"warehouse": "La bodega no existe."})
    if resolved.company_id != company.id:
        raise ValidationError(
            {"warehouse": "La bodega no pertenece a la empresa."}
        )
    if resolved.branch_id is not None and resolved.branch_id != branch.id:
        raise ValidationError(
            {"warehouse": "La bodega no pertenece a la sucursal indicada."}
        )
    return resolved


def _get_consumer_final(*, company):
    customer, _ = Customer.objects.get_or_create(
        company=company,
        code=_CONSUMER_FINAL_CODE,
        defaults={
            "name": "Consumidor final",
            "status": Customer.Status.ACTIVE,
        },
    )
    if customer.status != Customer.Status.ACTIVE:
        raise ValidationError(
            {"customer": "El consumidor final de la empresa no esta activo."}
        )
    return customer


def _load_customer(*, customer, company):
    if customer is None:
        return _get_consumer_final(company=company)
    try:
        resolved = Customer.objects.get(pk=_primary_key(customer))
    except (Customer.DoesNotExist, TypeError, ValueError):
        raise ValidationError({"customer": "El cliente no existe."})
    if resolved.company_id != company.id:
        raise ValidationError(
            {"customer": "El cliente no pertenece a la empresa."}
        )
    if resolved.status != Customer.Status.ACTIVE:
        raise ValidationError({"customer": "El cliente no esta activo."})
    return resolved


def _load_payment_method(*, payment_method, company, pos=False):
    if payment_method is None:
        if pos:
            raise ValidationError(
                {"payment_method": "El metodo de pago es obligatorio."}
            )
        return None
    try:
        resolved = PaymentMethod.objects.get(pk=_primary_key(payment_method))
    except (PaymentMethod.DoesNotExist, TypeError, ValueError):
        raise ValidationError({"payment_method": "El metodo de pago no existe."})
    if resolved.company_id != company.id:
        raise ValidationError(
            {"payment_method": "El metodo de pago no pertenece a la empresa."}
        )
    if not resolved.is_active:
        raise ValidationError(
            {"payment_method": "El metodo de pago no esta activo."}
        )
    if pos and resolved.kind not in _POS_PAYMENT_KINDS:
        raise ValidationError(
            {"payment_method": "El POS solo admite efectivo o transferencia."}
        )
    return resolved


def _normalize_pos_items(*, items, company):
    if not items:
        raise ValidationError({"items": "La venta POS debe tener lineas."})

    raw_items = []
    variant_ids = []
    seen = set()
    for index, raw_item in enumerate(items):
        if not isinstance(raw_item, dict):
            raise ValidationError({"items": f"La linea {index + 1} no es valida."})
        variant_id = _primary_key(raw_item.get("variant"))
        try:
            variant_id = int(variant_id)
        except (TypeError, ValueError):
            raise ValidationError(
                {"items": f"La linea {index + 1} no tiene una variante valida."}
            )
        if variant_id in seen:
            raise ValidationError(
                {"items": "Una variante no puede repetirse en la venta."}
            )
        seen.add(variant_id)
        raw_items.append((variant_id, raw_item, index))
        variant_ids.append(variant_id)

    variants = {
        variant.id: variant
        for variant in ProductVariant.objects.select_for_update()
        .select_related("product")
        .filter(
            id__in=variant_ids,
            product__company=company,
            product__status=Product.Status.ACTIVE,
            status=ProductVariant.Status.ACTIVE,
        )
    }
    if len(variants) != len(variant_ids):
        raise ValidationError(
            {"items": "Una o mas variantes no pertenecen a la empresa o no estan activas."}
        )

    normalized = []
    for variant_id, raw_item, index in raw_items:
        quantity = _quantity(
            raw_item.get("quantity"),
            field=f"items[{index}].quantity",
        )
        expected_price = _money(
            variants[variant_id].base_price,
            field=f"items[{index}].unit_price",
        )
        supplied_price = raw_item.get("unit_price")
        if supplied_price is not None and _money(
            supplied_price,
            field=f"items[{index}].unit_price",
        ) != expected_price:
            raise ValidationError(
                {
                    f"items[{index}].unit_price": (
                        "El precio debe coincidir con el precio vigente del producto."
                    )
                }
            )
        normalized.append(
            {
                "variant": variants[variant_id],
                "quantity": quantity,
                "unit_price": expected_price,
                "line_total": (quantity * expected_price).quantize(_CENT),
            }
        )
    normalized.sort(key=lambda item: item["variant"].id)
    return normalized


def _lock_sale_stocks(*, warehouse, items):
    variant_ids = [item["variant"].id for item in items]
    stocks = {
        stock.variant_id: stock
        for stock in InventoryStock.objects.select_for_update()
        .filter(warehouse=warehouse, variant_id__in=variant_ids)
        .order_by("variant_id")
    }
    if len(stocks) != len(variant_ids):
        raise ValidationError(
            {"items": "No existe stock registrado para una o mas variantes."}
        )
    for item in items:
        stock = stocks[item["variant"].id]
        if stock.quantity < item["quantity"]:
            raise ValidationError(
                {
                    "items": (
                        f"Stock insuficiente para el SKU {item['variant'].sku}."
                    )
                }
            )
    return stocks


def _pos_request_matches(
    *,
    sale,
    payment,
    branch,
    warehouse,
    customer,
    payment_method,
    items,
    reference,
):
    if (
        sale.origin != Sale.Origin.POS
        or sale.branch_id != branch.id
        or sale.warehouse_id != warehouse.id
        or sale.customer_id != customer.id
        or payment is None
        or payment.reference != reference
        or payment.amount != sale.total_amount
        or payment.payment_method_id != payment_method.id
    ):
        return False
    existing_items = list(
        sale.items.order_by("variant_id", "id").values(
            "variant_id", "quantity", "unit_price"
        )
    )
    expected_items = [
        {
            "variant_id": item["variant"].id,
            "quantity": item["quantity"],
            "unit_price": item["unit_price"],
        }
        for item in items
    ]
    return existing_items == expected_items


def _pos_replay_request_matches(
    *, sale, payment, branch, warehouse, customer, payment_method, items, reference
):
    """Compare a retry with immutable sale snapshots, without current catalog state."""
    try:
        branch_id = int(_primary_key(branch))
        warehouse_id = int(_primary_key(warehouse))
        payment_method_id = int(_primary_key(payment_method))
    except (TypeError, ValueError):
        return False
    if sale.origin != Sale.Origin.POS or sale.branch_id != branch_id or sale.warehouse_id != warehouse_id:
        return False
    if customer is None:
        if not sale.customer_id or getattr(sale.customer, "code", None) != _CONSUMER_FINAL_CODE:
            return False
    elif sale.customer_id != _primary_key(customer):
        return False
    if payment is None or payment.reference != reference or payment.amount != sale.total_amount:
        return False
    if payment.payment_method_id != payment_method_id:
        return False
    expected = []
    for raw in items:
        if not isinstance(raw, dict):
            return False
        try:
            variant_id = int(_primary_key(raw.get("variant")))
            quantity = _quantity(raw.get("quantity"))
        except (TypeError, ValueError, ValidationError):
            return False
        supplied_price = raw.get("unit_price")
        try:
            unit_price = _money(supplied_price) if supplied_price is not None else None
        except ValidationError:
            return False
        expected.append((variant_id, quantity, unit_price))
    expected.sort(key=lambda item: item[0])
    existing = list(
        sale.items.order_by("variant_id", "id").values("variant_id", "quantity", "unit_price")
    )
    if len(existing) != len(expected):
        return False
    return all(
        row["variant_id"] == variant_id
        and row["quantity"] == quantity
        and (unit_price is None or row["unit_price"] == unit_price)
        for row, (variant_id, quantity, unit_price) in zip(existing, expected)
    )


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
            "warehouse",
            "customer",
            "order__customer",
            "order__warehouse",
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
        .select_related("company", "branch", "customer", "warehouse")
        .prefetch_related("items__variant__product")
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
        warehouse=locked_order.warehouse,
        customer=locked_order.customer,
        order=locked_order,
        origin=Sale.Origin.ORDER,
        number=_next_sale_number(company=locked_company),
        status=initial_status,
        total_amount=total_amount,
        paid_amount=total_amount if total_amount == 0 else 0,
        idempotency_key=normalized_key,
        created_by=created_by,
    )
    for order_item in locked_order.items.all():
        SaleItem.objects.create(
            sale=sale,
            variant=order_item.variant,
            sku_snapshot=order_item.variant.sku,
            product_name_snapshot=order_item.variant.product.name,
            quantity=order_item.quantity,
            unit_price=order_item.unit_price,
        )
    SaleEvent.objects.create(
        sale=sale,
        event_type=SaleEvent.EventType.CREATED,
        new_status=sale.status,
        performed_by=created_by,
    )
    return sale, True


@transaction.atomic
def create_pos_sale(
    *,
    company,
    branch,
    warehouse,
    customer=None,
    items,
    payment_method,
    reference,
    idempotency_key,
    created_by,
):
    locked_company = _load_company(company)
    normalized_key = _normalize_text(
        idempotency_key,
        field="idempotency_key",
        max_length=100,
    )
    normalized_reference = _normalize_text(
        reference,
        field="reference",
        max_length=150,
    )
    existing = (
        Sale.objects.select_for_update()
        .select_related("customer")
        .filter(company=locked_company, idempotency_key=normalized_key)
        .first()
    )
    if existing is not None:
        existing_payment = existing.payments.order_by("id").first()
        if not _pos_replay_request_matches(
            sale=existing,
            payment=existing_payment,
            branch=branch,
            warehouse=warehouse,
            customer=customer,
            payment_method=payment_method,
            items=items,
            reference=normalized_reference,
        ):
            raise SaleIdempotencyConflictError(
                "La clave de idempotencia ya fue usada con otra venta POS."
            )
        return existing, existing_payment, False
    resolved_branch = _load_branch(branch=branch, company=locked_company)
    resolved_warehouse = _load_warehouse(
        warehouse=warehouse,
        company=locked_company,
        branch=resolved_branch,
    )
    resolved_customer = _load_customer(
        customer=customer,
        company=locked_company,
    )
    resolved_payment_method = _load_payment_method(
        payment_method=payment_method,
        company=locked_company,
        pos=True,
    )
    normalized_items = _normalize_pos_items(
        items=items,
        company=locked_company,
    )
    total_amount = sum(
        (item["line_total"] for item in normalized_items),
        Decimal("0.00"),
    ).quantize(_CENT)
    if total_amount <= 0:
        raise ValidationError(
            {"items": "El total de la venta debe ser mayor a cero."}
        )

    stocks = _lock_sale_stocks(
        warehouse=resolved_warehouse,
        items=normalized_items,
    )
    sale = Sale.objects.create(
        company=locked_company,
        branch=resolved_branch,
        warehouse=resolved_warehouse,
        customer=resolved_customer,
        order=None,
        origin=Sale.Origin.POS,
        number=_next_sale_number(company=locked_company),
        status=Sale.Status.PAID,
        total_amount=total_amount,
        paid_amount=total_amount,
        idempotency_key=normalized_key,
        created_by=created_by,
    )

    for item in normalized_items:
        sale_item = SaleItem.objects.create(
            sale=sale,
            variant=item["variant"],
            sku_snapshot=item["variant"].sku,
            product_name_snapshot=item["variant"].product.name,
            quantity=item["quantity"],
            unit_price=item["unit_price"],
        )
        stock = stocks[item["variant"].id]
        stock.quantity -= item["quantity"]
        stock.save(update_fields=("quantity", "updated_at"))
        movement = InventoryMovement.objects.create(
            warehouse=resolved_warehouse,
            variant=item["variant"],
            movement_type=InventoryMovement.MovementType.EXIT,
            quantity_delta=-item["quantity"],
            created_by=created_by,
        )
        SaleInventoryMovement.objects.create(
            sale_item=sale_item,
            inventory_movement=movement,
            kind=SaleInventoryMovement.Kind.SALE,
        )

    payment = Payment.objects.create(
        sale=sale,
        amount=total_amount,
        reference=normalized_reference,
        idempotency_key=normalized_key,
        payment_method=resolved_payment_method,
        recorded_by=created_by,
    )
    SaleEvent.objects.create(
        sale=sale,
        event_type=SaleEvent.EventType.CREATED,
        new_status=sale.status,
        performed_by=created_by,
    )
    SaleEvent.objects.create(
        sale=sale,
        event_type=SaleEvent.EventType.PAYMENT_RECORDED,
        previous_status=sale.status,
        new_status=sale.status,
        payment=payment,
        amount=payment.amount,
        reference=payment.reference,
        performed_by=created_by,
    )
    return sale, payment, True


@transaction.atomic
def record_payment(
    *,
    sale,
    amount,
    reference,
    idempotency_key,
    performed_by,
    payment_method=None,
):
    locked_sale = _lock_sale(sale)
    amount = _money(amount)
    normalized_reference = reference.strip()
    normalized_key = idempotency_key.strip()
    resolved_payment_method = _load_payment_method(
        payment_method=payment_method,
        company=locked_sale.company,
    )

    existing = Payment.objects.filter(
        sale=locked_sale,
        idempotency_key=normalized_key,
    ).first()

    if existing is not None:
        if (
            existing.amount != amount
            or existing.reference != normalized_reference
            or existing.payment_method_id
            != getattr(resolved_payment_method, "id", None)
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
        payment_method=resolved_payment_method,
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


@transaction.atomic
def reverse_pos_sale(*, sale, reference, performed_by):
    normalized_reference = _normalize_text(
        reference,
        field="reference",
        max_length=150,
    )
    locked_sale = (
        Sale.objects.select_for_update()
        .select_related("company", "branch", "warehouse", "customer")
        .get(pk=sale.pk)
    )
    existing = SaleReversal.objects.filter(sale=locked_sale).first()
    if existing is not None:
        if existing.reference != normalized_reference:
            raise SaleIdempotencyConflictError(
                "La venta POS ya fue revertida con otra referencia."
            )
        return locked_sale, existing, False

    if locked_sale.origin != Sale.Origin.POS:
        raise SaleTransitionError(
            "Solo se pueden revertir ventas originadas en el POS."
        )
    if locked_sale.status == Sale.Status.CANCELLED:
        raise SaleTransitionError("La venta ya se encuentra anulada.")
    if locked_sale.status != Sale.Status.PAID:
        raise SaleTransitionError(
            "Solo se pueden revertir ventas POS completamente pagadas."
        )
    if locked_sale.paid_amount != locked_sale.total_amount:
        raise SaleTransitionError(
            "La venta POS no tiene un pago completo para revertir."
        )

    sale_items = list(
        SaleItem.objects.filter(sale=locked_sale)
        .select_related("variant")
        .order_by("variant_id", "id")
    )
    if not sale_items:
        raise ValidationError({"sale": "La venta POS no tiene lineas para revertir."})

    links = list(
        SaleInventoryMovement.objects.filter(
            sale_item__sale=locked_sale,
            kind=SaleInventoryMovement.Kind.SALE,
        )
        .select_related("sale_item", "inventory_movement")
        .order_by("sale_item__variant_id", "id")
    )
    links_by_item = {link.sale_item_id: link for link in links}
    if len(links_by_item) != len(sale_items):
        raise ValidationError(
            {"sale": "La trazabilidad de inventario de la venta esta incompleta."}
        )

    variant_ids = [item.variant_id for item in sale_items]
    stocks = {
        stock.variant_id: stock
        for stock in InventoryStock.objects.select_for_update()
        .filter(warehouse=locked_sale.warehouse, variant_id__in=variant_ids)
        .order_by("variant_id")
    }
    if len(stocks) != len(variant_ids):
        raise ValidationError(
            {"sale": "No existe stock para completar la reposicion."}
        )

    for sale_item in sale_items:
        link = links_by_item[sale_item.id]
        movement = link.inventory_movement
        expected_delta = -sale_item.quantity
        if (
            movement.variant_id != sale_item.variant_id
            or movement.warehouse_id != locked_sale.warehouse_id
            or movement.quantity_delta != expected_delta
        ):
            raise ValidationError(
                {"sale": "El movimiento de inventario no coincide con la linea."}
            )

    for sale_item in sale_items:
        stock = stocks[sale_item.variant_id]
        stock.quantity += sale_item.quantity
        stock.save(update_fields=("quantity", "updated_at"))
        movement = InventoryMovement.objects.create(
            warehouse=locked_sale.warehouse,
            variant=sale_item.variant,
            movement_type=InventoryMovement.MovementType.ENTRY,
            quantity_delta=sale_item.quantity,
            created_by=performed_by,
        )
        SaleInventoryMovement.objects.create(
            sale_item=sale_item,
            inventory_movement=movement,
            kind=SaleInventoryMovement.Kind.REVERSAL,
        )

    reversal = SaleReversal.objects.create(
        sale=locked_sale,
        amount=locked_sale.total_amount,
        reference=normalized_reference,
        performed_by=performed_by,
    )
    previous_status = locked_sale.status
    locked_sale.status = Sale.Status.CANCELLED
    locked_sale.paid_amount = Decimal("0.00")
    locked_sale.cancelled_by = performed_by
    locked_sale.cancelled_at = timezone.now()
    locked_sale.save(
        update_fields=(
            "status",
            "paid_amount",
            "cancelled_by",
            "cancelled_at",
            "updated_at",
        )
    )
    SaleEvent.objects.create(
        sale=locked_sale,
        event_type=SaleEvent.EventType.CANCELLED,
        previous_status=previous_status,
        new_status=locked_sale.status,
        amount=reversal.amount,
        reference=reversal.reference,
        performed_by=performed_by,
    )
    return locked_sale, reversal, True
