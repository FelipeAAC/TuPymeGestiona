from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from organizations.authorization import has_permission
from organizations.models import CompanyMembership

from catalog.models import Brand, Category, Product, ProductVariant, Supplier
from catalog.serializers import (
    BrandCreateSerializer,
    BrandSummarySerializer,
    CategoryCreateSerializer,
    CategoryDetailSerializer,
    CategorySummarySerializer,
    ProductCreateSerializer,
    ProductSerializer,
    ProductUpdateSerializer,
    ProductVariantCreateSerializer,
    ProductVariantSerializer,
    ProductVariantUpdateSerializer,
    SupplierCreateSerializer,
    SupplierSerializer,
    SupplierUpdateSerializer,
)


PRODUCTS_VIEW_PERMISSION_CODE = "catalog.products.view"
PRODUCTS_MANAGE_PERMISSION_CODE = "catalog.products.manage"
CATEGORIES_MANAGE_PERMISSION_CODE = "catalog.categories.manage"
BRANDS_MANAGE_PERMISSION_CODE = "catalog.brands.manage"
SUPPLIERS_MANAGE_PERMISSION_CODE = "catalog.suppliers.manage"


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

    if company_id <= 0:
        return None

    return company_id


def _get_active_membership(*, user, company_id):
    return (
        CompanyMembership.objects.filter(
            user=user,
            company_id=company_id,
            status=CompanyMembership.Status.ACTIVE,
        )
        .select_related("company")
        .first()
    )


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def product_list_view(request):
    if request.method == "POST":
        return _create_product(request)

    return _list_products(request)


@api_view(["GET", "PATCH"])
@permission_classes([IsAuthenticated])
def product_detail_view(request, product_id):
    if request.method == "PATCH":
        return _update_product(
            request,
            product_id=product_id,
        )

    return _retrieve_product(
        request,
        product_id=product_id,
    )


def _retrieve_product(request, *, product_id):
    raw_company_id = request.query_params.get("company")

    if raw_company_id in (None, ""):
        return Response(
            {
                "detail": "El parametro company es obligatorio.",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    company_id = _parse_company_id(raw_company_id)

    if company_id is None:
        return Response(
            {
                "detail": "El parametro company debe ser un entero valido.",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    membership = _get_active_membership(
        user=request.user,
        company_id=company_id,
    )

    if membership is None:
        return Response(
            {
                "detail": "No tienes acceso a esta empresa.",
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    company = membership.company

    if not has_permission(
        user=request.user,
        company=company,
        permission_code=PRODUCTS_VIEW_PERMISSION_CODE,
    ):
        return Response(
            {
                "detail": "No tienes permiso para ver los productos.",
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    product = (
        Product.objects.filter(
            pk=product_id,
            company=company,
        )
        .select_related(
            "category",
            "brand",
        )
        .prefetch_related(
            "variants",
        )
        .first()
    )

    if product is None:
        return Response(
            {
                "detail": "El producto no existe en esta empresa.",
            },
            status=status.HTTP_404_NOT_FOUND,
        )

    return Response(
        {
            "product": ProductSerializer(product).data,
        }
    )


def _update_product(request, *, product_id):
    raw_company_id = request.data.get("company")

    if raw_company_id in (None, ""):
        return Response(
            {
                "detail": "El campo company es obligatorio.",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    company_id = _parse_company_id(raw_company_id)

    if company_id is None:
        return Response(
            {
                "detail": "El campo company debe ser un entero valido.",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    membership = _get_active_membership(
        user=request.user,
        company_id=company_id,
    )

    if membership is None:
        return Response(
            {
                "detail": "No tienes acceso a esta empresa.",
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    company = membership.company

    if not has_permission(
        user=request.user,
        company=company,
        permission_code=PRODUCTS_MANAGE_PERMISSION_CODE,
    ):
        return Response(
            {
                "detail": "No tienes permiso para administrar los productos.",
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    product = (
        Product.objects.filter(
            pk=product_id,
            company=company,
        )
        .select_related(
            "category",
            "brand",
        )
        .prefetch_related(
            "variants",
        )
        .first()
    )

    if product is None:
        return Response(
            {
                "detail": "El producto no existe en esta empresa.",
            },
            status=status.HTTP_404_NOT_FOUND,
        )

    payload = request.data.copy()
    payload.pop("company", None)

    serializer = ProductUpdateSerializer(
        product,
        data=payload,
        partial=True,
        context={
            "company": company,
        },
    )
    serializer.is_valid(
        raise_exception=True,
    )

    product = serializer.save()

    return Response(
        {
            "product": ProductSerializer(product).data,
        }
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def product_variant_create_view(request, product_id):
    raw_company_id = request.data.get("company")

    if raw_company_id in (None, ""):
        return Response(
            {
                "detail": "El campo company es obligatorio.",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    company_id = _parse_company_id(raw_company_id)

    if company_id is None:
        return Response(
            {
                "detail": "El campo company debe ser un entero valido.",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    membership = _get_active_membership(
        user=request.user,
        company_id=company_id,
    )

    if membership is None:
        return Response(
            {
                "detail": "No tienes acceso a esta empresa.",
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    company = membership.company

    if not has_permission(
        user=request.user,
        company=company,
        permission_code=PRODUCTS_MANAGE_PERMISSION_CODE,
    ):
        return Response(
            {
                "detail": "No tienes permiso para administrar los productos.",
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    product = (
        Product.objects.filter(
            pk=product_id,
            company=company,
        )
        .first()
    )

    if product is None:
        return Response(
            {
                "detail": "El producto no existe en esta empresa.",
            },
            status=status.HTTP_404_NOT_FOUND,
        )

    payload = request.data.copy()
    payload.pop("company", None)

    serializer = ProductVariantCreateSerializer(
        data=payload,
        context={
            "product": product,
        },
    )
    serializer.is_valid(
        raise_exception=True,
    )

    variant = serializer.save()

    return Response(
        {
            "variant": ProductVariantSerializer(variant).data,
        },
        status=status.HTTP_201_CREATED,
    )


@api_view(["GET", "PATCH"])
@permission_classes([IsAuthenticated])
def product_variant_detail_view(
    request,
    product_id,
    variant_id,
):
    if request.method == "PATCH":
        return _update_product_variant(
            request,
            product_id=product_id,
            variant_id=variant_id,
        )

    return _retrieve_product_variant(
        request,
        product_id=product_id,
        variant_id=variant_id,
    )


def _retrieve_product_variant(
    request,
    *,
    product_id,
    variant_id,
):
    raw_company_id = request.query_params.get("company")

    if raw_company_id in (None, ""):
        return Response(
            {
                "detail": "El parametro company es obligatorio.",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    company_id = _parse_company_id(raw_company_id)

    if company_id is None:
        return Response(
            {
                "detail": "El parametro company debe ser un entero valido.",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    membership = _get_active_membership(
        user=request.user,
        company_id=company_id,
    )

    if membership is None:
        return Response(
            {
                "detail": "No tienes acceso a esta empresa.",
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    company = membership.company

    if not has_permission(
        user=request.user,
        company=company,
        permission_code=PRODUCTS_VIEW_PERMISSION_CODE,
    ):
        return Response(
            {
                "detail": "No tienes permiso para ver los productos.",
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    variant = (
        ProductVariant.objects.filter(
            pk=variant_id,
            product_id=product_id,
            product__company=company,
        )
        .select_related(
            "product",
        )
        .first()
    )

    if variant is None:
        return Response(
            {
                "detail": "La variante no existe para este producto.",
            },
            status=status.HTTP_404_NOT_FOUND,
        )

    return Response(
        {
            "variant": ProductVariantSerializer(variant).data,
        }
    )


def _update_product_variant(
    request,
    *,
    product_id,
    variant_id,
):
    raw_company_id = request.data.get("company")

    if raw_company_id in (None, ""):
        return Response(
            {
                "detail": "El campo company es obligatorio.",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    company_id = _parse_company_id(raw_company_id)

    if company_id is None:
        return Response(
            {
                "detail": "El campo company debe ser un entero valido.",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    membership = _get_active_membership(
        user=request.user,
        company_id=company_id,
    )

    if membership is None:
        return Response(
            {
                "detail": "No tienes acceso a esta empresa.",
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    company = membership.company

    if not has_permission(
        user=request.user,
        company=company,
        permission_code=PRODUCTS_MANAGE_PERMISSION_CODE,
    ):
        return Response(
            {
                "detail": "No tienes permiso para administrar los productos.",
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    variant = (
        ProductVariant.objects.filter(
            pk=variant_id,
            product_id=product_id,
            product__company=company,
        )
        .select_related(
            "product",
        )
        .first()
    )

    if variant is None:
        return Response(
            {
                "detail": "La variante no existe para este producto.",
            },
            status=status.HTTP_404_NOT_FOUND,
        )

    payload = request.data.copy()
    payload.pop("company", None)

    serializer = ProductVariantUpdateSerializer(
        variant,
        data=payload,
        partial=True,
    )
    serializer.is_valid(
        raise_exception=True,
    )

    variant = serializer.save()

    return Response(
        {
            "variant": ProductVariantSerializer(variant).data,
        }
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def product_options_view(request):
    raw_company_id = request.query_params.get("company")

    if raw_company_id in (None, ""):
        return Response(
            {
                "detail": "El parametro company es obligatorio.",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    company_id = _parse_company_id(raw_company_id)

    if company_id is None:
        return Response(
            {
                "detail": "El parametro company debe ser un entero valido.",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    membership = _get_active_membership(
        user=request.user,
        company_id=company_id,
    )

    if membership is None:
        return Response(
            {
                "detail": "No tienes acceso a esta empresa.",
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    company = membership.company

    if not has_permission(
        user=request.user,
        company=company,
        permission_code=PRODUCTS_MANAGE_PERMISSION_CODE,
    ):
        return Response(
            {
                "detail": "No tienes permiso para administrar los productos.",
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    categories = Category.objects.filter(
        company=company,
        status=Category.Status.ACTIVE,
    )

    brands = Brand.objects.filter(
        company=company,
    )

    return Response(
        {
            "categories": CategorySummarySerializer(
                categories,
                many=True,
            ).data,
            "brands": BrandSummarySerializer(
                brands,
                many=True,
            ).data,
        }
    )


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def category_list_create_view(request):
    if request.method == "POST":
        return _create_category(request)

    return _list_categories(request)


def _list_categories(request):
    raw_company_id = request.query_params.get("company")

    if raw_company_id in (None, ""):
        return Response(
            {
                "detail": "El parametro company es obligatorio.",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    company_id = _parse_company_id(raw_company_id)

    if company_id is None:
        return Response(
            {
                "detail": "El parametro company debe ser un entero valido.",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    membership = _get_active_membership(
        user=request.user,
        company_id=company_id,
    )

    if membership is None:
        return Response(
            {
                "detail": "No tienes acceso a esta empresa.",
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    company = membership.company

    if not has_permission(
        user=request.user,
        company=company,
        permission_code=CATEGORIES_MANAGE_PERMISSION_CODE,
    ):
        return Response(
            {
                "detail": "No tienes permiso para administrar las categorias.",
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    categories = (
        Category.objects.filter(
            company=company,
        )
        .select_related("parent")
    )

    return Response(
        {
            "categories": CategoryDetailSerializer(
                categories,
                many=True,
            ).data,
        }
    )


def _create_category(request):
    raw_company_id = request.data.get("company")

    if raw_company_id in (None, ""):
        return Response(
            {
                "detail": "El campo company es obligatorio.",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    company_id = _parse_company_id(raw_company_id)

    if company_id is None:
        return Response(
            {
                "detail": "El campo company debe ser un entero valido.",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    membership = _get_active_membership(
        user=request.user,
        company_id=company_id,
    )

    if membership is None:
        return Response(
            {
                "detail": "No tienes acceso a esta empresa.",
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    company = membership.company

    if not has_permission(
        user=request.user,
        company=company,
        permission_code=CATEGORIES_MANAGE_PERMISSION_CODE,
    ):
        return Response(
            {
                "detail": "No tienes permiso para administrar las categorias.",
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    serializer = CategoryCreateSerializer(
        data=request.data,
        context={
            "company": company,
        },
    )
    serializer.is_valid(
        raise_exception=True,
    )

    category = serializer.save()

    return Response(
        {
            "category": CategoryDetailSerializer(category).data,
        },
        status=status.HTTP_201_CREATED,
    )


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def brand_list_create_view(request):
    if request.method == "POST":
        return _create_brand(request)

    return _list_brands(request)


def _list_brands(request):
    raw_company_id = request.query_params.get("company")

    if raw_company_id in (None, ""):
        return Response(
            {
                "detail": "El parametro company es obligatorio.",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    company_id = _parse_company_id(raw_company_id)

    if company_id is None:
        return Response(
            {
                "detail": "El parametro company debe ser un entero valido.",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    membership = _get_active_membership(
        user=request.user,
        company_id=company_id,
    )

    if membership is None:
        return Response(
            {
                "detail": "No tienes acceso a esta empresa.",
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    company = membership.company

    if not has_permission(
        user=request.user,
        company=company,
        permission_code=BRANDS_MANAGE_PERMISSION_CODE,
    ):
        return Response(
            {
                "detail": "No tienes permiso para administrar las marcas.",
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    brands = Brand.objects.filter(
        company=company,
    )

    return Response(
        {
            "brands": BrandSummarySerializer(
                brands,
                many=True,
            ).data,
        }
    )


def _create_brand(request):
    raw_company_id = request.data.get("company")

    if raw_company_id in (None, ""):
        return Response(
            {
                "detail": "El campo company es obligatorio.",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    company_id = _parse_company_id(raw_company_id)

    if company_id is None:
        return Response(
            {
                "detail": "El campo company debe ser un entero valido.",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    membership = _get_active_membership(
        user=request.user,
        company_id=company_id,
    )

    if membership is None:
        return Response(
            {
                "detail": "No tienes acceso a esta empresa.",
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    company = membership.company

    if not has_permission(
        user=request.user,
        company=company,
        permission_code=BRANDS_MANAGE_PERMISSION_CODE,
    ):
        return Response(
            {
                "detail": "No tienes permiso para administrar las marcas.",
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    serializer = BrandCreateSerializer(
        data=request.data,
        context={
            "company": company,
        },
    )
    serializer.is_valid(
        raise_exception=True,
    )

    brand = serializer.save()

    return Response(
        {
            "brand": BrandSummarySerializer(brand).data,
        },
        status=status.HTTP_201_CREATED,
    )


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def supplier_list_create_view(request):
    if request.method == "POST":
        return _create_supplier(request)

    return _list_suppliers(request)


def _list_suppliers(request):
    raw_company_id = request.query_params.get("company")

    if raw_company_id in (None, ""):
        return Response(
            {
                "detail": "El parametro company es obligatorio.",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    company_id = _parse_company_id(raw_company_id)

    if company_id is None:
        return Response(
            {
                "detail": "El parametro company debe ser un entero valido.",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    membership = _get_active_membership(
        user=request.user,
        company_id=company_id,
    )

    if membership is None:
        return Response(
            {
                "detail": "No tienes acceso a esta empresa.",
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    company = membership.company

    if not has_permission(
        user=request.user,
        company=company,
        permission_code=SUPPLIERS_MANAGE_PERMISSION_CODE,
    ):
        return Response(
            {
                "detail": (
                    "No tienes permiso para administrar los proveedores."
                ),
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    suppliers = Supplier.objects.filter(
        company=company,
    )

    return Response(
        {
            "suppliers": SupplierSerializer(
                suppliers,
                many=True,
            ).data,
        }
    )


def _create_supplier(request):
    raw_company_id = request.data.get("company")

    if raw_company_id in (None, ""):
        return Response(
            {
                "detail": "El campo company es obligatorio.",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    company_id = _parse_company_id(raw_company_id)

    if company_id is None:
        return Response(
            {
                "detail": "El campo company debe ser un entero valido.",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    membership = _get_active_membership(
        user=request.user,
        company_id=company_id,
    )

    if membership is None:
        return Response(
            {
                "detail": "No tienes acceso a esta empresa.",
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    company = membership.company

    if not has_permission(
        user=request.user,
        company=company,
        permission_code=SUPPLIERS_MANAGE_PERMISSION_CODE,
    ):
        return Response(
            {
                "detail": (
                    "No tienes permiso para administrar los proveedores."
                ),
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    serializer = SupplierCreateSerializer(
        data=request.data,
        context={
            "company": company,
        },
    )
    serializer.is_valid(
        raise_exception=True,
    )

    supplier = serializer.save()

    return Response(
        {
            "supplier": SupplierSerializer(supplier).data,
        },
        status=status.HTTP_201_CREATED,
    )


@api_view(["GET", "PATCH"])
@permission_classes([IsAuthenticated])
def supplier_detail_view(request, supplier_id):
    if request.method == "PATCH":
        return _update_supplier(
            request,
            supplier_id=supplier_id,
        )

    return _retrieve_supplier(
        request,
        supplier_id=supplier_id,
    )


def _retrieve_supplier(request, *, supplier_id):
    raw_company_id = request.query_params.get("company")

    if raw_company_id in (None, ""):
        return Response(
            {
                "detail": "El parametro company es obligatorio.",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    company_id = _parse_company_id(raw_company_id)

    if company_id is None:
        return Response(
            {
                "detail": "El parametro company debe ser un entero valido.",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    membership = _get_active_membership(
        user=request.user,
        company_id=company_id,
    )

    if membership is None:
        return Response(
            {
                "detail": "No tienes acceso a esta empresa.",
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    company = membership.company

    if not has_permission(
        user=request.user,
        company=company,
        permission_code=SUPPLIERS_MANAGE_PERMISSION_CODE,
    ):
        return Response(
            {
                "detail": (
                    "No tienes permiso para administrar los proveedores."
                ),
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    supplier = Supplier.objects.filter(
        pk=supplier_id,
        company=company,
    ).first()

    if supplier is None:
        return Response(
            {
                "detail": "El proveedor no existe en esta empresa.",
            },
            status=status.HTTP_404_NOT_FOUND,
        )

    return Response(
        {
            "supplier": SupplierSerializer(supplier).data,
        }
    )


def _update_supplier(request, *, supplier_id):
    raw_company_id = request.data.get("company")

    if raw_company_id in (None, ""):
        return Response(
            {
                "detail": "El campo company es obligatorio.",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    company_id = _parse_company_id(raw_company_id)

    if company_id is None:
        return Response(
            {
                "detail": "El campo company debe ser un entero valido.",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    membership = _get_active_membership(
        user=request.user,
        company_id=company_id,
    )

    if membership is None:
        return Response(
            {
                "detail": "No tienes acceso a esta empresa.",
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    company = membership.company

    if not has_permission(
        user=request.user,
        company=company,
        permission_code=SUPPLIERS_MANAGE_PERMISSION_CODE,
    ):
        return Response(
            {
                "detail": (
                    "No tienes permiso para administrar los proveedores."
                ),
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    supplier = Supplier.objects.filter(
        pk=supplier_id,
        company=company,
    ).first()

    if supplier is None:
        return Response(
            {
                "detail": "El proveedor no existe en esta empresa.",
            },
            status=status.HTTP_404_NOT_FOUND,
        )

    payload = request.data.copy()
    payload.pop("company", None)

    serializer = SupplierUpdateSerializer(
        supplier,
        data=payload,
        partial=True,
    )
    serializer.is_valid(
        raise_exception=True,
    )

    supplier = serializer.save()

    return Response(
        {
            "supplier": SupplierSerializer(supplier).data,
        }
    )


def _list_products(request):
    raw_company_id = request.query_params.get("company")

    if raw_company_id in (None, ""):
        return Response(
            {
                "detail": "El parametro company es obligatorio.",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    company_id = _parse_company_id(raw_company_id)

    if company_id is None:
        return Response(
            {
                "detail": "El parametro company debe ser un entero valido.",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    membership = _get_active_membership(
        user=request.user,
        company_id=company_id,
    )

    if membership is None:
        return Response(
            {
                "detail": "No tienes acceso a esta empresa.",
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    company = membership.company

    if not has_permission(
        user=request.user,
        company=company,
        permission_code=PRODUCTS_VIEW_PERMISSION_CODE,
    ):
        return Response(
            {
                "detail": "No tienes permiso para ver los productos.",
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    products = (
        Product.objects.filter(
            company=company,
        )
        .select_related(
            "category",
            "brand",
        )
        .prefetch_related(
            "variants",
        )
    )

    return Response(
        {
            "products": ProductSerializer(
                products,
                many=True,
            ).data,
        }
    )


def _create_product(request):
    raw_company_id = request.data.get("company")

    if raw_company_id in (None, ""):
        return Response(
            {
                "detail": "El campo company es obligatorio.",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    company_id = _parse_company_id(raw_company_id)

    if company_id is None:
        return Response(
            {
                "detail": "El campo company debe ser un entero valido.",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    membership = _get_active_membership(
        user=request.user,
        company_id=company_id,
    )

    if membership is None:
        return Response(
            {
                "detail": "No tienes acceso a esta empresa.",
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    company = membership.company

    if not has_permission(
        user=request.user,
        company=company,
        permission_code=PRODUCTS_MANAGE_PERMISSION_CODE,
    ):
        return Response(
            {
                "detail": "No tienes permiso para administrar los productos.",
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    serializer = ProductCreateSerializer(
        data=request.data,
        context={
            "company": company,
        },
    )
    serializer.is_valid(
        raise_exception=True,
    )

    product = serializer.save()

    return Response(
        {
            "product": ProductSerializer(product).data,
        },
        status=status.HTTP_201_CREATED,
    )
