from decimal import Decimal

from rest_framework import serializers

from catalog.models import ProductVariant
from customers.models import Customer
from organizations.models import Branch, Warehouse

from .models import Order, OrderInventoryMovement, OrderItem


ORDER_ORDERING_CHOICES = (
    ("-number", "Numero descendente"),
    ("number", "Numero ascendente"),
    ("-created_at", "Fecha de creacion descendente"),
    ("created_at", "Fecha de creacion ascendente"),
    ("-updated_at", "Fecha de actualizacion descendente"),
    ("updated_at", "Fecha de actualizacion ascendente"),
)


class OrderItemInputSerializer(serializers.Serializer):
    variant = serializers.PrimaryKeyRelatedField(
        queryset=ProductVariant.objects.select_related(
            "product",
        ).all(),
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
    )


class OrderInventoryMovementSerializer(serializers.ModelSerializer):
    movement_type = serializers.CharField(
        source="inventory_movement.movement_type",
        read_only=True,
    )
    quantity_delta = serializers.DecimalField(
        source="inventory_movement.quantity_delta",
        max_digits=14,
        decimal_places=3,
        read_only=True,
    )
    created_by = serializers.IntegerField(
        source="inventory_movement.created_by_id",
        read_only=True,
    )

    class Meta:
        model = OrderInventoryMovement
        fields = (
            "id",
            "kind",
            "inventory_movement",
            "movement_type",
            "quantity_delta",
            "created_by",
            "created_at",
        )
        read_only_fields = fields


class OrderItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(
        source="variant.product.name",
        read_only=True,
    )
    variant_sku = serializers.CharField(
        source="variant.sku",
        read_only=True,
    )
    line_total = serializers.DecimalField(
        max_digits=28,
        decimal_places=2,
        read_only=True,
    )
    stock_movements = OrderInventoryMovementSerializer(
        many=True,
        read_only=True,
    )

    class Meta:
        model = OrderItem
        fields = (
            "id",
            "variant",
            "variant_sku",
            "product_name",
            "quantity",
            "unit_price",
            "line_total",
            "stock_movements",
        )


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(
        many=True,
        read_only=True,
    )
    total = serializers.DecimalField(
        max_digits=28,
        decimal_places=2,
        read_only=True,
    )

    class Meta:
        model = Order
        fields = (
            "id",
            "company",
            "branch",
            "warehouse",
            "customer",
            "number",
            "status",
            "notes",
            "delivery_address",
            "delivery_commune",
            "delivery_city",
            "created_by",
            "created_at",
            "updated_at",
            "items",
            "total",
        )
        read_only_fields = fields


def _validate_order_relations(
    *,
    company,
    branch,
    warehouse,
    customer,
    items,
):
    errors = {}

    if branch.company_id != company.id:
        errors["branch"] = (
            "La sucursal debe pertenecer a la empresa."
        )

    if warehouse.company_id != company.id:
        errors["warehouse"] = (
            "La bodega debe pertenecer a la empresa."
        )
    elif (
        warehouse.branch_id is not None
        and warehouse.branch_id != branch.id
    ):
        errors["warehouse"] = (
            "La bodega debe pertenecer a la sucursal "
            "seleccionada o ser una bodega de empresa."
        )

    if customer.company_id != company.id:
        errors["customer"] = (
            "El cliente debe pertenecer a la empresa."
        )

    variant_ids = []

    for item in items:
        variant = item["variant"]
        variant_ids.append(variant.id)

        if variant.product.company_id != company.id:
            errors["items"] = (
                "Todas las variantes deben pertenecer a la empresa."
            )
            break

    if len(variant_ids) != len(set(variant_ids)):
        errors["items"] = (
            "Una variante no puede repetirse dentro del pedido."
        )

    if errors:
        raise serializers.ValidationError(errors)


class OrderCreateSerializer(serializers.Serializer):
    branch = serializers.PrimaryKeyRelatedField(
        queryset=Branch.objects.select_related("company").all(),
    )
    warehouse = serializers.PrimaryKeyRelatedField(
        queryset=Warehouse.objects.select_related(
            "company",
            "branch",
        ).all(),
    )
    customer = serializers.PrimaryKeyRelatedField(
        queryset=Customer.objects.select_related("company").all(),
    )
    notes = serializers.CharField(
        required=False,
        allow_blank=True,
        default="",
    )
    items = OrderItemInputSerializer(
        many=True,
        required=False,
        default=list,
    )

    def validate(self, attrs):
        _validate_order_relations(
            company=self.context["company"],
            branch=attrs["branch"],
            warehouse=attrs["warehouse"],
            customer=attrs["customer"],
            items=attrs["items"],
        )
        return attrs


class OrderUpdateSerializer(serializers.Serializer):
    branch = serializers.PrimaryKeyRelatedField(
        queryset=Branch.objects.select_related("company").all(),
        required=False,
    )
    warehouse = serializers.PrimaryKeyRelatedField(
        queryset=Warehouse.objects.select_related(
            "company",
            "branch",
        ).all(),
        required=False,
    )
    customer = serializers.PrimaryKeyRelatedField(
        queryset=Customer.objects.select_related("company").all(),
        required=False,
    )
    notes = serializers.CharField(
        required=False,
        allow_blank=True,
    )
    items = OrderItemInputSerializer(
        many=True,
        required=False,
    )

    def validate(self, attrs):
        order = self.instance

        _validate_order_relations(
            company=order.company,
            branch=attrs.get("branch", order.branch),
            warehouse=attrs.get("warehouse", order.warehouse),
            customer=attrs.get("customer", order.customer),
            items=attrs.get("items", []),
        )
        return attrs


class OrderListQuerySerializer(serializers.Serializer):
    status = serializers.ChoiceField(
        choices=Order.Status.choices,
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
        choices=ORDER_ORDERING_CHOICES,
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
