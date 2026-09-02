from decimal import Decimal

from rest_framework import serializers

from orders.models import Order

from .models import Payment, Sale, SaleEvent


SALE_ORDERING_CHOICES = (
    ("-number", "Numero descendente"),
    ("number", "Numero ascendente"),
    ("-created_at", "Fecha de creacion descendente"),
    ("created_at", "Fecha de creacion ascendente"),
    ("-updated_at", "Fecha de actualizacion descendente"),
    ("updated_at", "Fecha de actualizacion ascendente"),
)


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = (
            "id",
            "amount",
            "reference",
            "idempotency_key",
            "recorded_by",
            "created_at",
        )
        read_only_fields = fields


class SaleEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = SaleEvent
        fields = (
            "id",
            "event_type",
            "previous_status",
            "new_status",
            "payment",
            "amount",
            "reference",
            "performed_by",
            "created_at",
        )
        read_only_fields = fields


class SaleSerializer(serializers.ModelSerializer):
    order_number = serializers.IntegerField(
        source="order.number",
        read_only=True,
    )
    customer = serializers.IntegerField(
        source="order.customer_id",
        read_only=True,
    )
    customer_code = serializers.CharField(
        source="order.customer.code",
        read_only=True,
    )
    customer_name = serializers.CharField(
        source="order.customer.name",
        read_only=True,
    )
    balance = serializers.DecimalField(
        max_digits=28,
        decimal_places=2,
        read_only=True,
    )
    payments = PaymentSerializer(many=True, read_only=True)
    events = SaleEventSerializer(many=True, read_only=True)

    class Meta:
        model = Sale
        fields = (
            "id",
            "company",
            "branch",
            "order",
            "order_number",
            "customer",
            "customer_code",
            "customer_name",
            "number",
            "status",
            "total_amount",
            "paid_amount",
            "balance",
            "idempotency_key",
            "created_by",
            "cancelled_by",
            "created_at",
            "updated_at",
            "cancelled_at",
            "payments",
            "events",
        )
        read_only_fields = fields


class SaleCreateSerializer(serializers.Serializer):
    order = serializers.PrimaryKeyRelatedField(
        queryset=Order.objects.select_related(
            "company",
            "branch",
            "customer",
        ).all(),
    )
    idempotency_key = serializers.CharField(
        max_length=100,
        allow_blank=False,
        trim_whitespace=True,
    )

    def validate_order(self, order):
        if order.company_id != self.context["company"].id:
            raise serializers.ValidationError(
                "El pedido debe pertenecer a la empresa de la venta."
            )
        return order


class PaymentCreateSerializer(serializers.Serializer):
    amount = serializers.DecimalField(
        max_digits=28,
        decimal_places=2,
        min_value=Decimal("0.01"),
    )
    reference = serializers.CharField(
        max_length=150,
        allow_blank=False,
        trim_whitespace=True,
    )
    idempotency_key = serializers.CharField(
        max_length=100,
        allow_blank=False,
        trim_whitespace=True,
    )


class SaleListQuerySerializer(serializers.Serializer):
    status = serializers.ChoiceField(
        choices=Sale.Status.choices,
        required=False,
    )
    branch = serializers.IntegerField(
        min_value=1,
        required=False,
    )
    customer = serializers.IntegerField(
        min_value=1,
        required=False,
    )
    search = serializers.CharField(
        max_length=150,
        required=False,
        allow_blank=True,
    )
    ordering = serializers.ChoiceField(
        choices=SALE_ORDERING_CHOICES,
        required=False,
        default="-number",
    )
    page = serializers.IntegerField(
        min_value=1,
        required=False,
        default=1,
    )
    page_size = serializers.IntegerField(
        min_value=1,
        max_value=100,
        required=False,
        default=20,
    )
