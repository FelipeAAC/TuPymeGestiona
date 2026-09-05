from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models

from orders.models import Order
from portal.models import CustomerPortalAccount
from sales.models import Sale


class MercadoPagoCheckout(models.Model):
    class Status(models.TextChoices):
        CREATING = "CREATING", "Creando preferencia"
        READY = "READY", "Listo para pagar"
        PENDING = "PENDING", "Pago pendiente"
        APPROVED = "APPROVED", "Pago aprobado"
        REJECTED = "REJECTED", "Pago rechazado"
        CANCELLED = "CANCELLED", "Pago cancelado"
        REFUNDED = "REFUNDED", "Pago devuelto"
        UNCERTAIN = "UNCERTAIN", "Resultado incierto"

    order = models.OneToOneField(Order, on_delete=models.PROTECT, related_name="mercado_pago_checkout")
    portal_account = models.ForeignKey(CustomerPortalAccount, on_delete=models.PROTECT, related_name="mercado_pago_checkouts")
    sale = models.OneToOneField(Sale, on_delete=models.PROTECT, related_name="mercado_pago_checkout", null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.CREATING)
    external_reference = models.CharField(max_length=64, unique=True)
    amount = models.DecimalField(max_digits=28, decimal_places=2)
    currency = models.CharField(max_length=3, default="CLP")
    idempotency_key = models.CharField(max_length=100)
    request_hash = models.CharField(max_length=64)
    preference_id = models.CharField(max_length=120, blank=True, default="")
    init_point = models.URLField(max_length=1000, blank=True, default="")
    sandbox_init_point = models.URLField(max_length=1000, blank=True, default="")
    provider_status = models.CharField(max_length=40, blank=True, default="")
    provider_status_detail = models.CharField(max_length=120, blank=True, default="")
    last_payment_id = models.CharField(max_length=80, blank=True, default="")
    last_error_code = models.CharField(max_length=80, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [
            models.CheckConstraint(condition=models.Q(amount__gt=0), name="mp_checkout_amount_gt_zero"),
            models.UniqueConstraint(fields=["portal_account", "idempotency_key"], name="uniq_mp_checkout_account_key"),
        ]

    def clean(self):
        super().clean()
        errors = {}
        if self.order_id and self.portal_account_id:
            if self.order.company_id != self.portal_account.company_id:
                errors["portal_account"] = "La cuenta del portal debe pertenecer a la empresa del pedido."
            if self.order.customer_id != self.portal_account.customer_id:
                errors["portal_account"] = "La cuenta del portal debe corresponder al cliente del pedido."
        if self.sale_id and self.order_id and self.sale.order_id != self.order_id:
            errors["sale"] = "La venta debe corresponder al mismo pedido."
        if self.currency != "CLP":
            errors["currency"] = "Mercado Pago se integra en CLP para este alcance."
        if self.amount is not None and self.amount <= Decimal("0.00"):
            errors["amount"] = "El monto debe ser mayor a cero."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.idempotency_key = self.idempotency_key.strip()
        self.external_reference = self.external_reference.strip()
        self.clean()
        super().save(*args, **kwargs)


class MercadoPagoRemotePayment(models.Model):
    checkout = models.ForeignKey(MercadoPagoCheckout, on_delete=models.PROTECT, related_name="remote_payments")
    provider_payment_id = models.CharField(max_length=80, unique=True)
    status = models.CharField(max_length=40)
    status_detail = models.CharField(max_length=120, blank=True, default="")
    transaction_amount = models.DecimalField(max_digits=28, decimal_places=2)
    currency_id = models.CharField(max_length=3)
    live_mode = models.BooleanField(default=False)
    payload_hash = models.CharField(max_length=64)
    date_created = models.DateTimeField(null=True, blank=True)
    date_approved = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at", "-id"]


class MercadoPagoEvent(models.Model):
    class EventType(models.TextChoices):
        PREFERENCE_REQUESTED = "PREFERENCE_REQUESTED", "Preferencia solicitada"
        PREFERENCE_READY = "PREFERENCE_READY", "Preferencia creada"
        PREFERENCE_UNCERTAIN = "PREFERENCE_UNCERTAIN", "Preferencia incierta"
        PREFERENCE_RESOLVED = "PREFERENCE_RESOLVED", "Preferencia resuelta"
        PAYMENT_REFRESHED = "PAYMENT_REFRESHED", "Pago consultado"
        WEBHOOK_RECEIVED = "WEBHOOK_RECEIVED", "Webhook recibido"
        PAYMENT_APPROVED = "PAYMENT_APPROVED", "Pago aprobado"
        PAYMENT_REJECTED = "PAYMENT_REJECTED", "Pago rechazado"
        PAYMENT_PENDING = "PAYMENT_PENDING", "Pago pendiente"
        PAYMENT_MISMATCH = "PAYMENT_MISMATCH", "Pago inconsistente"
        INTERNAL_PAYMENT_RECORDED = "INTERNAL_PAYMENT_RECORDED", "Pago interno registrado"

    checkout = models.ForeignKey(MercadoPagoCheckout, on_delete=models.PROTECT, related_name="events")
    event_type = models.CharField(max_length=40, choices=EventType.choices)
    provider_payment = models.ForeignKey(MercadoPagoRemotePayment, on_delete=models.PROTECT, related_name="events", null=True, blank=True)
    correlation_id = models.CharField(max_length=100, blank=True, default="")
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["checkout_id", "created_at", "id"]


class MercadoPagoWebhookReceipt(models.Model):
    notification_id = models.CharField(max_length=100, unique=True)
    request_id = models.CharField(max_length=100, blank=True, default="")
    data_id = models.CharField(max_length=100)
    payload_hash = models.CharField(max_length=64)
    result = models.CharField(max_length=40, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
