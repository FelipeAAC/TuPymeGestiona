from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from organizations.models import Company


class PaymentMethod(models.Model):
    class Kind(models.TextChoices):
        CASH = "CASH", "Efectivo"
        TRANSFER = "TRANSFER", "Transferencia"
        ONLINE = "ONLINE", "Pago en linea"
        OTHER = "OTHER", "Otro"

    company = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="payment_methods",
    )
    code = models.CharField(max_length=40)
    name = models.CharField(max_length=100)
    kind = models.CharField(max_length=20, choices=Kind.choices)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["company_id", "sort_order", "name", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "code"],
                name="uniq_admin_payment_method_company_code",
            )
        ]

    def clean(self):
        super().clean()
        self.code = self.code.strip().upper()
        self.name = " ".join(self.name.split())
        errors = {}
        if not self.code:
            errors["code"] = "El codigo del metodo de pago es obligatorio."
        if not self.name:
            errors["name"] = "El nombre del metodo de pago es obligatorio."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.company_id}:{self.code}"


class CompanySettings(models.Model):
    company = models.OneToOneField(
        Company,
        on_delete=models.PROTECT,
        related_name="general_settings",
    )
    vat_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("19.00"),
    )
    currency = models.CharField(max_length=3, default="CLP")
    timezone = models.CharField(max_length=80, default="America/Santiago")
    payment_provider = models.CharField(max_length=60, default="MERCADO_PAGO")
    payment_sandbox_enabled = models.BooleanField(default=True)
    notification_sender_email = models.EmailField(blank=True, default="")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["company_id"]

    def clean(self):
        super().clean()
        self.currency = self.currency.strip().upper()
        self.timezone = self.timezone.strip()
        self.payment_provider = self.payment_provider.strip().upper()
        self.notification_sender_email = self.notification_sender_email.strip().lower()
        errors = {}
        if self.vat_rate < 0 or self.vat_rate > 100:
            errors["vat_rate"] = "El IVA debe estar entre 0 y 100."
        if len(self.currency) != 3:
            errors["currency"] = "La moneda debe usar un codigo ISO de tres letras."
        if not self.timezone:
            errors["timezone"] = "La zona horaria es obligatoria."
        if not self.payment_provider:
            errors["payment_provider"] = "El proveedor de pagos es obligatorio."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Configuracion empresa {self.company_id}"


class OrderStatusConfiguration(models.Model):
    company = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="order_status_configurations",
    )
    code = models.CharField(max_length=30)
    display_name = models.CharField(max_length=80)
    sort_order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    is_system = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["company_id", "sort_order", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "code"],
                name="uniq_admin_order_status_company_code",
            )
        ]

    def clean(self):
        super().clean()
        self.code = self.code.strip().upper()
        self.display_name = " ".join(self.display_name.split())
        errors = {}
        if not self.code:
            errors["code"] = "El codigo del estado es obligatorio."
        if not self.display_name:
            errors["display_name"] = "El nombre visible del estado es obligatorio."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.company_id}:{self.code}"


class AdministrationEvent(models.Model):
    company = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="administration_events",
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="administration_events",
    )
    event_type = models.CharField(max_length=60)
    resource_type = models.CharField(max_length=60)
    resource_id = models.CharField(max_length=64, blank=True, default="")
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["company_id", "-created_at", "-id"]
        indexes = [
            models.Index(
                fields=["company", "-created_at"],
                name="admin_event_company_idx",
            )
        ]

    def __str__(self):
        return f"{self.company_id}:{self.event_type}:{self.resource_id}"
