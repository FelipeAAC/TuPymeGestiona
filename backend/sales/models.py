from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from administration.models import PaymentMethod
from catalog.models import ProductVariant
from customers.models import Customer
from inventory.models import InventoryMovement
from orders.models import Order
from organizations.models import Branch, Company, Warehouse


class SaleNumberSequence(models.Model):
    company = models.OneToOneField(
        Company,
        on_delete=models.PROTECT,
        related_name="sale_number_sequence",
    )
    next_number = models.PositiveBigIntegerField(default=1)

    class Meta:
        ordering = ["company_id"]

    def clean(self):
        super().clean()

        if self.next_number < 1:
            raise ValidationError(
                {
                    "next_number": (
                        "El siguiente numero de venta debe ser mayor a cero."
                    )
                }
            )

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.company} - siguiente {self.next_number}"


class Sale(models.Model):
    class Origin(models.TextChoices):
        ORDER = "ORDER", "Pedido"
        POS = "POS", "Venta directa"

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pendiente"
        PARTIAL = "PARTIAL", "Parcial"
        PAID = "PAID", "Pagado"
        CANCELLED = "CANCELLED", "Anulado"

    company = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="sales",
    )
    branch = models.ForeignKey(
        Branch,
        on_delete=models.PROTECT,
        related_name="sales",
    )
    warehouse = models.ForeignKey(
        Warehouse,
        on_delete=models.PROTECT,
        related_name="sales",
        null=True,
        blank=True,
    )
    customer = models.ForeignKey(
        Customer,
        on_delete=models.PROTECT,
        related_name="sales",
        null=True,
        blank=True,
    )
    order = models.OneToOneField(
        Order,
        on_delete=models.PROTECT,
        related_name="sale",
        null=True,
        blank=True,
    )
    origin = models.CharField(
        max_length=10,
        choices=Origin.choices,
        default=Origin.ORDER,
    )
    number = models.PositiveBigIntegerField()
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    total_amount = models.DecimalField(
        max_digits=28,
        decimal_places=2,
    )
    paid_amount = models.DecimalField(
        max_digits=28,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    idempotency_key = models.CharField(max_length=100)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_sales",
    )
    cancelled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="cancelled_sales",
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    cancelled_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ["company_id", "-number"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "number"],
                name="uniq_sale_company_number",
            ),
            models.UniqueConstraint(
                fields=["company", "idempotency_key"],
                name="uniq_sale_company_idempotency_key",
            ),
            models.CheckConstraint(
                condition=models.Q(number__gt=0),
                name="sale_number_greater_than_zero",
            ),
            models.CheckConstraint(
                condition=models.Q(total_amount__gte=0),
                name="sale_total_amount_not_negative",
            ),
            models.CheckConstraint(
                condition=models.Q(paid_amount__gte=0),
                name="sale_paid_amount_not_negative",
            ),
            models.CheckConstraint(
                condition=models.Q(paid_amount__lte=models.F("total_amount")),
                name="sale_paid_amount_not_over_total",
            ),
        ]
        indexes = [
            models.Index(
                fields=["company", "origin", "-created_at"],
                name="sale_co_origin_created_idx",
            ),
            models.Index(
                fields=["company", "branch", "-number"],
                name="sale_co_branch_number_idx",
            ),
        ]

    def clean(self):
        super().clean()
        errors = {}

        if (
            self.branch_id
            and self.company_id
            and self.branch.company_id != self.company_id
        ):
            errors["branch"] = (
                "La sucursal debe pertenecer a la empresa de la venta."
            )

        if (
            self.warehouse_id
            and self.company_id
            and self.warehouse.company_id != self.company_id
        ):
            errors["warehouse"] = (
                "La bodega debe pertenecer a la empresa de la venta."
            )

        if (
            self.warehouse_id
            and self.branch_id
            and self.warehouse.branch_id is not None
            and self.warehouse.branch_id != self.branch_id
        ):
            errors["warehouse"] = (
                "La bodega debe pertenecer a la sucursal de la venta "
                "o ser una bodega de empresa."
            )

        if (
            self.customer_id
            and self.company_id
            and self.customer.company_id != self.company_id
        ):
            errors["customer"] = (
                "El cliente debe pertenecer a la empresa de la venta."
            )

        if self.order_id and self.company_id:
            if self.order.company_id != self.company_id:
                errors["order"] = (
                    "El pedido debe pertenecer a la empresa de la venta."
                )
            elif self.branch_id and self.order.branch_id != self.branch_id:
                errors["order"] = (
                    "El pedido debe pertenecer a la sucursal de la venta."
                )
            elif self.order.status != Order.Status.DELIVERED:
                errors["order"] = (
                    "La venta solo puede asociarse a un pedido entregado."
                )

            if self.warehouse_id and self.order.warehouse_id != self.warehouse_id:
                errors["warehouse"] = (
                    "La bodega debe coincidir con la del pedido de la venta."
                )
            if self.customer_id and self.order.customer_id != self.customer_id:
                errors["customer"] = (
                    "El cliente debe coincidir con el del pedido de la venta."
                )

        if self.origin == self.Origin.ORDER and self.order_id is None:
            errors["order"] = "Una venta de pedido debe tener un pedido asociado."
        if self.origin == self.Origin.POS and self.order_id is not None:
            errors["order"] = "Una venta POS no puede tener un pedido asociado."

        if not self.idempotency_key.strip():
            errors["idempotency_key"] = (
                "La clave de idempotencia no puede estar vacia."
            )

        if self.total_amount is not None and self.total_amount < 0:
            errors["total_amount"] = (
                "El total de la venta no puede ser negativo."
            )

        if self.paid_amount is not None and self.paid_amount < 0:
            errors["paid_amount"] = (
                "El monto pagado no puede ser negativo."
            )

        if (
            self.total_amount is not None
            and self.paid_amount is not None
            and self.paid_amount > self.total_amount
        ):
            errors["paid_amount"] = (
                "El monto pagado no puede superar el total de la venta."
            )

        if self.total_amount is not None and self.paid_amount is not None:
            if self.status == self.Status.PENDING and (
                self.paid_amount != 0 or self.total_amount == 0
            ):
                errors["status"] = (
                    "Una venta pendiente debe tener saldo pagado cero."
                )
            elif self.status == self.Status.PARTIAL and not (
                Decimal("0.00") < self.paid_amount < self.total_amount
            ):
                errors["status"] = (
                    "Una venta parcial debe tener un abono menor al total."
                )
            elif (
                self.status == self.Status.PAID
                and self.paid_amount != self.total_amount
            ):
                errors["status"] = (
                    "Una venta pagada debe tener el total completamente pagado."
                )
            elif (
                self.status == self.Status.CANCELLED
                and self.paid_amount != 0
            ):
                errors["status"] = (
                    "Una venta con abonos no puede quedar anulada."
                )

        if self.status == self.Status.CANCELLED:
            if self.cancelled_by_id is None or self.cancelled_at is None:
                errors["status"] = (
                    "Una venta anulada debe registrar autor y fecha."
                )
        elif self.cancelled_by_id is not None or self.cancelled_at is not None:
            errors["status"] = (
                "Solo una venta anulada puede registrar datos de anulacion."
            )

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.idempotency_key = self.idempotency_key.strip()
        self.clean()
        super().save(*args, **kwargs)

    @property
    def balance(self):
        if self.status == self.Status.CANCELLED:
            return Decimal("0.00")
        return self.total_amount - self.paid_amount

    def __str__(self):
        return f"{self.company} - Venta {self.number}"


class SaleItem(models.Model):
    sale = models.ForeignKey(
        Sale,
        on_delete=models.PROTECT,
        related_name="items",
    )
    variant = models.ForeignKey(
        ProductVariant,
        on_delete=models.PROTECT,
        related_name="sale_items",
    )
    sku_snapshot = models.CharField(max_length=100)
    product_name_snapshot = models.CharField(max_length=200)
    quantity = models.DecimalField(max_digits=14, decimal_places=3)
    unit_price = models.DecimalField(max_digits=14, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["sale_id", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["sale", "variant"],
                name="uniq_sale_item_variant",
            ),
            models.CheckConstraint(
                condition=models.Q(quantity__gt=0),
                name="sale_item_quantity_greater_than_zero",
            ),
            models.CheckConstraint(
                condition=models.Q(unit_price__gte=0),
                name="sale_item_unit_price_not_negative",
            ),
        ]

    def clean(self):
        super().clean()
        errors = {}
        if self.sale_id and self.variant_id:
            if self.variant.product.company_id != self.sale.company_id:
                errors["variant"] = (
                    "La variante debe pertenecer a la empresa de la venta."
                )
        if not self.sku_snapshot.strip():
            errors["sku_snapshot"] = "El SKU capturado no puede estar vacio."
        if not self.product_name_snapshot.strip():
            errors["product_name_snapshot"] = (
                "El nombre capturado no puede estar vacio."
            )
        if self.quantity is not None and self.quantity <= 0:
            errors["quantity"] = "La cantidad debe ser mayor a cero."
        if self.unit_price is not None and self.unit_price < 0:
            errors["unit_price"] = "El precio unitario no puede ser negativo."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.sku_snapshot = self.sku_snapshot.strip()
        self.product_name_snapshot = self.product_name_snapshot.strip()
        self.full_clean()
        super().save(*args, **kwargs)

    @property
    def line_total(self):
        return self.quantity * self.unit_price

    def __str__(self):
        return f"Venta {self.sale.number} - {self.sku_snapshot}"


class SaleInventoryMovement(models.Model):
    class Kind(models.TextChoices):
        SALE = "SALE", "Salida por venta"
        REVERSAL = "REVERSAL", "Reposicion por anulacion"

    sale_item = models.ForeignKey(
        SaleItem,
        on_delete=models.PROTECT,
        related_name="stock_movements",
    )
    inventory_movement = models.OneToOneField(
        InventoryMovement,
        on_delete=models.PROTECT,
        related_name="sale_stock_link",
    )
    kind = models.CharField(max_length=20, choices=Kind.choices)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["sale_item_id", "kind", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["sale_item", "kind"],
                name="uniq_sale_item_stock_movement_kind",
            ),
        ]

    def clean(self):
        super().clean()
        if not self.sale_item_id or not self.inventory_movement_id:
            return
        if self.inventory_movement.variant_id != self.sale_item.variant_id:
            raise ValidationError(
                {"inventory_movement": "El movimiento debe corresponder a la variante de la linea."}
            )
        sale = self.sale_item.sale
        if sale.warehouse_id and self.inventory_movement.warehouse_id != sale.warehouse_id:
            raise ValidationError(
                {"inventory_movement": "El movimiento debe pertenecer a la bodega de la venta."}
            )
        if self.kind == self.Kind.SALE and self.inventory_movement.quantity_delta >= 0:
            raise ValidationError(
                {"inventory_movement": "La salida de venta debe disminuir el stock."}
            )
        if self.kind == self.Kind.REVERSAL and self.inventory_movement.quantity_delta <= 0:
            raise ValidationError(
                {"inventory_movement": "La reposicion debe aumentar el stock."}
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class SaleReversal(models.Model):
    sale = models.OneToOneField(
        Sale,
        on_delete=models.PROTECT,
        related_name="reversal",
    )
    amount = models.DecimalField(max_digits=28, decimal_places=2)
    reference = models.CharField(max_length=150)
    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="sale_reversals",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["sale_id"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount__gt=0),
                name="sale_reversal_amount_greater_than_zero",
            ),
        ]

    def clean(self):
        super().clean()
        errors = {}
        if self.amount is not None and self.amount <= 0:
            errors["amount"] = "El monto de la reversión debe ser mayor a cero."
        if not self.reference.strip():
            errors["reference"] = "La referencia de reversión no puede estar vacia."
        if self.sale_id and self.amount is not None and self.amount > self.sale.total_amount:
            errors["amount"] = "La reversión no puede superar el total de la venta."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.reference = self.reference.strip()
        self.full_clean()
        super().save(*args, **kwargs)


class Payment(models.Model):
    sale = models.ForeignKey(
        Sale,
        on_delete=models.PROTECT,
        related_name="payments",
    )
    amount = models.DecimalField(
        max_digits=28,
        decimal_places=2,
    )
    reference = models.CharField(max_length=150)
    idempotency_key = models.CharField(max_length=100)
    payment_method = models.ForeignKey(
        PaymentMethod,
        on_delete=models.PROTECT,
        related_name="sales_payments",
        null=True,
        blank=True,
    )
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="recorded_sales_payments",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["sale_id", "created_at", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["sale", "idempotency_key"],
                name="uniq_payment_sale_idempotency_key",
            ),
            models.CheckConstraint(
                condition=models.Q(amount__gt=0),
                name="payment_amount_greater_than_zero",
            ),
        ]

    def clean(self):
        super().clean()
        errors = {}

        if self.amount is not None and self.amount <= 0:
            errors["amount"] = "El monto del pago debe ser mayor a cero."

        if not self.reference.strip():
            errors["reference"] = (
                "La referencia del pago no puede estar vacia."
            )

        if not self.idempotency_key.strip():
            errors["idempotency_key"] = (
                "La clave de idempotencia no puede estar vacia."
            )

        if (
            self.payment_method_id
            and self.sale_id
            and self.payment_method.company_id != self.sale.company_id
        ):
            errors["payment_method"] = (
                "El metodo de pago debe pertenecer a la empresa de la venta."
            )

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.reference = self.reference.strip()
        self.idempotency_key = self.idempotency_key.strip()
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.sale} - {self.amount}"


class SaleEvent(models.Model):
    class EventType(models.TextChoices):
        CREATED = "CREATED", "Venta creada"
        PAYMENT_RECORDED = "PAYMENT_RECORDED", "Pago registrado"
        CANCELLED = "CANCELLED", "Venta anulada"

    sale = models.ForeignKey(
        Sale,
        on_delete=models.PROTECT,
        related_name="events",
    )
    event_type = models.CharField(
        max_length=30,
        choices=EventType.choices,
    )
    previous_status = models.CharField(
        max_length=20,
        choices=Sale.Status.choices,
        blank=True,
        default="",
    )
    new_status = models.CharField(
        max_length=20,
        choices=Sale.Status.choices,
    )
    payment = models.OneToOneField(
        Payment,
        on_delete=models.PROTECT,
        related_name="audit_event",
        null=True,
        blank=True,
    )
    amount = models.DecimalField(
        max_digits=28,
        decimal_places=2,
        null=True,
        blank=True,
    )
    reference = models.CharField(
        max_length=150,
        blank=True,
        default="",
    )
    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="sales_events",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["sale_id", "created_at", "id"]

    def clean(self):
        super().clean()

        if (
            self.payment_id
            and self.sale_id
            and self.payment.sale_id != self.sale_id
        ):
            raise ValidationError(
                {
                    "payment": (
                        "El pago debe pertenecer a la venta del evento."
                    )
                }
            )

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.sale} - {self.get_event_type_display()}"
