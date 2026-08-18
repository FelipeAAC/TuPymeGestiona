from rest_framework import serializers

from catalog.models import Brand, Category, Product, ProductVariant


class CategorySummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = (
            "id",
            "name",
        )


class BrandSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Brand
        fields = (
            "id",
            "name",
        )


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
