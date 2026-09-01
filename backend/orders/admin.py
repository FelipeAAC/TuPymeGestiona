from django.contrib import admin

from .models import Order, OrderItem, OrderNumberSequence


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        "number",
        "company",
        "branch",
        "customer",
        "status",
        "created_at",
    )
    list_filter = (
        "status",
        "company",
        "branch",
    )
    search_fields = (
        "number",
        "customer__name",
        "customer__code",
    )
    inlines = (OrderItemInline,)


@admin.register(OrderNumberSequence)
class OrderNumberSequenceAdmin(admin.ModelAdmin):
    list_display = (
        "company",
        "next_number",
    )
