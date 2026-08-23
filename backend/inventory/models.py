from django.core.exceptions import ValidationError
from django.db import models

from catalog.models import ProductVariant
from organizations.models import Warehouse


class InventoryStock(models.Model):
    warehouse = models.ForeignKey(
        Warehouse,
        on_delete=models.PROTECT,
        related_name="inventory_stocks",
    )
    variant = models.ForeignKey(
        ProductVariant,
        on_delete=models.PROTECT,
        related_name="inventory_stocks",
    )
    quantity = models.DecimalField(
        max_digits=14,
        decimal_places=3,
        default=0,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )
    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = [
            "warehouse_id",
            "variant_id",
        ]
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "warehouse",
                    "variant",
                ],
                name="uniq_inventory_stock_warehouse_variant",
            ),
        ]

    def clean(self):
        super().clean()

        if (
            self.warehouse_id
            and self.variant_id
            and self.warehouse.company_id
            != self.variant.product.company_id
        ):
            raise ValidationError(
                {
                    "variant": (
                        "La variante debe pertenecer "
                        "a la misma empresa que la bodega."
                    )
                }
            )

        if self.quantity < 0:
            raise ValidationError(
                {
                    "quantity": (
                        "La cantidad de inventario "
                        "no puede ser negativa."
                    )
                }
            )

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return (
            f"{self.warehouse} - "
            f"{self.variant} - "
            f"{self.quantity}"
        )
