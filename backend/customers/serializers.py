from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction

from rest_framework import serializers

from .models import Customer


CUSTOMER_ORDERING_CHOICES = (
    ("name", "Nombre ascendente"),
    ("-name", "Nombre descendente"),
    ("code", "Código ascendente"),
    ("-code", "Código descendente"),
    ("created_at", "Fecha de creación ascendente"),
    ("-created_at", "Fecha de creación descendente"),
    ("updated_at", "Fecha de actualización ascendente"),
    ("-updated_at", "Fecha de actualización descendente"),
)


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
            "address",
            "commune",
            "city",
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


class CustomerListQuerySerializer(serializers.Serializer):
    code = serializers.CharField(
        max_length=50,
        required=False,
        allow_blank=True,
    )
    name = serializers.CharField(
        max_length=150,
        required=False,
        allow_blank=True,
    )
    tax_id = serializers.CharField(
        max_length=50,
        required=False,
        allow_blank=True,
    )
    status = serializers.ChoiceField(
        choices=Customer.Status.choices,
        required=False,
    )
    search = serializers.CharField(
        max_length=150,
        required=False,
        allow_blank=True,
    )
    ordering = serializers.ChoiceField(
        choices=CUSTOMER_ORDERING_CHOICES,
        required=False,
        default="name",
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
    address = serializers.CharField(max_length=220, required=False, allow_blank=True, default="")
    commune = serializers.CharField(max_length=120, required=False, allow_blank=True, default="")
    city = serializers.CharField(max_length=120, required=False, allow_blank=True, default="")
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
    address = serializers.CharField(max_length=220, required=False, allow_blank=True)
    commune = serializers.CharField(max_length=120, required=False, allow_blank=True)
    city = serializers.CharField(max_length=120, required=False, allow_blank=True)
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
