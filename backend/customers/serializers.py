from rest_framework import serializers

from .models import Customer


class CustomerSerializer(serializers.ModelSerializer):

    class Meta:
        model = Customer

        fields = (
            "id",
            "company",
            "code",
            "name",
            "tax_id",
            "email",
            "phone",
            "status",
            "created_at",
            "updated_at",
        )


class CustomerCreateSerializer(serializers.ModelSerializer):

    class Meta:
        model = Customer

        fields = (
            "company",
            "code",
            "name",
            "tax_id",
            "email",
            "phone",
            "status",
        )
