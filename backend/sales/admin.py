from django.contrib import admin

from .models import Payment, Sale, SaleEvent, SaleNumberSequence


class PaymentInline(admin.TabularInline):
    model = Payment
    extra = 0
    readonly_fields = (
        "amount",
        "reference",
        "idempotency_key",
        "recorded_by",
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
        "order",
        "status",
        "total_amount",
        "paid_amount",
        "created_at",
    )
    list_filter = (
        "status",
        "company",
        "branch",
    )
    search_fields = (
        "number",
        "order__number",
        "order__customer__name",
        "order__customer__code",
    )
    inlines = (PaymentInline, SaleEventInline)


@admin.register(SaleNumberSequence)
class SaleNumberSequenceAdmin(admin.ModelAdmin):
    list_display = ("company", "next_number")
