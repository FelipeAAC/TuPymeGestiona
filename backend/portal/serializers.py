from decimal import Decimal

from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from catalog.models import ProductVariant
from organizations.models import Branch, Company


class PortalRegistrationSerializer(serializers.Serializer):
    company = serializers.PrimaryKeyRelatedField(
        queryset=Company.objects.filter(is_active=True),
        required=False,
        allow_null=True,
        default=None,
    )
    email = serializers.EmailField(max_length=254)
    password = serializers.CharField(write_only=True, min_length=8, trim_whitespace=False)
    first_name = serializers.CharField(max_length=150)
    last_name = serializers.CharField(max_length=150, required=False, allow_blank=True, default="")
    phone = serializers.CharField(max_length=50, required=False, allow_blank=True, default="")
    address = serializers.CharField(max_length=220, required=False, allow_blank=True, default="")
    commune = serializers.CharField(max_length=120, required=False, allow_blank=True, default="")
    city = serializers.CharField(max_length=120, required=False, allow_blank=True, default="")

    def validate_password(self, value):
        validate_password(value)
        return value


class PortalOrderItemInputSerializer(serializers.Serializer):
    variant = serializers.PrimaryKeyRelatedField(queryset=ProductVariant.objects.all())
    quantity = serializers.DecimalField(
        max_digits=14,
        decimal_places=3,
        min_value=Decimal("0.001"),
    )


class PortalOrderCreateSerializer(serializers.Serializer):
    company = serializers.PrimaryKeyRelatedField(queryset=Company.objects.filter(is_active=True))
    branch = serializers.PrimaryKeyRelatedField(queryset=Branch.objects.filter(is_active=True))
    delivery_address = serializers.CharField(max_length=220)
    delivery_commune = serializers.CharField(max_length=120)
    delivery_city = serializers.CharField(max_length=120)
    notes = serializers.CharField(required=False, allow_blank=True, default="", max_length=2000)
    items = PortalOrderItemInputSerializer(many=True, min_length=1)

    def validate(self, attrs):
        company = attrs["company"]
        branch = attrs["branch"]
        if branch.company_id != company.id:
            raise serializers.ValidationError({"branch": "La sucursal no pertenece a la tienda."})

        variant_ids = []
        for item in attrs["items"]:
            variant = item["variant"]
            variant_ids.append(variant.id)
            if variant.product.company_id != company.id:
                raise serializers.ValidationError({"items": "Todos los productos deben pertenecer a la tienda."})
            if variant.status != variant.Status.ACTIVE or variant.product.status != variant.product.Status.ACTIVE:
                raise serializers.ValidationError({"items": "Todos los productos deben estar activos y publicados."})

        if len(variant_ids) != len(set(variant_ids)):
            raise serializers.ValidationError({"items": "Una variante no puede repetirse en el pedido."})

        return attrs
