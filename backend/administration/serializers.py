import re

from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework import serializers

from organizations.models import (
    Branch,
    Company,
    CompanyMembership,
    CompanyRole,
    Permission,
)

from administration.models import (
    AdministrationEvent,
    CompanySettings,
    OrderStatusConfiguration,
    PaymentMethod,
)
from administration.services import replace_membership_access


User = get_user_model()


def normalize_rut(value):
    raw = re.sub(r"[^0-9kK]", "", (value or "").strip())
    if not raw:
        return ""
    if len(raw) < 2:
        raise serializers.ValidationError("El RUT es invalido.")
    body, supplied_dv = raw[:-1], raw[-1].upper()
    if not body.isdigit():
        raise serializers.ValidationError("El RUT es invalido.")
    total = 0
    factor = 2
    for digit in reversed(body):
        total += int(digit) * factor
        factor = 2 if factor == 7 else factor + 1
    result = 11 - (total % 11)
    expected_dv = "0" if result == 11 else "K" if result == 10 else str(result)
    if supplied_dv != expected_dv:
        raise serializers.ValidationError("El RUT es invalido.")
    return f"{int(body)}-{supplied_dv}"


class CompanyAdminSerializer(serializers.ModelSerializer):
    class Meta:
        model = Company
        fields = (
            "id",
            "name",
            "rut",
            "legal_name",
            "business_activity",
            "contact_email",
            "phone",
            "address",
            "commune",
            "city",
            "is_active",
        )
        read_only_fields = ("id",)

    def validate_rut(self, value):
        return normalize_rut(value)

    def validate(self, attrs):
        rut = attrs.get("rut", getattr(self.instance, "rut", ""))
        if rut:
            query = Company.objects.filter(rut__iexact=rut)
            if self.instance:
                query = query.exclude(pk=self.instance.pk)
            if query.exists():
                raise serializers.ValidationError({"rut": "El RUT ya esta registrado."})
        return attrs


class BranchAdminSerializer(serializers.ModelSerializer):
    class Meta:
        model = Branch
        fields = (
            "id",
            "company",
            "code",
            "name",
            "address",
            "commune",
            "city",
            "phone",
            "is_active",
        )
        read_only_fields = ("id", "company")

    def validate_code(self, value):
        value = value.strip().upper()
        if not value:
            raise serializers.ValidationError("El codigo de la sucursal es obligatorio.")
        return value

    def validate_name(self, value):
        value = " ".join(value.split())
        if not value:
            raise serializers.ValidationError("El nombre de la sucursal es obligatorio.")
        return value

    def validate(self, attrs):
        company = self.context["company"]
        code = attrs.get("code", getattr(self.instance, "code", ""))
        query = Branch.objects.filter(company=company, code__iexact=code)
        if self.instance:
            query = query.exclude(pk=self.instance.pk)
        if query.exists():
            raise serializers.ValidationError({"code": "Ya existe una sucursal con ese codigo."})
        return attrs


class PermissionAdminSerializer(serializers.ModelSerializer):
    class Meta:
        model = Permission
        fields = ("id", "code", "scope_behavior")


class RoleAdminSerializer(serializers.ModelSerializer):
    permission_codes = serializers.SerializerMethodField()

    class Meta:
        model = CompanyRole
        fields = ("id", "name", "status", "permission_codes")

    def get_permission_codes(self, role):
        return list(
            role.permission_links.order_by("permission__code").values_list(
                "permission__code",
                flat=True,
            )
        )


class RoleWriteSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=150)
    status = serializers.ChoiceField(choices=CompanyRole.Status.choices)
    permission_codes = serializers.ListField(
        child=serializers.CharField(max_length=100),
        allow_empty=True,
    )

    def validate_name(self, value):
        value = " ".join(value.split())
        if not value:
            raise serializers.ValidationError("El nombre del rol es obligatorio.")
        return value

    def validate_permission_codes(self, value):
        unique = list(dict.fromkeys(code.strip() for code in value if code.strip()))
        if Permission.objects.filter(code__in=unique).count() != len(unique):
            raise serializers.ValidationError("Uno o mas permisos no existen.")
        return unique


class MembershipUserSerializer(serializers.ModelSerializer):
    user_id = serializers.IntegerField(source="user.id", read_only=True)
    username = serializers.CharField(source="user.username", read_only=True)
    email = serializers.EmailField(source="user.email", read_only=True)
    first_name = serializers.CharField(source="user.first_name", read_only=True)
    last_name = serializers.CharField(source="user.last_name", read_only=True)
    branch_ids = serializers.SerializerMethodField()
    role_ids = serializers.SerializerMethodField()
    role_names = serializers.SerializerMethodField()

    class Meta:
        model = CompanyMembership
        fields = (
            "id",
            "user_id",
            "username",
            "email",
            "first_name",
            "last_name",
            "status",
            "branch_ids",
            "role_ids",
            "role_names",
        )

    def get_branch_ids(self, membership):
        return list(
            membership.branch_memberships.order_by("branch_id").values_list(
                "branch_id",
                flat=True,
            )
        )

    def get_role_ids(self, membership):
        return list(
            membership.role_assignments.order_by("role_id").values_list(
                "role_id",
                flat=True,
            ).distinct()
        )

    def get_role_names(self, membership):
        return list(
            membership.role_assignments.order_by("role__name").values_list(
                "role__name",
                flat=True,
            ).distinct()
        )


class UserCreateSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150, required=False, allow_blank=True)
    email = serializers.EmailField(max_length=254)
    first_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    last_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    password = serializers.CharField(write_only=True, required=False, allow_blank=True, min_length=8)
    role_ids = serializers.ListField(child=serializers.IntegerField(min_value=1), allow_empty=True)
    branch_ids = serializers.ListField(child=serializers.IntegerField(min_value=1), allow_empty=True)

    def validate_email(self, value):
        return value.strip().lower()

    def validate(self, attrs):
        company = self.context["company"]
        role_ids = list(dict.fromkeys(attrs.get("role_ids", [])))
        branch_ids = list(dict.fromkeys(attrs.get("branch_ids", [])))
        if company.roles.filter(id__in=role_ids).count() != len(role_ids):
            raise serializers.ValidationError({"role_ids": "Uno o mas roles no pertenecen a la empresa."})
        if company.branches.filter(id__in=branch_ids).count() != len(branch_ids):
            raise serializers.ValidationError({"branch_ids": "Una o mas sucursales no pertenecen a la empresa."})
        attrs["role_ids"] = role_ids
        attrs["branch_ids"] = branch_ids
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        company = self.context["company"]
        email = validated_data["email"]
        user = User.objects.filter(email__iexact=email).first()
        created_identity = False
        if user is None:
            password = validated_data.get("password", "")
            if not password:
                raise serializers.ValidationError({"password": "La contraseña es obligatoria para un usuario nuevo."})
            username = validated_data.get("username", "").strip()
            if not username:
                base = re.sub(r"[^A-Za-z0-9._-]", "", email.split("@", 1)[0]) or "usuario"
                username = base
                suffix = 1
                while User.objects.filter(username=username).exists():
                    suffix += 1
                    username = f"{base}{suffix}"
            elif User.objects.filter(username=username).exists():
                raise serializers.ValidationError({"username": "El nombre de usuario ya esta registrado."})
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                first_name=validated_data.get("first_name", "").strip(),
                last_name=validated_data.get("last_name", "").strip(),
            )
            created_identity = True
        membership, created_membership = CompanyMembership.objects.get_or_create(
            user=user,
            company=company,
            defaults={"status": CompanyMembership.Status.ACTIVE},
        )
        if not created_membership:
            if membership.status == CompanyMembership.Status.ACTIVE:
                raise serializers.ValidationError({"email": "El usuario ya pertenece a esta empresa."})
            membership.status = CompanyMembership.Status.ACTIVE
            membership.save(update_fields=["status", "updated_at"])
        replace_membership_access(
            membership=membership,
            branch_ids=validated_data.get("branch_ids", []),
            role_ids=validated_data.get("role_ids", []),
        )
        membership._created_identity = created_identity
        return membership


class UserUpdateSerializer(serializers.Serializer):
    first_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    last_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    status = serializers.ChoiceField(choices=CompanyMembership.Status.choices, required=False)
    role_ids = serializers.ListField(child=serializers.IntegerField(min_value=1), required=False, allow_empty=True)
    branch_ids = serializers.ListField(child=serializers.IntegerField(min_value=1), required=False, allow_empty=True)

    def validate(self, attrs):
        company = self.context["company"]
        if "role_ids" in attrs:
            attrs["role_ids"] = list(dict.fromkeys(attrs["role_ids"]))
            if company.roles.filter(id__in=attrs["role_ids"]).count() != len(attrs["role_ids"]):
                raise serializers.ValidationError({"role_ids": "Uno o mas roles no pertenecen a la empresa."})
        if "branch_ids" in attrs:
            attrs["branch_ids"] = list(dict.fromkeys(attrs["branch_ids"]))
            if company.branches.filter(id__in=attrs["branch_ids"]).count() != len(attrs["branch_ids"]):
                raise serializers.ValidationError({"branch_ids": "Una o mas sucursales no pertenecen a la empresa."})
        return attrs


class PaymentMethodSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentMethod
        fields = ("id", "code", "name", "kind", "is_active", "sort_order")

    def validate_code(self, value):
        value = value.strip().upper()
        if not value:
            raise serializers.ValidationError("El codigo del metodo de pago es obligatorio.")
        return value

    def validate_name(self, value):
        value = " ".join(value.split())
        if not value:
            raise serializers.ValidationError("El nombre del metodo de pago es obligatorio.")
        return value

    def validate(self, attrs):
        company = self.context.get("company") or getattr(self.instance, "company", None)
        if company is None:
            return attrs
        code = attrs.get("code", getattr(self.instance, "code", ""))
        query = PaymentMethod.objects.filter(company=company, code__iexact=code)
        if self.instance:
            query = query.exclude(pk=self.instance.pk)
        if query.exists():
            raise serializers.ValidationError({"code": "Ya existe un metodo de pago con ese codigo."})
        return attrs


class CompanySettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = CompanySettings
        fields = (
            "vat_rate",
            "currency",
            "timezone",
            "payment_provider",
            "payment_sandbox_enabled",
            "notification_sender_email",
            "updated_at",
        )
        read_only_fields = ("updated_at",)


class OrderStatusConfigurationSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderStatusConfiguration
        fields = (
            "id",
            "code",
            "display_name",
            "sort_order",
            "is_active",
            "is_system",
        )
        read_only_fields = ("id", "code", "is_system")


class AdministrationEventSerializer(serializers.ModelSerializer):
    actor_name = serializers.SerializerMethodField()

    class Meta:
        model = AdministrationEvent
        fields = (
            "id",
            "event_type",
            "resource_type",
            "resource_id",
            "actor_name",
            "metadata",
            "created_at",
        )

    def get_actor_name(self, event):
        full_name = event.actor.get_full_name().strip()
        return full_name or event.actor.username
