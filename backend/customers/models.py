from django.core.exceptions import ValidationError
from django.db import models

from organizations.models import Company


class Customer(models.Model):

    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Activo"
        INACTIVE = "INACTIVE", "Inactivo"

    company = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="customers",
    )

    code = models.CharField(
        max_length=50,
    )

    name = models.CharField(
        max_length=150,
    )

    tax_id = models.CharField(
        max_length=50,
        blank=True,
    )

    email = models.EmailField(
        blank=True,
    )

    phone = models.CharField(
        max_length=50,
        blank=True,
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )


    class Meta:
        ordering = [
            "company_id",
            "name",
        ]

        constraints = [
            models.UniqueConstraint(
                fields=[
                    "company",
                    "code",
                ],
                name="uniq_customer_company_code",
            ),
        ]


    def clean(self):
        super().clean()

        if not self.name.strip():
            raise ValidationError(
                {
                    "name": (
                        "El nombre del cliente "
                        "no puede estar vacío."
                    )
                }
            )

        if not self.code.strip():
            raise ValidationError(
                {
                    "code": (
                        "El código del cliente "
                        "no puede estar vacío."
                    )
                }
            )


    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)


    def __str__(self):
        return f"{self.company} - {self.name}"
