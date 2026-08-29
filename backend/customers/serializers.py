from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction

from rest_framework import serializers

from .models import Customer


def _validation_error_detail(error):
    if hasattr(error, "message_dict"):
        return error.message_dict

    return {
        "non_field_errors": error.messages,
    }


def _validate_unique_code(*, company, code, instance=None):
    customers = Customer.objects.filter(
        company=company,
        code=code,
    )

    if instance is not None:
        customers = customers.exclude(pk=instance.pk)

    if customers.exists():
        raise serializers.ValidationError(
            "Ya existe un cliente con este código en la empresa."
        )

    return code


def _duplicate_code_error():
    return serializers.ValidationError(
        {
            "code": (
                "Ya existe un cliente con este código en la empresa."
            ),
        }
    )


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
        read_only_fields = (
            "id",
            "company",
            "created_at",
            "updated_at",
        )


class CustomerCreateSerializer(serializers.Serializer):
    code = serializers.CharField(
        max_length=50,
    )
    name = serializers.CharField(
        max_length=150,
    )
    tax_id = serializers.CharField(
        max_length=50,
        required=False,
        allow_blank=True,
        default="",
    )
    email = serializers.EmailField(
        required=False,
        allow_blank=True,
        default="",
    )
    phone = serializers.CharField(
        max_length=50,
        required=False,
        allow_blank=True,
        default="",
    )
    status = serializers.ChoiceField(
        choices=Customer.Status.choices,
        required=False,
        default=Customer.Status.ACTIVE,
    )

    def validate_code(self, code):
        return _validate_unique_code(
            company=self.context["company"],
            code=code,
        )

    def create(self, validated_data):
        company = self.context["company"]
        validated_data.pop("company", None)

        try:
            with transaction.atomic():
                return Customer.objects.create(
                    company=company,
                    **validated_data,
                )
        except IntegrityError as error:
            raise _duplicate_code_error() from error
        except DjangoValidationError as error:
            raise serializers.ValidationError(
                _validation_error_detail(error),
            ) from error


class CustomerUpdateSerializer(serializers.Serializer):
    code = serializers.CharField(
        max_length=50,
        required=False,
    )
    name = serializers.CharField(
        max_length=150,
        required=False,
    )
    tax_id = serializers.CharField(
        max_length=50,
        required=False,
        allow_blank=True,
    )
    email = serializers.EmailField(
        required=False,
        allow_blank=True,
    )
    phone = serializers.CharField(
        max_length=50,
        required=False,
        allow_blank=True,
    )
    status = serializers.ChoiceField(
        choices=Customer.Status.choices,
        required=False,
    )

    def validate_code(self, code):
        return _validate_unique_code(
            company=self.instance.company,
            code=code,
            instance=self.instance,
        )

    def update(self, instance, validated_data):
        for field, value in validated_data.items():
            setattr(instance, field, value)

        try:
            with transaction.atomic():
                instance.save()
        except IntegrityError as error:
            raise _duplicate_code_error() from error
        except DjangoValidationError as error:
            raise serializers.ValidationError(
                _validation_error_detail(error),
            ) from error

        return instance
