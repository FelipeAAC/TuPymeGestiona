from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from rest_framework import serializers

from catalog.models import Brand, Category, Product, ProductVariant


def _validation_error_detail(exc):
    if hasattr(exc, "message_dict"):
        return exc.message_dict

    return {
        "detail": exc.messages,
    }


class CategorySummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = (
            "id",
            "name",
        )


class CategoryDetailSerializer(serializers.ModelSerializer):
    parent = CategorySummarySerializer(
        read_only=True,
    )

    class Meta:
        model = Category
        fields = (
            "id",
            "name",
            "parent",
        )


class CategoryCreateSerializer(serializers.Serializer):
    name = serializers.CharField(
        max_length=150,
    )
    parent = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.none(),
        required=False,
        allow_null=True,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        company = self.context.get("company")

        if company is not None:
            self.fields["parent"].queryset = Category.objects.filter(
                company=company,
            )

    def create(self, validated_data):
        company = self.context["company"]

        try:
            return Category.objects.create(
                company=company,
                **validated_data,
            )
        except DjangoValidationError as exc:
            raise serializers.ValidationError(
                _validation_error_detail(exc),
            ) from exc


class BrandSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Brand
        fields = (
            "id",
            "name",
        )


class BrandCreateSerializer(serializers.Serializer):
    name = serializers.CharField(
        max_length=150,
    )

    def create(self, validated_data):
        company = self.context["company"]

        try:
            return Brand.objects.create(
                company=company,
                **validated_data,
            )
        except DjangoValidationError as exc:
            raise serializers.ValidationError(
                _validation_error_detail(exc),
            ) from exc


class ProductVariantSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductVariant
        fields = (
            "id",
            "sku",
            "gtin",
            "base_price",
            "status",
        )


class ProductSerializer(serializers.ModelSerializer):
    category = CategorySummarySerializer(read_only=True)
    brand = BrandSummarySerializer(read_only=True)
    variants = ProductVariantSerializer(
        many=True,
        read_only=True,
    )

    class Meta:
        model = Product
        fields = (
            "id",
            "name",
            "status",
            "category",
            "brand",
            "variants",
        )


class ProductVariantCreateSerializer(serializers.Serializer):
    sku = serializers.CharField(
        max_length=100,
    )
    gtin = serializers.CharField(
        max_length=32,
        required=False,
        allow_blank=True,
        default="",
    )
    base_price = serializers.DecimalField(
        max_digits=14,
        decimal_places=2,
    )


class ProductCreateSerializer(serializers.Serializer):
    name = serializers.CharField(
        max_length=200,
    )
    category = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.none(),
    )
    brand = serializers.PrimaryKeyRelatedField(
        queryset=Brand.objects.none(),
        required=False,
        allow_null=True,
    )
    variant = ProductVariantCreateSerializer()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        company = self.context.get("company")

        if company is not None:
            self.fields["category"].queryset = Category.objects.filter(
                company=company,
            )
            self.fields["brand"].queryset = Brand.objects.filter(
                company=company,
            )

    def create(self, validated_data):
        company = self.context["company"]
        variant_data = validated_data.pop("variant")

        with transaction.atomic():
            try:
                product = Product.objects.create(
                    company=company,
                    **validated_data,
                )
            except DjangoValidationError as exc:
                raise serializers.ValidationError(
                    _validation_error_detail(exc),
                ) from exc

            try:
                ProductVariant.objects.create(
                    product=product,
                    **variant_data,
                )
            except DjangoValidationError as exc:
                raise serializers.ValidationError(
                    {
                        "variant": _validation_error_detail(exc),
                    },
                ) from exc

        return product
