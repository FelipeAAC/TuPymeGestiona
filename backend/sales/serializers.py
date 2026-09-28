from decimal import Decimal

from rest_framework import serializers

from administration.models import PaymentMethod
from catalog.models import ProductVariant
from customers.models import Customer
from orders.models import Order
from organizations.models import Branch, Warehouse

from .models import Payment, Sale, SaleEvent, SaleItem


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
            "payment_method",
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


class SaleItemSerializer(serializers.ModelSerializer):
    line_total = serializers.DecimalField(
        max_digits=28,
        decimal_places=2,
        read_only=True,
    )

    class Meta:
        model = SaleItem
        fields = (
            "id",
            "variant",
            "sku_snapshot",
            "product_name_snapshot",
            "quantity",
            "unit_price",
            "line_total",
            "created_at",
        )
        read_only_fields = fields


class SaleSerializer(serializers.ModelSerializer):
    order_number = serializers.IntegerField(
        source="order.number",
        read_only=True,
    )
    customer = serializers.IntegerField(
        source="customer_id",
        read_only=True,
    )
    customer_code = serializers.CharField(
        source="customer.code",
        read_only=True,
    )
    customer_name = serializers.CharField(
        source="customer.name",
        read_only=True,
    )
    balance = serializers.DecimalField(
        max_digits=28,
        decimal_places=2,
        read_only=True,
    )
    payments = PaymentSerializer(many=True, read_only=True)
    events = SaleEventSerializer(many=True, read_only=True)
    items = SaleItemSerializer(many=True, read_only=True)

    class Meta:
        model = Sale
        fields = (
            "id",
            "company",
            "branch",
            "warehouse",
            "origin",
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
            "items",
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
    payment_method = serializers.PrimaryKeyRelatedField(
        queryset=PaymentMethod.objects.all(),
        required=False,
        allow_null=True,
    )


class PosSaleItemCreateSerializer(serializers.Serializer):
    variant = serializers.PrimaryKeyRelatedField(
        queryset=ProductVariant.objects.select_related("product").all(),
    )
    quantity = serializers.DecimalField(
        max_digits=14,
        decimal_places=3,
        min_value=Decimal("0.001"),
    )
    unit_price = serializers.DecimalField(
        max_digits=14,
        decimal_places=2,
        min_value=Decimal("0.00"),
        required=False,
    )


class PosSaleCreateSerializer(serializers.Serializer):
    branch = serializers.PrimaryKeyRelatedField(
        queryset=Branch.objects.all(),
    )
    warehouse = serializers.PrimaryKeyRelatedField(
        queryset=Warehouse.objects.all(),
    )
    customer = serializers.PrimaryKeyRelatedField(
        queryset=Customer.objects.all(),
        required=False,
        allow_null=True,
    )
    items = PosSaleItemCreateSerializer(many=True, allow_empty=False)
    payment_method = serializers.PrimaryKeyRelatedField(
        queryset=PaymentMethod.objects.all(),
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

    def validate(self, attrs):
        company = self.context["company"]
        branch = attrs["branch"]
        warehouse = attrs["warehouse"]
        customer = attrs.get("customer")
        payment_method = attrs["payment_method"]
        errors = {}
        if branch.company_id != company.id:
            errors["branch"] = "La sucursal no pertenece a la empresa activa."
        if warehouse.company_id != company.id:
            errors["warehouse"] = "La bodega no pertenece a la empresa."
        elif warehouse.branch_id is not None and warehouse.branch_id != branch.id:
            errors["warehouse"] = "La bodega no pertenece a la sucursal indicada."
        if customer is not None:
            if customer.company_id != company.id:
                errors["customer"] = "El cliente no pertenece a la empresa."
        if (
            payment_method.company_id != company.id
            or payment_method.kind not in (PaymentMethod.Kind.CASH, PaymentMethod.Kind.TRANSFER)
        ):
            errors["payment_method"] = (
                "El metodo de pago debe ser efectivo o transferencia activo de la empresa."
            )
        for index, item in enumerate(attrs["items"]):
            variant = item["variant"]
            if variant.product.company_id != company.id:
                errors[f"items.{index}.variant"] = (
                    "La variante no pertenece a la empresa o no esta activa."
                )
        if errors:
            raise serializers.ValidationError(errors)
        return attrs


class PosSaleOptionsQuerySerializer(serializers.Serializer):
    branch = serializers.IntegerField(min_value=1, required=False)
    warehouse = serializers.IntegerField(min_value=1, required=False)
    search = serializers.CharField(
        max_length=150,
        required=False,
        allow_blank=True,
    )


class PosSaleReversalSerializer(serializers.Serializer):
    reference = serializers.CharField(
        max_length=150,
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
