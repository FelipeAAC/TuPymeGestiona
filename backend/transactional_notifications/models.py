from django.db import models

from organizations.models import Company
from orders.models import Order


class TransactionalNotification(models.Model):
    class Kind(models.TextChoices):
        ORDER_CONFIRMED = "ORDER_CONFIRMED", "Pedido confirmado"
        ORDER_PREPARED = "ORDER_PREPARED", "Pedido preparado"
        ORDER_DELIVERED = "ORDER_DELIVERED", "Pedido entregado"
        ORDER_CANCELLED = "ORDER_CANCELLED", "Pedido cancelado"
        PAYMENT_APPROVED = "PAYMENT_APPROVED", "Pago aprobado"
        PAYMENT_PENDING = "PAYMENT_PENDING", "Pago pendiente"
        PAYMENT_REJECTED = "PAYMENT_REJECTED", "Pago rechazado"
        PAYMENT_CANCELLED = "PAYMENT_CANCELLED", "Pago cancelado"
        PAYMENT_REFUNDED = "PAYMENT_REFUNDED", "Pago devuelto"

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pendiente"
        SENDING = "SENDING", "Enviando"
        RETRY = "RETRY", "Reintento"
        SENT = "SENT", "Enviado"
        FAILED = "FAILED", "Fallido"
        UNCERTAIN = "UNCERTAIN", "Resultado incierto"

    company = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="transactional_notifications",
    )
    order = models.ForeignKey(
        Order,
        on_delete=models.PROTECT,
        related_name="transactional_notifications",
        null=True,
        blank=True,
    )
    checkout = models.ForeignKey(
        "external_payments.MercadoPagoCheckout",
        on_delete=models.PROTECT,
        related_name="transactional_notifications",
        null=True,
        blank=True,
    )
    kind = models.CharField(max_length=40, choices=Kind.choices)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    recipient_email = models.EmailField()
    sender_email = models.EmailField()
    subject = models.CharField(max_length=255)
    template_name = models.CharField(max_length=80)
    payload = models.JSONField(default=dict)
    idempotency_key = models.CharField(max_length=180)
    attempts = models.PositiveSmallIntegerField(default=0)
    next_attempt_at = models.DateTimeField(null=True, blank=True)
    sending_started_at = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    provider_message_id = models.CharField(max_length=255, blank=True, default="")
    last_error_code = models.CharField(max_length=80, blank=True, default="")
    last_error_message = models.CharField(max_length=500, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["company_id", "-created_at", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "idempotency_key"],
                name="uniq_tx_notification_company_key",
            ),
        ]
        indexes = [
            models.Index(
                fields=["status", "next_attempt_at", "created_at"],
                name="tx_notif_pending_idx",
            ),
            models.Index(
                fields=["company", "-created_at"],
                name="tx_notif_company_idx",
            ),
        ]


class TransactionalNotificationAttempt(models.Model):
    class Outcome(models.TextChoices):
        SENT = "SENT", "Enviado"
        RETRY = "RETRY", "Reintento"
        FAILED = "FAILED", "Fallido"
        UNCERTAIN = "UNCERTAIN", "Incierto"

    notification = models.ForeignKey(
        TransactionalNotification,
        on_delete=models.PROTECT,
        related_name="attempt_log",
    )
    attempt_number = models.PositiveSmallIntegerField()
    outcome = models.CharField(max_length=20, choices=Outcome.choices)
    error_code = models.CharField(max_length=80, blank=True, default="")
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["notification_id", "attempt_number", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["notification", "attempt_number"],
                name="uniq_tx_notification_attempt_number",
            ),
        ]
