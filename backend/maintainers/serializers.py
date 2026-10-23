from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from rest_framework import serializers

from administration.models import CompanySettings, OrderStatusConfiguration, PaymentMethod
from administration.serializers import (
    AdministrationEventSerializer,
    BranchAdminSerializer,
    CompanyAdminSerializer,
    CompanySettingsSerializer,
    MembershipUserSerializer,
    OrderStatusConfigurationSerializer,
    PaymentMethodSerializer,
    PermissionAdminSerializer,
    RoleAdminSerializer,
    RoleWriteSerializer,
    UserCreateSerializer,
    UserUpdateSerializer,
)
from catalog.models import Brand, Category, Product, ProductVariant, Supplier
from organizations.models import Branch, Company, CompanyMembership, Permission, Warehouse
from maintainers.models import MaintainerAuditEvent


User = get_user_model()


class MaintainerUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = (
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "platform_admin",
            "destructive_admin",
        )
        read_only_fields = fields


class MaintainerAuditEventSerializer(serializers.ModelSerializer):
    actor_name = serializers.SerializerMethodField()

    class Meta:
        model = MaintainerAuditEvent
        fields = (
            "id",
            "event_type",
            "resource_type",
            "resource_id",
            "company_id_snapshot",
            "actor_name",
            "metadata",
            "created_at",
        )
        read_only_fields = fields

    def get_actor_name(self, obj):
        return obj.actor.get_full_name() or obj.actor.email or obj.actor.username


class CompanySummarySerializer(serializers.ModelSerializer):
    branches_count = serializers.IntegerField(read_only=True)
    users_count = serializers.IntegerField(read_only=True)
    products_count = serializers.IntegerField(read_only=True)
    orders_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Company
        fields = (
            "id",
            "name",
            "legal_name",
            "rut",
            "is_active",
            "branches_count",
            "users_count",
            "products_count",
            "orders_count",
        )


class MaintainerWarehouseSerializer(serializers.ModelSerializer):
    company = serializers.IntegerField(source="company_id", read_only=True)
    company_id = serializers.IntegerField(read_only=True)
    branch = serializers.IntegerField(source="branch_id", read_only=True, allow_null=True)
    branch_id = serializers.IntegerField(read_only=True)
    branch_name = serializers.CharField(source="branch.name", read_only=True, allow_null=True)

    class Meta:
        model = Warehouse
        fields = (
            "id",
            "company",
            "company_id",
            "branch",
            "branch_id",
            "branch_name",
            "code",
            "name",
            "is_active",
        )


class WarehouseWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Warehouse
        fields = ("branch", "code", "name", "is_active")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        company = self.context.get("company")
        if company is not None:
            self.fields["branch"].queryset = Branch.objects.filter(company=company)

    def validate(self, attrs):
        company = self.context["company"]
        branch = attrs.get("branch", getattr(self.instance, "branch", None))
        if branch is not None and branch.company_id != company.id:
            raise serializers.ValidationError({"branch": "La sucursal debe pertenecer a la empresa."})
        return attrs

    def create(self, validated_data):
        company = self.context["company"]
        warehouse = Warehouse(company=company, **validated_data)
        try:
            warehouse.full_clean()
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.message_dict) from exc
        warehouse.save()
        return warehouse

    def update(self, instance, validated_data):
        for field, value in validated_data.items():
            setattr(instance, field, value)
        try:
            instance.full_clean()
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.message_dict) from exc
        instance.save()
        return instance


class CategoryWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ("name", "parent", "status")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        company = self.context.get("company")
        if company is not None:
            self.fields["parent"].queryset = Category.objects.filter(company=company)

    def validate(self, attrs):
        parent = attrs.get("parent", getattr(self.instance, "parent", None))
        company = self.context["company"]
        if parent is not None and parent.company_id != company.id:
            raise serializers.ValidationError({"parent": "La categoria padre debe pertenecer a la empresa."})
        return attrs

    def create(self, validated_data):
        category = Category(company=self.context["company"], **validated_data)
        try:
            category.full_clean()
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.message_dict) from exc
        category.save()
        return category

    def update(self, instance, validated_data):
        for field, value in validated_data.items():
            setattr(instance, field, value)
        try:
            instance.full_clean()
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.message_dict) from exc
        instance.save()
        return instance


class MaintainerCategorySerializer(serializers.ModelSerializer):
    parent = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ("id", "name", "parent", "status")

    def get_parent(self, obj):
        if obj.parent_id is None:
            return None
        return {"id": obj.parent_id, "name": obj.parent.name}


class BrandWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Brand
        fields = ("name", "is_active")
        extra_kwargs = {"is_active": {"required": False}}

    def create(self, validated_data):
        return Brand.objects.create(company=self.context["company"], **validated_data)


class ProductVariantWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductVariant
        fields = ("sku", "gtin", "base_price", "status")
        extra_kwargs = {"status": {"required": False}}

    def create(self, validated_data):
        variant = ProductVariant(product=self.context["product"], **validated_data)
        try:
            variant.full_clean()
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.message_dict) from exc
        variant.save()
        return variant

    def update(self, instance, validated_data):
        for field, value in validated_data.items():
            setattr(instance, field, value)
        try:
            instance.full_clean()
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.message_dict) from exc
        instance.save()
        return instance


class ProductWriteSerializer(serializers.ModelSerializer):
    variant = ProductVariantWriteSerializer(required=False)

    class Meta:
        model = Product
        fields = ("name", "description", "image_url", "category", "brand", "status", "variant")
        extra_kwargs = {"status": {"required": False}}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        company = self.context.get("company")
        if company is not None:
            self.fields["category"].queryset = Category.objects.filter(company=company)
            self.fields["brand"].queryset = Brand.objects.filter(company=company)

    def validate(self, attrs):
        company = self.context["company"]
        category = attrs.get("category", getattr(self.instance, "category", None))
        brand = attrs.get("brand", getattr(self.instance, "brand", None))
        if category is not None and category.company_id != company.id:
            raise serializers.ValidationError({"category": "La categoria debe pertenecer a la empresa."})
        if brand is not None and brand.company_id != company.id:
            raise serializers.ValidationError({"brand": "La marca debe pertenecer a la empresa."})
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        variant_data = validated_data.pop("variant", None)
        product = Product(company=self.context["company"], **validated_data)
        try:
            product.full_clean()
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.message_dict) from exc
        product.save()
        if variant_data:
            variant = ProductVariant(product=product, **variant_data)
            try:
                variant.full_clean()
            except DjangoValidationError as exc:
                raise serializers.ValidationError({"variant": exc.message_dict}) from exc
            variant.save()
        return product

    def update(self, instance, validated_data):
        validated_data.pop("variant", None)
        for field, value in validated_data.items():
            setattr(instance, field, value)
        try:
            instance.full_clean()
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.message_dict) from exc
        instance.save()
        return instance


class SupplierWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Supplier
        fields = ("name", "contact_name", "email", "phone", "status")
        extra_kwargs = {
            "contact_name": {"required": False, "allow_blank": True},
            "email": {"required": False, "allow_blank": True},
            "phone": {"required": False, "allow_blank": True},
            "status": {"required": False},
        }

    def create(self, validated_data):
        return Supplier.objects.create(company=self.context["company"], **validated_data)


__all__ = [
    "AdministrationEventSerializer",
    "BranchAdminSerializer",
    "CategoryWriteSerializer",
    "CompanyAdminSerializer",
    "CompanySettingsSerializer",
    "CompanySummarySerializer",
    "MaintainerUserSerializer",
    "MaintainerAuditEventSerializer",
    "MaintainerCategorySerializer",
    "MaintainerWarehouseSerializer",
    "MembershipUserSerializer",
    "OrderStatusConfigurationSerializer",
    "PaymentMethodSerializer",
    "PermissionAdminSerializer",
    "ProductVariantWriteSerializer",
    "ProductWriteSerializer",
    "RoleAdminSerializer",
    "RoleWriteSerializer",
    "SupplierWriteSerializer",
    "UserCreateSerializer",
    "UserUpdateSerializer",
    "WarehouseWriteSerializer",
]
