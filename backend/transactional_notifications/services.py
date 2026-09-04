import os
from datetime import timedelta

from django.conf import settings
from django.core.mail import EmailMultiAlternatives, get_connection
from django.db import models, transaction
from django.template.loader import render_to_string
from django.utils import timezone

from administration.models import CompanySettings
from external_payments.models import MercadoPagoCheckout
from orders.models import Order

from .models import TransactionalNotification, TransactionalNotificationAttempt


ORDER_KIND_BY_STATUS = {
    Order.Status.CONFIRMED: TransactionalNotification.Kind.ORDER_CONFIRMED,
    Order.Status.PREPARED: TransactionalNotification.Kind.ORDER_PREPARED,
    Order.Status.DELIVERED: TransactionalNotification.Kind.ORDER_DELIVERED,
    Order.Status.CANCELLED: TransactionalNotification.Kind.ORDER_CANCELLED,
}

PAYMENT_KIND_BY_STATUS = {
    MercadoPagoCheckout.Status.APPROVED: TransactionalNotification.Kind.PAYMENT_APPROVED,
    MercadoPagoCheckout.Status.PENDING: TransactionalNotification.Kind.PAYMENT_PENDING,
    MercadoPagoCheckout.Status.REJECTED: TransactionalNotification.Kind.PAYMENT_REJECTED,
    MercadoPagoCheckout.Status.CANCELLED: TransactionalNotification.Kind.PAYMENT_CANCELLED,
    MercadoPagoCheckout.Status.REFUNDED: TransactionalNotification.Kind.PAYMENT_REFUNDED,
}

ORDER_LABELS = dict(Order.Status.choices)
PAYMENT_LABELS = dict(MercadoPagoCheckout.Status.choices)


class TransactionalEmailConfigurationError(Exception):
    pass


def _sender_for_company(company):
    configured = (
        CompanySettings.objects.filter(company=company)
        .values_list("notification_sender_email", flat=True)
        .first()
        or ""
    ).strip().lower()
    return configured or settings.TRANSACTIONAL_EMAIL_FROM


def _recipient_for_order(order):
    return (order.customer.email or "").strip().lower()


def _order_payload(order):
    return {
        "company_name": order.company.name,
        "order_id": order.id,
        "order_number": order.number,
        "customer_name": order.customer.name,
        "status": order.status,
        "status_label": ORDER_LABELS.get(order.status, order.status),
        "total": format(order.total, ".2f"),
        "currency": "CLP",
        "delivery_address": order.delivery_address,
        "delivery_commune": order.delivery_commune,
        "delivery_city": order.delivery_city,
    }


def _payment_payload(checkout, payment):
    return {
        "company_name": checkout.order.company.name,
        "order_id": checkout.order_id,
        "order_number": checkout.order.number,
        "customer_name": checkout.portal_account.customer.name,
        "payment_status": checkout.status,
        "payment_status_label": PAYMENT_LABELS.get(checkout.status, checkout.status),
        "provider_status": payment.status if payment else checkout.provider_status,
        "provider_status_detail": payment.status_detail if payment else checkout.provider_status_detail,
        "provider_payment_id": payment.provider_payment_id if payment else checkout.last_payment_id,
        "amount": format(checkout.amount, ".2f"),
        "currency": checkout.currency,
    }


def _create_idempotent(**kwargs):
    company = kwargs.pop("company")
    idempotency_key = kwargs.pop("idempotency_key")
    notification, created = TransactionalNotification.objects.get_or_create(
        company=company,
        idempotency_key=idempotency_key,
        defaults=kwargs,
    )
    return notification, created


def enqueue_order_status_notification(*, order):
    kind = ORDER_KIND_BY_STATUS.get(order.status)
    recipient = _recipient_for_order(order)
    if kind is None or not recipient:
        return None, False
    label = ORDER_LABELS.get(order.status, order.status)
    return _create_idempotent(
        company=order.company,
        order=order,
        kind=kind,
        recipient_email=recipient,
        sender_email=_sender_for_company(order.company),
        subject=f"Pedido #{order.number}: {label}",
        template_name="order_status_v1",
        payload=_order_payload(order),
        idempotency_key=f"order-status:{order.id}:{order.status}",
    )


def enqueue_payment_status_notification(*, checkout, payment=None):
    kind = PAYMENT_KIND_BY_STATUS.get(checkout.status)
    recipient = (checkout.portal_account.customer.email or checkout.portal_account.user.email or "").strip().lower()
    if kind is None or not recipient:
        return None, False
    provider_payment_id = payment.provider_payment_id if payment else checkout.last_payment_id or "none"
    return _create_idempotent(
        company=checkout.order.company,
        order=checkout.order,
        checkout=checkout,
        kind=kind,
        recipient_email=recipient,
        sender_email=_sender_for_company(checkout.order.company),
        subject=f"Pago del pedido #{checkout.order.number}: {PAYMENT_LABELS.get(checkout.status, checkout.status)}",
        template_name="payment_status_v1",
        payload=_payment_payload(checkout, payment),
        idempotency_key=f"payment-status:{checkout.id}:{provider_payment_id}:{checkout.status}",
    )


def _connection():
    backend = settings.TRANSACTIONAL_EMAIL_BACKEND
    kwargs = {"timeout": settings.TRANSACTIONAL_EMAIL_TIMEOUT}
    if backend == "django.core.mail.backends.smtp.EmailBackend":
        username = os.getenv(settings.TRANSACTIONAL_EMAIL_USERNAME_ENV, "")
        password = os.getenv(settings.TRANSACTIONAL_EMAIL_PASSWORD_ENV, "")
        kwargs.update(
            host=settings.TRANSACTIONAL_EMAIL_HOST,
            port=settings.TRANSACTIONAL_EMAIL_PORT,
            username=username or None,
            password=password or None,
            use_tls=settings.TRANSACTIONAL_EMAIL_USE_TLS,
            use_ssl=settings.TRANSACTIONAL_EMAIL_USE_SSL,
        )
    return get_connection(backend=backend, **kwargs)


def send_notification(notification, *, connection=None):
    context = {"notification": notification, **notification.payload}
    text_body = render_to_string(
        f"transactional_notifications/{notification.template_name}.txt",
        context,
    )
    html_body = render_to_string(
        f"transactional_notifications/{notification.template_name}.html",
        context,
    )
    message = EmailMultiAlternatives(
        subject=notification.subject,
        body=text_body,
        from_email=notification.sender_email,
        to=[notification.recipient_email],
        connection=connection or _connection(),
    )
    message.attach_alternative(html_body, "text/html")
    sent = message.send(fail_silently=False)
    if sent != 1:
        raise OSError("El backend de correo no confirmó el envío.")
    return getattr(message, "extra_headers", {}).get("Message-ID", "")


def _retry_delay(attempts):
    base = max(1, settings.TRANSACTIONAL_EMAIL_RETRY_MINUTES)
    return timedelta(minutes=min(base * (2 ** max(0, attempts - 1)), 24 * 60))


def process_one_notification(notification_id, *, sender=None, now=None):
    now = now or timezone.now()
    with transaction.atomic():
        notification = TransactionalNotification.objects.select_for_update().get(pk=notification_id)
        if notification.status not in {
            TransactionalNotification.Status.PENDING,
            TransactionalNotification.Status.RETRY,
        }:
            return notification, False
        if notification.next_attempt_at and notification.next_attempt_at > now:
            return notification, False
        notification.status = TransactionalNotification.Status.SENDING
        notification.attempts += 1
        notification.sending_started_at = now
        notification.save(update_fields=("status", "attempts", "sending_started_at", "updated_at"))
        attempt_number = notification.attempts

    send_callable = sender or send_notification
    try:
        provider_message_id = send_callable(notification) or ""
    except (TimeoutError, ConnectionError, OSError) as exc:
        with transaction.atomic():
            notification = TransactionalNotification.objects.select_for_update().get(pk=notification_id)
            if attempt_number >= settings.TRANSACTIONAL_EMAIL_MAX_ATTEMPTS:
                notification.status = TransactionalNotification.Status.FAILED
                outcome = TransactionalNotificationAttempt.Outcome.FAILED
                notification.next_attempt_at = None
            else:
                notification.status = TransactionalNotification.Status.RETRY
                outcome = TransactionalNotificationAttempt.Outcome.RETRY
                notification.next_attempt_at = now + _retry_delay(attempt_number)
            notification.last_error_code = exc.__class__.__name__[:80]
            notification.last_error_message = str(exc)[:500]
            notification.sending_started_at = None
            notification.save(update_fields=(
                "status", "next_attempt_at", "last_error_code",
                "last_error_message", "sending_started_at", "updated_at",
            ))
            TransactionalNotificationAttempt.objects.create(
                notification=notification,
                attempt_number=attempt_number,
                outcome=outcome,
                error_code=notification.last_error_code,
            )
        return notification, False
    except Exception as exc:
        with transaction.atomic():
            notification = TransactionalNotification.objects.select_for_update().get(pk=notification_id)
            notification.status = TransactionalNotification.Status.FAILED
            notification.last_error_code = exc.__class__.__name__[:80]
            notification.last_error_message = str(exc)[:500]
            notification.next_attempt_at = None
            notification.sending_started_at = None
            notification.save(update_fields=(
                "status", "last_error_code", "last_error_message",
                "next_attempt_at", "sending_started_at", "updated_at",
            ))
            TransactionalNotificationAttempt.objects.create(
                notification=notification,
                attempt_number=attempt_number,
                outcome=TransactionalNotificationAttempt.Outcome.FAILED,
                error_code=notification.last_error_code,
            )
        return notification, False

    with transaction.atomic():
        notification = TransactionalNotification.objects.select_for_update().get(pk=notification_id)
        notification.status = TransactionalNotification.Status.SENT
        notification.sent_at = timezone.now()
        notification.provider_message_id = str(provider_message_id)[:255]
        notification.last_error_code = ""
        notification.last_error_message = ""
        notification.next_attempt_at = None
        notification.sending_started_at = None
        notification.save(update_fields=(
            "status", "sent_at", "provider_message_id", "last_error_code",
            "last_error_message", "next_attempt_at", "sending_started_at", "updated_at",
        ))
        TransactionalNotificationAttempt.objects.create(
            notification=notification,
            attempt_number=attempt_number,
            outcome=TransactionalNotificationAttempt.Outcome.SENT,
        )
    return notification, True


def process_pending_notifications(*, limit=100, sender=None, now=None):
    if not settings.TRANSACTIONAL_EMAIL_ENABLED and sender is None:
        raise TransactionalEmailConfigurationError(
            "TRANSACTIONAL_EMAIL_ENABLED=false; no se enviaron correos reales."
        )
    now = now or timezone.now()
    ids = list(
        TransactionalNotification.objects.filter(
            status__in=[TransactionalNotification.Status.PENDING, TransactionalNotification.Status.RETRY]
        )
        .filter(models.Q(next_attempt_at__isnull=True) | models.Q(next_attempt_at__lte=now))
        .order_by("created_at", "id")
        .values_list("id", flat=True)[:limit]
    )
    results = []
    for notification_id in ids:
        results.append(process_one_notification(notification_id, sender=sender, now=now))
    return results


def mark_stale_sending_uncertain(*, now=None):
    now = now or timezone.now()
    cutoff = now - timedelta(minutes=settings.TRANSACTIONAL_EMAIL_SENDING_STALE_MINUTES)
    stale_ids = list(
        TransactionalNotification.objects.filter(
            status=TransactionalNotification.Status.SENDING,
            sending_started_at__lte=cutoff,
        ).values_list("id", flat=True)
    )
    count = 0
    for notification_id in stale_ids:
        with transaction.atomic():
            notification = TransactionalNotification.objects.select_for_update().get(pk=notification_id)
            if notification.status != TransactionalNotification.Status.SENDING or not notification.sending_started_at or notification.sending_started_at > cutoff:
                continue
            notification.status = TransactionalNotification.Status.UNCERTAIN
            notification.last_error_code = "SEND_RESULT_UNCERTAIN"
            notification.last_error_message = "El proceso terminó sin confirmar si el servidor SMTP recibió el mensaje. No se reenvía automáticamente."
            notification.sending_started_at = None
            notification.save(update_fields=("status", "last_error_code", "last_error_message", "sending_started_at", "updated_at"))
            TransactionalNotificationAttempt.objects.create(
                notification=notification,
                attempt_number=notification.attempts,
                outcome=TransactionalNotificationAttempt.Outcome.UNCERTAIN,
                error_code="SEND_RESULT_UNCERTAIN",
            )
            count += 1
    return count


def preflight_errors():
    errors = []
    if not settings.TRANSACTIONAL_EMAIL_ENABLED:
        errors.append("TRANSACTIONAL_EMAIL_ENABLED debe ser true para envío real.")
    if not settings.TRANSACTIONAL_EMAIL_FROM:
        errors.append("TRANSACTIONAL_EMAIL_FROM es obligatorio.")
    if settings.TRANSACTIONAL_EMAIL_BACKEND == "django.core.mail.backends.smtp.EmailBackend":
        if not settings.TRANSACTIONAL_EMAIL_HOST:
            errors.append("TRANSACTIONAL_EMAIL_HOST es obligatorio para SMTP.")
        if settings.TRANSACTIONAL_EMAIL_USE_TLS and settings.TRANSACTIONAL_EMAIL_USE_SSL:
            errors.append("TLS y SSL no pueden habilitarse al mismo tiempo.")
        if settings.TRANSACTIONAL_EMAIL_REQUIRE_AUTH:
            if not os.getenv(settings.TRANSACTIONAL_EMAIL_USERNAME_ENV, ""):
                errors.append(f"Falta la variable secreta {settings.TRANSACTIONAL_EMAIL_USERNAME_ENV}.")
            if not os.getenv(settings.TRANSACTIONAL_EMAIL_PASSWORD_ENV, ""):
                errors.append(f"Falta la variable secreta {settings.TRANSACTIONAL_EMAIL_PASSWORD_ENV}.")
    return errors
