from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from catalog.models import ProductVariant
from organizations.models import Company, Warehouse


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


class InventoryMovement(models.Model):
    class MovementType(models.TextChoices):
        ENTRY = "ENTRY", "Entrada"
        EXIT = "EXIT", "Salida"
        ADJUSTMENT = "ADJUSTMENT", "Ajuste"

    warehouse = models.ForeignKey(
        Warehouse,
        on_delete=models.PROTECT,
        related_name="inventory_movements",
    )
    variant = models.ForeignKey(
        ProductVariant,
        on_delete=models.PROTECT,
        related_name="inventory_movements",
    )
    movement_type = models.CharField(
        max_length=20,
        choices=MovementType.choices,
    )
    quantity_delta = models.DecimalField(
        max_digits=14,
        decimal_places=3,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_inventory_movements",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        ordering = [
            "-created_at",
            "-id",
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

        if self.quantity_delta is None:
            return

        if self.quantity_delta == 0:
            raise ValidationError(
                {
                    "quantity_delta": (
                        "La cantidad del movimiento "
                        "no puede ser cero."
                    )
                }
            )

        if (
            self.movement_type == self.MovementType.ENTRY
            and self.quantity_delta < 0
        ):
            raise ValidationError(
                {
                    "quantity_delta": (
                        "Una entrada de inventario "
                        "debe tener una cantidad positiva."
                    )
                }
            )

        if (
            self.movement_type == self.MovementType.EXIT
            and self.quantity_delta > 0
        ):
            raise ValidationError(
                {
                    "quantity_delta": (
                        "Una salida de inventario "
                        "debe tener una cantidad negativa."
                    )
                }
            )

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return (
            f"{self.get_movement_type_display()} - "
            f"{self.warehouse} - "
            f"{self.variant} - "
            f"{self.quantity_delta}"
        )


class InventoryTransfer(models.Model):

    class Status(models.TextChoices):
        COMPLETED = "COMPLETED", "Completada"
        CANCELLED = "CANCELLED", "Cancelada"

    company = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="inventory_transfers",
    )

    source_warehouse = models.ForeignKey(
        Warehouse,
        on_delete=models.PROTECT,
        related_name="outgoing_inventory_transfers",
    )

    destination_warehouse = models.ForeignKey(
        Warehouse,
        on_delete=models.PROTECT,
        related_name="incoming_inventory_transfers",
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_inventory_transfers",
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.COMPLETED,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    def clean(self):
        super().clean()

        if (
            self.source_warehouse_id
            and self.destination_warehouse_id
            and self.source_warehouse_id
            == self.destination_warehouse_id
        ):
            raise ValidationError(
                {
                    "destination_warehouse": (
                        "La bodega destino debe "
                        "ser diferente a la bodega origen."
                    )
                }
            )

        if (
            self.source_warehouse_id
            and self.company_id
            and self.source_warehouse.company_id
            != self.company_id
        ):
            raise ValidationError(
                {
                    "source_warehouse": (
                        "La bodega origen debe "
                        "pertenecer a la empresa."
                    )
                }
            )

        if (
            self.destination_warehouse_id
            and self.company_id
            and self.destination_warehouse.company_id
            != self.company_id
        ):
            raise ValidationError(
                {
                    "destination_warehouse": (
                        "La bodega destino debe "
                        "pertenecer a la empresa."
                    )
                }
            )

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return (
            f"Transferencia {self.id}: "
            f"{self.source_warehouse} -> "
            f"{self.destination_warehouse}"
        )


class InventoryTransferItem(models.Model):

    transfer = models.ForeignKey(
        InventoryTransfer,
        on_delete=models.CASCADE,
        related_name="items",
    )

    variant = models.ForeignKey(
        ProductVariant,
        on_delete=models.PROTECT,
        related_name="inventory_transfer_items",
    )

    quantity = models.DecimalField(
        max_digits=14,
        decimal_places=3,
    )

    def clean(self):
        super().clean()

        if self.quantity <= 0:
            raise ValidationError(
                {
                    "quantity": (
                        "La cantidad transferida "
                        "debe ser mayor a cero."
                    )
                }
            )

        if (
            self.transfer_id
            and self.variant_id
            and self.transfer.company_id
            != self.variant.product.company_id
        ):
            raise ValidationError(
                {
                    "variant": (
                        "La variante debe pertenecer "
                        "a la misma empresa."
                    )
                }
            )

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return (
            f"{self.variant} - "
            f"{self.quantity}"
        )
