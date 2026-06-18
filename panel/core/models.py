from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models


class Customer(models.Model):
    name = models.CharField(max_length=120)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        self.name = (self.name or "").strip()
        super().save(*args, **kwargs)


class Product(models.Model):
    name = models.CharField(max_length=120)
    sku = models.CharField(max_length=40, unique=True)
    stock = models.PositiveIntegerField(default=0, validators=[MinValueValidator(0)])
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)],
    )
    category = models.CharField(max_length=50, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.sku} - {self.name}"

    def save(self, *args, **kwargs):
        self.name = (self.name or "").strip()
        self.sku = (self.sku or "").strip().upper()
        if self.price is None:
            self.price = Decimal("0.00")
        super().save(*args, **kwargs)

    @property
    def is_low_stock(self):
        return self.stock > 0 and self.stock <= 5

    @property
    def total_value(self):
        return self.price * Decimal(self.stock)


class Order(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    qty = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    order_number = models.CharField(max_length=32, blank=True, null=True)
    payment_method = models.CharField(max_length=50, blank=True, null=True)
    delivery_zone = models.CharField(max_length=100, blank=True, null=True)
    delivery_address = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    @property
    def line_total(self):
        return self.product.price * self.qty


class Message(models.Model):
    SENDER_CUSTOMER = "customer"
    SENDER_ADMIN = "admin"
    SENDER_CHOICES = [
        (SENDER_CUSTOMER, "Cliente"),
        (SENDER_ADMIN, "Admin"),
    ]

    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    text = models.TextField()
    order_number = models.CharField(max_length=32, blank=True, null=True)
    sender = models.CharField(max_length=10, choices=SENDER_CHOICES, default=SENDER_ADMIN)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"[{self.get_sender_display()}] {self.customer}: {self.text[:80]}"


class ActivityLog(models.Model):
    ORDER = "order"
    PRODUCT_ADD = "product_add"
    RESTOCK = "restock"
    OUT_OF_STOCK = "out_of_stock"
    MESSAGE = "message"

    ACTIONS = [
        (ORDER, "Venta"),
        (PRODUCT_ADD, "Alta de producto"),
        (RESTOCK, "Reposición de stock"),
        (OUT_OF_STOCK, "Producto sin stock"),
        (MESSAGE, "Mensaje a cliente"),
    ]

    action = models.CharField(max_length=30, choices=ACTIONS)
    message = models.CharField(max_length=255)
    meta = models.JSONField(blank=True, default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"[{self.get_action_display()}] {self.message}"
