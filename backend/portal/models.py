from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from customers.models import Customer
from orders.models import Order
from organizations.models import Company


class CustomerPortalAccount(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Activo"
        SUSPENDED = "SUSPENDED", "Suspendido"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="portal_accounts",
    )
    company = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="portal_accounts",
    )
    customer = models.OneToOneField(
        Customer,
        on_delete=models.PROTECT,
        related_name="portal_account",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["company_id", "user_id"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "company"],
                name="uniq_portal_account_user_company",
            ),
        ]

    def clean(self):
        super().clean()
        if self.customer_id and self.company_id and self.customer.company_id != self.company_id:
            raise ValidationError({"customer": "El cliente debe pertenecer a la empresa de la cuenta."})

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)


class PortalOrderRequest(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="portal_order_requests",
    )
    company = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="portal_order_requests",
    )
    idempotency_key = models.CharField(max_length=100)
    request_hash = models.CharField(max_length=64)
    order = models.OneToOneField(
        Order,
        on_delete=models.PROTECT,
        related_name="portal_request",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "company", "idempotency_key"],
                name="uniq_portal_order_request_key",
            ),
        ]
