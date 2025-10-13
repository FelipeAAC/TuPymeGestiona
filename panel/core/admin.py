from django.contrib import admin
from .models import Customer, Product, Order, Message

@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ("id", "name")
    search_fields = ("name",)

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("id", "sku", "name", "stock", "price")
    list_editable = ("stock", "price")
    search_fields = ("sku", "name")
    list_filter = ("stock",)

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("id", "customer", "product", "qty", "created_at")
    list_filter = ("created_at",)
    search_fields = ("customer__name", "product__name")

@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ("id", "customer", "text", "created_at")
    list_filter = ("created_at",)
    search_fields = ("customer__name", "text")
