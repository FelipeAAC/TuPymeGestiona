from rest_framework import serializers

from inventory.models import (
    InventoryMovement,
    InventoryStock,
    InventoryTransfer,
    InventoryTransferItem,
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



class InventoryTransferItemCreateSerializer(
    serializers.ModelSerializer
):

    class Meta:
        model = InventoryTransferItem

        fields = (
            "variant",
            "quantity",
        )



class InventoryTransferItemSerializer(
    serializers.ModelSerializer
):

    class Meta:
        model = InventoryTransferItem

        fields = (
            "variant",
            "quantity",
        )



class InventoryTransferCreateSerializer(
    serializers.ModelSerializer
):

    items = InventoryTransferItemCreateSerializer(
        many=True,
    )

    class Meta:
        model = InventoryTransfer

        fields = (
            "source_warehouse",
            "destination_warehouse",
            "items",
        )


    def validate(self, attrs):

        company = self.context["company"]

        source = attrs.get(
            "source_warehouse",
        )

        destination = attrs.get(
            "destination_warehouse",
        )

        items = attrs.get(
            "items",
        )


        if source.company_id != company.id:

            raise serializers.ValidationError(
                {
                    "source_warehouse": (
                        "La bodega origen debe pertenecer "
                        "a la misma empresa."
                    )
                }
            )


        if destination.company_id != company.id:

            raise serializers.ValidationError(
                {
                    "destination_warehouse": (
                        "La bodega destino debe pertenecer "
                        "a la misma empresa."
                    )
                }
            )


        if source.id == destination.id:

            raise serializers.ValidationError(
                {
                    "destination_warehouse": (
                        "La bodega destino debe ser "
                        "diferente a la bodega origen."
                    )
                }
            )


        for item in items:

            variant = item["variant"]

            if variant.product.company_id != company.id:

                raise serializers.ValidationError(
                    {
                        "items": (
                            "Todas las variantes deben "
                            "pertenecer a la empresa."
                        )
                    }
                )


        return attrs



class InventoryTransferSerializer(
    serializers.ModelSerializer
):

    items = InventoryTransferItemSerializer(
        many=True,
        read_only=True,
    )


    class Meta:
        model = InventoryTransfer

        fields = (
            "id",
            "source_warehouse",
            "destination_warehouse",
            "created_by",
            "status",
            "created_at",
            "items",
        )
