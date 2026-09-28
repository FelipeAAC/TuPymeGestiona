from django.contrib import admin

from .models import (
    Payment,
    Sale,
    SaleEvent,
    SaleItem,
    SaleNumberSequence,
    SaleReversal,
)


class PaymentInline(admin.TabularInline):
    model = Payment
    extra = 0
    readonly_fields = (
        "amount",
        "reference",
        "idempotency_key",
        "payment_method",
        "recorded_by",
        "created_at",
    )
    can_delete = False


class SaleItemInline(admin.TabularInline):
    model = SaleItem
    extra = 0
    readonly_fields = (
        "variant",
        "sku_snapshot",
        "product_name_snapshot",
        "quantity",
        "unit_price",
        "created_at",
    )
    can_delete = False


class SaleReversalInline(admin.TabularInline):
    model = SaleReversal
    extra = 0
    readonly_fields = (
        "amount",
        "reference",
        "performed_by",
        "created_at",
    )
    can_delete = False


class SaleEventInline(admin.TabularInline):
    model = SaleEvent
    extra = 0
    readonly_fields = (
        "event_type",
        "previous_status",
        "new_status",
        "payment",
        "amount",
        "reference",
        "performed_by",
        "created_at",
    )
    can_delete = False


@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = (
        "number",
        "company",
        "branch",
        "origin",
        "order",
        "customer",
        "warehouse",
        "status",
        "total_amount",
        "paid_amount",
        "created_at",
    )
    list_filter = (
        "status",
        "origin",
        "company",
        "branch",
    )
    search_fields = (
        "number",
        "order__number",
        "order__customer__name",
        "order__customer__code",
        "customer__name",
        "customer__code",
        "warehouse__code",
    )
    inlines = (
        SaleItemInline,
        PaymentInline,
        SaleEventInline,
        SaleReversalInline,
    )


@admin.register(SaleNumberSequence)
class SaleNumberSequenceAdmin(admin.ModelAdmin):
    list_display = ("company", "next_number")
