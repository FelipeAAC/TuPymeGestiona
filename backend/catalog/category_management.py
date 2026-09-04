from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from catalog.models import Category
from organizations.authorization import has_permission
from organizations.models import CompanyMembership

CATEGORIES_MANAGE_PERMISSION_CODE = "catalog.categories.manage"


def _parse_company_id(raw_company_id):
    if isinstance(raw_company_id, bool):
        return None
    if isinstance(raw_company_id, int):
        company_id = raw_company_id
    elif isinstance(raw_company_id, str):
        raw_company_id = raw_company_id.strip()
        if not raw_company_id.isdecimal():
            return None
        company_id = int(raw_company_id)
    else:
        return None
    return company_id if company_id > 0 else None


def _membership_for(*, user, company_id):
    return (
        CompanyMembership.objects.filter(
            user=user,
            company_id=company_id,
            status=CompanyMembership.Status.ACTIVE,
        )
        .select_related("company")
        .first()
    )


def _authorized_company(request, *, raw_company_id, field_label):
    if raw_company_id in (None, ""):
        return None, Response(
            {"detail": f"El {field_label} company es obligatorio."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    company_id = _parse_company_id(raw_company_id)
    if company_id is None:
        return None, Response(
            {"detail": f"El {field_label} company debe ser un entero valido."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    membership = _membership_for(user=request.user, company_id=company_id)
    if membership is None:
        return None, Response(
            {"detail": "No tienes acceso a esta empresa."},
            status=status.HTTP_403_FORBIDDEN,
        )
    company = membership.company
    if not has_permission(
        user=request.user,
        company=company,
        permission_code=CATEGORIES_MANAGE_PERMISSION_CODE,
    ):
        return None, Response(
            {"detail": "No tienes permiso para administrar las categorias."},
            status=status.HTTP_403_FORBIDDEN,
        )
    return company, None


class CategoryManagementSerializer(serializers.ModelSerializer):
    parent = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ("id", "name", "parent", "status")

    def get_parent(self, obj):
        if obj.parent is None:
            return None
        return {"id": obj.parent_id, "name": obj.parent.name}


class CategoryManagementUpdateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=150, required=False)
    parent = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.none(),
        required=False,
        allow_null=True,
    )
    status = serializers.ChoiceField(choices=Category.Status.choices, required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        company = self.context.get("company")
        if company is not None:
            self.fields["parent"].queryset = Category.objects.filter(company=company)

    def update(self, instance, validated_data):
        for field, value in validated_data.items():
            setattr(instance, field, value)
        try:
            instance.save()
        except DjangoValidationError as exc:
            detail = exc.message_dict if hasattr(exc, "message_dict") else {"detail": exc.messages}
            raise serializers.ValidationError(detail) from exc
        return instance


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def category_management_list_view(request):
    company, error = _authorized_company(
        request,
        raw_company_id=request.query_params.get("company"),
        field_label="parametro",
    )
    if error is not None:
        return error
    categories = Category.objects.filter(company=company).select_related("parent")
    return Response({"categories": CategoryManagementSerializer(categories, many=True).data})


@api_view(["GET", "PATCH"])
@permission_classes([IsAuthenticated])
def category_management_detail_view(request, category_id):
    raw_company_id = (
        request.data.get("company") if request.method == "PATCH" else request.query_params.get("company")
    )
    company, error = _authorized_company(
        request,
        raw_company_id=raw_company_id,
        field_label="campo" if request.method == "PATCH" else "parametro",
    )
    if error is not None:
        return error
    category = (
        Category.objects.filter(pk=category_id, company=company)
        .select_related("parent")
        .first()
    )
    if category is None:
        return Response(
            {"detail": "La categoria no existe en esta empresa."},
            status=status.HTTP_404_NOT_FOUND,
        )
    if request.method == "GET":
        return Response({"category": CategoryManagementSerializer(category).data})

    payload = request.data.copy()
    payload.pop("company", None)
    serializer = CategoryManagementUpdateSerializer(
        category,
        data=payload,
        partial=True,
        context={"company": company},
    )
    serializer.is_valid(raise_exception=True)
    category = serializer.save()
    category = Category.objects.select_related("parent").get(pk=category.pk)
    return Response({"category": CategoryManagementSerializer(category).data})
