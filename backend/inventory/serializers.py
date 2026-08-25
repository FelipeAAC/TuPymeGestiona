from rest_framework import serializers

from inventory.models import (
    InventoryMovement,
    InventoryStock,
)


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


class InventoryMovementSerializer(serializers.ModelSerializer):
    class Meta:
        model = InventoryMovement
        fields = (
            "id",
            "warehouse",
            "variant",
            "movement_type",
            "quantity_delta",
            "created_by",
            "created_at",
        )


class InventoryMovementCreateSerializer(
    serializers.ModelSerializer
):
    class Meta:
        model = InventoryMovement
        fields = (
            "warehouse",
            "variant",
            "movement_type",
            "quantity_delta",
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