from rest_framework import serializers

from inventory.models import InventoryStock


class InventoryStockSerializer(serializers.ModelSerializer):
    class Meta:
        model = InventoryStock
        fields = (
            "id",
            "warehouse",
            "variant",
            "quantity",
            "created_at",
            "updated_at",
        )


class InventoryStockCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = InventoryStock
        fields = (
            "warehouse",
            "variant",
            "quantity",
        )

    def validate(self, attrs):
        company = self.context["company"]

        warehouse = attrs.get("warehouse")
        variant = attrs.get("variant")

        if warehouse.company_id != company.id:
            raise serializers.ValidationError(
                {
                    "warehouse": (
                        "La bodega debe pertenecer "
                        "a la misma empresa."
                    )
                }
            )

        if variant.product.company_id != company.id:
            raise serializers.ValidationError(
                {
                    "variant": (
                        "La variante debe pertenecer "
                        "a la misma empresa."
                    )
                }
            )

        return attrs
