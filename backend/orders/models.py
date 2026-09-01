from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from catalog.models import ProductVariant
from customers.models import Customer
from inventory.models import InventoryMovement
from organizations.models import Branch, Company, Warehouse


class OrderNumberSequence(models.Model):
    company = models.OneToOneField(
        Company,
        on_delete=models.PROTECT,
        related_name="order_number_sequence",
    )
    next_number = models.PositiveBigIntegerField(
        default=1,
    )

    class Meta:
        ordering = ["company_id"]

    def clean(self):
        super().clean()

        if self.next_number < 1:
            raise ValidationError(
                {
                    "next_number": (
                        "El siguiente numero de pedido "
                        "debe ser mayor a cero."
                    )
                }
            )

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.company} - siguiente {self.next_number}"


class Order(models.Model):
    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Borrador"
        CONFIRMED = "CONFIRMED", "Confirmado"
        PREPARED = "PREPARED", "Preparado"
        DELIVERED = "DELIVERED", "Entregado"
        CANCELLED = "CANCELLED", "Cancelado"

    company = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="orders",
    )
    branch = models.ForeignKey(
        Branch,
        on_delete=models.PROTECT,
        related_name="orders",
    )
    warehouse = models.ForeignKey(
        Warehouse,
        on_delete=models.PROTECT,
        related_name="orders",
    )
    customer = models.ForeignKey(
        Customer,
        on_delete=models.PROTECT,
        related_name="orders",
    )
    number = models.PositiveBigIntegerField()
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
    )
    notes = models.TextField(
        blank=True,
        default="",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_orders",
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
            "-number",
        ]
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "company",
                    "number",
                ],
                name="uniq_order_company_number",
            ),
            models.CheckConstraint(
                condition=models.Q(number__gt=0),
                name="order_number_greater_than_zero",
            ),
        ]

    def clean(self):
        super().clean()

        if (
            self.branch_id
            and self.company_id
            and self.branch.company_id != self.company_id
        ):
            raise ValidationError(
                {
                    "branch": (
                        "La sucursal debe pertenecer "
                        "a la empresa del pedido."
                    )
                }
            )

        if (
            self.warehouse_id
            and self.company_id
            and self.warehouse.company_id != self.company_id
        ):
            raise ValidationError(
                {
                    "warehouse": (
                        "La bodega debe pertenecer "
                        "a la empresa del pedido."
                    )
                }
            )

        if (
            self.warehouse_id
            and self.branch_id
            and self.warehouse.branch_id is not None
            and self.warehouse.branch_id != self.branch_id
        ):
            raise ValidationError(
                {
                    "warehouse": (
                        "La bodega debe pertenecer a la sucursal "
                        "del pedido o ser una bodega de empresa."
                    )
                }
            )

        if (
            self.customer_id
            and self.company_id
            and self.customer.company_id != self.company_id
        ):
            raise ValidationError(
                {
                    "customer": (
                        "El cliente debe pertenecer "
                        "a la empresa del pedido."
                    )
                }
            )

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    @property
    def total(self):
        return sum(
            (item.line_total for item in self.items.all()),
            Decimal("0.00"),
        )

    def __str__(self):
        return f"{self.company} - Pedido {self.number}"


class OrderItem(models.Model):
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="items",
    )
    variant = models.ForeignKey(
        ProductVariant,
        on_delete=models.PROTECT,
        related_name="order_items",
    )
    quantity = models.DecimalField(
        max_digits=14,
        decimal_places=3,
    )
    unit_price = models.DecimalField(
        max_digits=14,
        decimal_places=2,
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
    )
    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = [
            "order_id",
            "id",
        ]
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "order",
                    "variant",
                ],
                name="uniq_order_item_variant",
            ),
            models.CheckConstraint(
                condition=models.Q(quantity__gt=0),
                name="order_item_quantity_greater_than_zero",
            ),
            models.CheckConstraint(
                condition=models.Q(unit_price__gte=0),
                name="order_item_unit_price_not_negative",
            ),
        ]

    def clean(self):
        super().clean()

        if self.quantity is not None and self.quantity <= 0:
            raise ValidationError(
                {
                    "quantity": (
                        "La cantidad del item debe ser mayor a cero."
                    )
                }
            )

        if self.unit_price is not None and self.unit_price < 0:
            raise ValidationError(
                {
                    "unit_price": (
                        "El precio unitario no puede ser negativo."
                    )
                }
            )

        if (
            self.order_id
            and self.variant_id
            and self.variant.product.company_id
            != self.order.company_id
        ):
            raise ValidationError(
                {
                    "variant": (
                        "La variante debe pertenecer "
                        "a la empresa del pedido."
                    )
                }
            )

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    @property
    def line_total(self):
        return self.quantity * self.unit_price

    def __str__(self):
        return f"Pedido {self.order.number} - {self.variant}"


class OrderInventoryMovement(models.Model):
    class Kind(models.TextChoices):
        CONFIRMATION = "CONFIRMATION", "Confirmacion"
        CANCELLATION = "CANCELLATION", "Anulacion"

    order_item = models.ForeignKey(
        OrderItem,
        on_delete=models.PROTECT,
        related_name="stock_movements",
    )
    inventory_movement = models.OneToOneField(
        InventoryMovement,
        on_delete=models.PROTECT,
        related_name="order_stock_link",
    )
    kind = models.CharField(
        max_length=20,
        choices=Kind.choices,
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        ordering = [
            "order_item__order_id",
            "order_item_id",
            "created_at",
            "id",
        ]
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "order_item",
                    "kind",
                ],
                name="uniq_order_item_stock_movement_kind",
            ),
        ]

    def clean(self):
        super().clean()

        if not self.order_item_id or not self.inventory_movement_id:
            return

        order_item = self.order_item
        movement = self.inventory_movement

        if movement.warehouse_id != order_item.order.warehouse_id:
            raise ValidationError(
                {
                    "inventory_movement": (
                        "El movimiento debe pertenecer a la bodega "
                        "del pedido."
                    )
                }
            )

        if movement.variant_id != order_item.variant_id:
            raise ValidationError(
                {
                    "inventory_movement": (
                        "El movimiento debe corresponder a la variante "
                        "del item."
                    )
                }
            )

        if self.kind == self.Kind.CONFIRMATION:
            expected_type = InventoryMovement.MovementType.EXIT
            expected_delta = -order_item.quantity
        else:
            expected_type = InventoryMovement.MovementType.ENTRY
            expected_delta = order_item.quantity

        if movement.movement_type != expected_type:
            raise ValidationError(
                {
                    "inventory_movement": (
                        "El tipo de movimiento no corresponde "
                        "a la operacion del pedido."
                    )
                }
            )

        if movement.quantity_delta != expected_delta:
            raise ValidationError(
                {
                    "inventory_movement": (
                        "La cantidad del movimiento debe coincidir "
                        "con la cantidad del item."
                    )
                }
            )

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return (
            f"Pedido {self.order_item.order.number} - "
            f"{self.get_kind_display()}"
        )
