from django.db import models

class Customer(models.Model):
    name = models.CharField(max_length=120)
    def __str__(self): return self.name

class Product(models.Model):
    name  = models.CharField(max_length=120)
    sku   = models.CharField(max_length=40, unique=True)
    stock = models.PositiveIntegerField(default=0)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    def __str__(self): return f"{self.sku} - {self.name}"

class Order(models.Model):
    customer   = models.ForeignKey(Customer, on_delete=models.CASCADE)
    product    = models.ForeignKey(Product, on_delete=models.CASCADE)
    qty        = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

class Message(models.Model):
    customer   = models.ForeignKey(Customer, on_delete=models.CASCADE)
    text       = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

class ActivityLog(models.Model):
    ORDER       = "order"
    PRODUCT_ADD = "product_add"
    RESTOCK     = "restock"
    OUT_OF_STOCK= "out_of_stock"
    MESSAGE     = "message"

    ACTIONS = [
        (ORDER, "Venta"),
        (PRODUCT_ADD, "Alta de producto"),
        (RESTOCK, "Reposición de stock"),
        (OUT_OF_STOCK, "Producto sin stock"),
        (MESSAGE, "Mensaje a cliente"),
    ]

    action     = models.CharField(max_length=30, choices=ACTIONS)
    message    = models.CharField(max_length=255)
    meta       = models.JSONField(blank=True, default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
