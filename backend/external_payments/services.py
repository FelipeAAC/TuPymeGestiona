import hashlib
import json
import os
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils.dateparse import parse_datetime

from orders.models import Order
from portal.models import CustomerPortalAccount
from sales.models import Sale
from sales.services import SaleIdempotencyConflictError, SaleTransitionError, create_sale, record_payment

from .models import MercadoPagoCheckout, MercadoPagoEvent, MercadoPagoRemotePayment
from .provider import MercadoPagoClient, MercadoPagoProviderError, MercadoPagoUncertainError


class MercadoPagoConflictError(Exception):
    pass


class MercadoPagoOwnershipError(Exception):
    pass


def _hash(payload):
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _account_for_order(*, user, order):
    account = CustomerPortalAccount.objects.filter(
        user=user,
        company=order.company,
        customer=order.customer,
        status=CustomerPortalAccount.Status.ACTIVE,
    ).select_related("user", "company", "customer").first()
    if account is None:
        raise MercadoPagoOwnershipError("El pedido no pertenece a tu cuenta de cliente.")
    return account


def _checkout_payload(*, checkout, client):
    order = checkout.order
    return {
        "items": [{
            "id": f"ORDER-{order.id}",
            "title": f"Pedido #{order.number} - {order.company.name}"[:256],
            "quantity": 1,
            "currency_id": "CLP",
            "unit_price": float(checkout.amount),
        }],
        "payer": {"email": checkout.portal_account.customer.email or checkout.portal_account.user.email},
        "back_urls": {
            "success": f"{client.return_base}/portal/payment-result?result=success&order={order.id}",
            "pending": f"{client.return_base}/portal/payment-result?result=pending&order={order.id}",
            "failure": f"{client.return_base}/portal/payment-result?result=failure&order={order.id}",
        },
        "notification_url": client.webhook_url,
        "auto_return": "approved",
        "external_reference": checkout.external_reference,
    }


def _serialize_preference(checkout):
    return {
        "preference_id": checkout.preference_id,
        "checkout_url": checkout.sandbox_init_point if settings.MERCADO_PAGO_USE_SANDBOX_INIT_POINT and checkout.sandbox_init_point else checkout.init_point,
        "init_point": checkout.init_point,
        "sandbox_init_point": checkout.sandbox_init_point,
    }


def checkout_summary(checkout):
    return {
        "id": checkout.id,
        "order": checkout.order_id,
        "status": checkout.status,
        "amount": format(checkout.amount, ".2f"),
        "currency": checkout.currency,
        "preference_id": checkout.preference_id,
        "checkout_url": _serialize_preference(checkout)["checkout_url"],
        "provider_status": checkout.provider_status,
        "provider_status_detail": checkout.provider_status_detail,
        "last_payment_id": checkout.last_payment_id,
        "updated_at": checkout.updated_at,
        "sale": checkout.sale_id,
    }


def list_customer_checkouts(*, user):
    return MercadoPagoCheckout.objects.filter(portal_account__user=user).select_related("order", "sale").order_by("-created_at", "-id")


def get_customer_checkout(*, user, order):
    _account_for_order(user=user, order=order)
    return MercadoPagoCheckout.objects.filter(order=order).select_related("order", "portal_account__user", "portal_account__customer", "sale").first()


def _create_event(checkout, event_type, *, payment=None, correlation_id="", metadata=None):
    MercadoPagoEvent.objects.create(
        checkout=checkout,
        event_type=event_type,
        provider_payment=payment,
        correlation_id=(correlation_id or "")[:100],
        metadata=metadata or {},
    )


def create_or_get_checkout(*, user, order, idempotency_key, client=None):
    if order.status not in (Order.Status.CONFIRMED, Order.Status.PREPARED):
        raise MercadoPagoConflictError("Solo se puede iniciar el pago de un pedido confirmado o en preparación.")
    account = _account_for_order(user=user, order=order)
    # Validar configuración antes de persistir un intento. Así, cuando el slice
    # está deshabilitado o faltan credenciales de prueba, no queda un checkout
    # huérfano en estado CREATING.
    client = client or MercadoPagoClient()
    if hasattr(order, "sale") and order.sale.paid_amount > 0:
        raise MercadoPagoConflictError("El pedido ya registra un pago interno.")
    request_data = {"order": order.id, "company": order.company_id, "amount": format(order.total, ".2f"), "currency": "CLP"}
    request_hash = _hash(request_data)

    with transaction.atomic():
        existing = MercadoPagoCheckout.objects.select_for_update().filter(order=order).first()
        if existing:
            if existing.request_hash != request_hash:
                raise MercadoPagoConflictError("Ya existe un checkout de Mercado Pago con datos distintos.")
            if existing.status == MercadoPagoCheckout.Status.UNCERTAIN:
                raise MercadoPagoConflictError("La creación anterior quedó incierta; resuélvela antes de reintentar.")
            if existing.preference_id:
                return existing, False
            if existing.status != MercadoPagoCheckout.Status.REJECTED:
                return existing, False
            # Un rechazo explícito (4xx) no creó una preferencia remota, por lo
            # que puede intentarse nuevamente después de corregir configuración.
            existing.status = MercadoPagoCheckout.Status.CREATING
            existing.idempotency_key = idempotency_key
            existing.last_error_code = ""
            existing.save(update_fields=("status", "idempotency_key", "last_error_code", "updated_at"))
            checkout = existing
        else:
            checkout = MercadoPagoCheckout.objects.create(
                order=order,
                portal_account=account,
                status=MercadoPagoCheckout.Status.CREATING,
                external_reference=f"TPG-MP-{order.company_id}-{order.id}",
                amount=order.total,
                currency="CLP",
                idempotency_key=idempotency_key,
                request_hash=request_hash,
            )
        _create_event(checkout, MercadoPagoEvent.EventType.PREFERENCE_REQUESTED)

    try:
        response = client.create_preference(_checkout_payload(checkout=checkout, client=client))
    except MercadoPagoUncertainError:
        checkout.status = MercadoPagoCheckout.Status.UNCERTAIN
        checkout.last_error_code = "PREFERENCE_UNCERTAIN"
        checkout.save(update_fields=("status", "last_error_code", "updated_at"))
        _create_event(checkout, MercadoPagoEvent.EventType.PREFERENCE_UNCERTAIN)
        raise
    except MercadoPagoProviderError as exc:
        checkout.status = MercadoPagoCheckout.Status.REJECTED
        checkout.last_error_code = exc.code
        checkout.save(update_fields=("status", "last_error_code", "updated_at"))
        raise

    checkout.preference_id = str(response.get("id") or "")
    checkout.init_point = str(response.get("init_point") or "")
    checkout.sandbox_init_point = str(response.get("sandbox_init_point") or "")
    if not checkout.preference_id or not checkout.init_point:
        checkout.status = MercadoPagoCheckout.Status.UNCERTAIN
        checkout.last_error_code = "INVALID_PREFERENCE_RESPONSE"
        checkout.save(update_fields=("status", "last_error_code", "updated_at"))
        raise MercadoPagoUncertainError("Mercado Pago no devolvió una preferencia utilizable.")
    checkout.status = MercadoPagoCheckout.Status.READY
    checkout.last_error_code = ""
    checkout.save(update_fields=("preference_id", "init_point", "sandbox_init_point", "status", "last_error_code", "updated_at"))
    _create_event(checkout, MercadoPagoEvent.EventType.PREFERENCE_READY, metadata={"preference_id": checkout.preference_id})
    return checkout, True


def resolve_uncertain_preference(*, user, order, client=None):
    checkout = get_customer_checkout(user=user, order=order)
    if checkout is None:
        raise MercadoPagoConflictError("No existe un checkout de Mercado Pago para el pedido.")
    if checkout.status != MercadoPagoCheckout.Status.UNCERTAIN:
        return checkout, False
    client = client or MercadoPagoClient()
    payload = client.search_preferences(checkout.external_reference)
    results = payload.get("elements") or payload.get("results") or []
    if not results:
        raise MercadoPagoConflictError("Mercado Pago aún no informa una preferencia para esta referencia. No se reintentó la creación.")
    pref = results[0]
    checkout.preference_id = str(pref.get("id") or "")
    checkout.init_point = str(pref.get("init_point") or "")
    checkout.sandbox_init_point = str(pref.get("sandbox_init_point") or "")
    if not checkout.preference_id or not checkout.init_point:
        raise MercadoPagoConflictError("La preferencia encontrada no contiene los datos mínimos esperados.")
    checkout.status = MercadoPagoCheckout.Status.READY
    checkout.last_error_code = ""
    checkout.save(update_fields=("preference_id", "init_point", "sandbox_init_point", "status", "last_error_code", "updated_at"))
    _create_event(checkout, MercadoPagoEvent.EventType.PREFERENCE_RESOLVED, metadata={"preference_id": checkout.preference_id})
    return checkout, True


def _map_status(status):
    normalized = (status or "").lower()
    if normalized == "approved":
        return MercadoPagoCheckout.Status.APPROVED
    if normalized in {"pending", "in_process", "authorized"}:
        return MercadoPagoCheckout.Status.PENDING
    if normalized in {"rejected"}:
        return MercadoPagoCheckout.Status.REJECTED
    if normalized in {"cancelled", "canceled"}:
        return MercadoPagoCheckout.Status.CANCELLED
    if normalized in {"refunded", "charged_back"}:
        return MercadoPagoCheckout.Status.REFUNDED
    return MercadoPagoCheckout.Status.PENDING


def _decimal(value):
    try:
        return Decimal(str(value)).quantize(Decimal("0.01"))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _verify_test_mode(payload):
    if settings.MERCADO_PAGO_ACCEPT_LIVE_MODE:
        return
    if bool(payload.get("live_mode")):
        raise MercadoPagoConflictError("Se rechazó un pago live_mode porque este slice está configurado solo para pruebas.")


def apply_payment_payload(*, payload, correlation_id=""):
    _verify_test_mode(payload)
    external_reference = str(payload.get("external_reference") or "")
    checkout = MercadoPagoCheckout.objects.filter(external_reference=external_reference).select_related(
        "order", "portal_account__user", "portal_account__customer", "sale"
    ).first()
    if checkout is None:
        return None, None, False
    provider_payment_id = str(payload.get("id") or "")
    amount = _decimal(payload.get("transaction_amount"))
    currency = str(payload.get("currency_id") or "")
    if not provider_payment_id or amount is None:
        raise MercadoPagoConflictError("El pago remoto no contiene identificador o monto válido.")
    payload_hash = _hash(payload)
    payment, _ = MercadoPagoRemotePayment.objects.update_or_create(
        provider_payment_id=provider_payment_id,
        defaults={
            "checkout": checkout,
            "status": str(payload.get("status") or "unknown")[:40],
            "status_detail": str(payload.get("status_detail") or "")[:120],
            "transaction_amount": amount,
            "currency_id": currency[:3],
            "live_mode": bool(payload.get("live_mode")),
            "payload_hash": payload_hash,
            "date_created": parse_datetime(str(payload.get("date_created") or "")) if payload.get("date_created") else None,
            "date_approved": parse_datetime(str(payload.get("date_approved") or "")) if payload.get("date_approved") else None,
        },
    )
    checkout.provider_status = payment.status
    checkout.provider_status_detail = payment.status_detail
    checkout.last_payment_id = provider_payment_id
    if amount != checkout.amount or currency != checkout.currency:
        checkout.status = MercadoPagoCheckout.Status.UNCERTAIN
        checkout.last_error_code = "PAYMENT_MISMATCH"
        checkout.save(update_fields=("provider_status", "provider_status_detail", "last_payment_id", "status", "last_error_code", "updated_at"))
        _create_event(checkout, MercadoPagoEvent.EventType.PAYMENT_MISMATCH, payment=payment, correlation_id=correlation_id, metadata={"amount": format(amount, ".2f"), "currency": currency})
        return checkout, payment, False

    checkout.status = _map_status(payment.status)
    checkout.last_error_code = ""
    checkout.save(update_fields=("provider_status", "provider_status_detail", "last_payment_id", "status", "last_error_code", "updated_at"))
    event_type = {
        MercadoPagoCheckout.Status.APPROVED: MercadoPagoEvent.EventType.PAYMENT_APPROVED,
        MercadoPagoCheckout.Status.REJECTED: MercadoPagoEvent.EventType.PAYMENT_REJECTED,
    }.get(checkout.status, MercadoPagoEvent.EventType.PAYMENT_PENDING)
    _create_event(checkout, event_type, payment=payment, correlation_id=correlation_id)
    if checkout.status == MercadoPagoCheckout.Status.APPROVED and checkout.order.status == Order.Status.DELIVERED:
        reconcile_delivered_order(order=checkout.order)
    return checkout, payment, True


def refresh_checkout_payment(*, user, order, payment_id, client=None):
    checkout = get_customer_checkout(user=user, order=order)
    if checkout is None:
        raise MercadoPagoConflictError("No existe un checkout de Mercado Pago para el pedido.")
    client = client or MercadoPagoClient()
    payload = client.get_payment(payment_id)
    remote_reference = str(payload.get("external_reference") or "")
    if remote_reference != checkout.external_reference:
        raise MercadoPagoConflictError("El pago consultado no corresponde al pedido.")
    result = apply_payment_payload(payload=payload, correlation_id=f"refresh:{payment_id}")
    _create_event(checkout, MercadoPagoEvent.EventType.PAYMENT_REFRESHED, payment=result[1], correlation_id=f"refresh:{payment_id}")
    return result[0]


def has_approved_external_payment(*, order):
    return MercadoPagoCheckout.objects.filter(order=order, status=MercadoPagoCheckout.Status.APPROVED).exists()


def has_incomplete_external_checkout(*, order):
    return MercadoPagoCheckout.objects.filter(order=order).exclude(status=MercadoPagoCheckout.Status.APPROVED).exists()


@transaction.atomic
def reconcile_delivered_order(*, order):
    checkout = MercadoPagoCheckout.objects.select_for_update().filter(order=order, status=MercadoPagoCheckout.Status.APPROVED).select_related(
        "portal_account__user", "sale", "order"
    ).first()
    if checkout is None:
        return None
    if order.status != Order.Status.DELIVERED:
        return checkout
    remote = checkout.remote_payments.filter(status="approved").order_by("-updated_at", "-id").first()
    if remote is None or remote.transaction_amount != checkout.amount or remote.currency_id != "CLP":
        return checkout
    actor = checkout.portal_account.user
    sale = Sale.objects.filter(order=order).first()
    if sale is None:
        sale, _ = create_sale(company=order.company, order=order, idempotency_key=f"mp-sale:{checkout.id}", created_by=actor)
    if sale.total_amount != checkout.amount:
        raise MercadoPagoConflictError("El total de la venta no coincide con el pago externo aprobado.")
    if sale.paid_amount == Decimal("0.00"):
        sale, payment, created = record_payment(
            sale=sale,
            amount=checkout.amount,
            reference=f"MP:{remote.provider_payment_id}",
            idempotency_key=f"mp-payment:{remote.provider_payment_id}",
            performed_by=actor,
        )
        if created:
            _create_event(checkout, MercadoPagoEvent.EventType.INTERNAL_PAYMENT_RECORDED, payment=remote, metadata={"sale": sale.id, "internal_payment": payment.id})
    elif sale.paid_amount != sale.total_amount:
        raise MercadoPagoConflictError("La venta ya tiene abonos incompatibles con el pago externo.")
    checkout.sale = sale
    checkout.save(update_fields=("sale", "updated_at"))
    return checkout
