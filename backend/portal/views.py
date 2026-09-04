from decimal import Decimal

from django.contrib.auth import login
from django.db.models import Q, Sum
from django.views.decorators.csrf import csrf_protect
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from catalog.models import Category, Product, ProductVariant
from inventory.models import InventoryStock
from orders.models import Order
from orders.serializers import OrderSerializer
from organizations.models import Branch, Company

from .models import CustomerPortalAccount
from .serializers import PortalOrderCreateSerializer, PortalRegistrationSerializer
from .services import (
    PortalConflictError,
    PortalStockError,
    create_portal_order,
    register_portal_customer,
)


def _availability_for_variant(variant):
    total = (
        InventoryStock.objects.filter(
            variant=variant,
            warehouse__company=variant.product.company,
        ).aggregate(total=Sum("quantity"))["total"]
        or Decimal("0")
    )
    return total


def _serialize_product(product, *, detailed=False):
    variants = []
    for variant in product.variants.all():
        if variant.status != ProductVariant.Status.ACTIVE:
            continue
        available = _availability_for_variant(variant)
        variants.append(
            {
                "id": variant.id,
                "sku": variant.sku,
                "gtin": variant.gtin,
                "base_price": variant.base_price,
                "available_quantity": format(available, ".3f"),
                "available": available > 0,
            }
        )

    payload = {
        "id": product.id,
        "name": product.name,
        "description": product.description,
        "image_url": product.image_url,
        "category": {"id": product.category_id, "name": product.category.name},
        "brand": (
            {"id": product.brand_id, "name": product.brand.name}
            if product.brand_id
            else None
        ),
        "variants": variants,
        "available": any(item["available"] for item in variants),
    }
    if not detailed:
        payload["description"] = product.description[:220]
    return payload


@api_view(["GET"])
@permission_classes([AllowAny])
def store_list_view(request):
    stores = Company.objects.filter(is_active=True).order_by("name", "id")
    return Response(
        {
            "stores": [
                {
                    "id": company.id,
                    "name": company.name,
                    "legal_name": company.legal_name,
                    "business_activity": company.business_activity,
                    "commune": company.commune,
                    "city": company.city,
                    "branches": [
                        {
                            "id": branch.id,
                            "code": branch.code,
                            "name": branch.name,
                            "address": branch.address,
                            "commune": branch.commune,
                            "city": branch.city,
                        }
                        for branch in company.branches.filter(is_active=True).order_by("name", "id")
                    ],
                }
                for company in stores
            ]
        }
    )


@api_view(["GET"])
@permission_classes([AllowAny])
def catalog_view(request, company_id):
    company = Company.objects.filter(pk=company_id, is_active=True).first()
    if company is None:
        return Response({"detail": "La tienda no existe o no está publicada."}, status=status.HTTP_404_NOT_FOUND)

    products = (
        Product.objects.filter(company=company, status=Product.Status.ACTIVE)
        .select_related("category", "brand", "company")
        .prefetch_related("variants")
    )
    search = request.query_params.get("search", "").strip()
    category_raw = request.query_params.get("category", "").strip()

    if search:
        products = products.filter(
            Q(name__icontains=search)
            | Q(description__icontains=search)
            | Q(brand__name__icontains=search)
            | Q(variants__sku__icontains=search)
        ).distinct()

    if category_raw:
        if not category_raw.isdecimal():
            return Response({"category": ["La categoría debe ser un entero válido."]}, status=status.HTTP_400_BAD_REQUEST)
        products = products.filter(category_id=int(category_raw))

    products = products.filter(variants__status=ProductVariant.Status.ACTIVE).distinct().order_by("name", "id")
    categories = Category.objects.filter(company=company, products__status=Product.Status.ACTIVE).distinct().order_by("name", "id")

    return Response(
        {
            "store": {"id": company.id, "name": company.name, "business_activity": company.business_activity},
            "categories": [{"id": item.id, "name": item.name} for item in categories],
            "products": [_serialize_product(product) for product in products],
        }
    )


@api_view(["GET"])
@permission_classes([AllowAny])
def product_detail_view(request, company_id, product_id):
    product = (
        Product.objects.filter(
            pk=product_id,
            company_id=company_id,
            company__is_active=True,
            status=Product.Status.ACTIVE,
            variants__status=ProductVariant.Status.ACTIVE,
        )
        .select_related("company", "category", "brand")
        .prefetch_related("variants")
        .distinct()
        .first()
    )
    if product is None:
        return Response({"detail": "El producto no existe o no está publicado."}, status=status.HTTP_404_NOT_FOUND)
    return Response({"product": _serialize_product(product, detailed=True)})


@csrf_protect
@api_view(["POST"])
@permission_classes([AllowAny])
def register_view(request):
    serializer = PortalRegistrationSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    try:
        user, account = register_portal_customer(**serializer.validated_data)
    except PortalConflictError as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
    login(request, user)
    return Response(
        {
            "user": {"id": user.id, "username": user.username, "email": user.email, "first_name": user.first_name, "last_name": user.last_name},
            "account": (
                {
                    "company": account.company_id,
                    "company_name": account.company.name,
                    "customer": account.customer_id,
                }
                if account is not None
                else None
            ),
        },
        status=status.HTTP_201_CREATED,
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def account_view(request):
    accounts = (
        CustomerPortalAccount.objects.filter(
            user=request.user,
            status=CustomerPortalAccount.Status.ACTIVE,
            company__is_active=True,
        )
        .select_related("company", "customer")
        .order_by("company__name", "id")
    )
    return Response(
        {
            "accounts": [
                {
                    "company": account.company_id,
                    "company_name": account.company.name,
                    "customer": account.customer_id,
                    "customer_name": account.customer.name,
                    "email": account.customer.email,
                    "phone": account.customer.phone,
                    "address": account.customer.address,
                    "commune": account.customer.commune,
                    "city": account.customer.city,
                }
                for account in accounts
            ]
        }
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def order_history_view(request):
    orders = (
        Order.objects.filter(
            customer__portal_account__user=request.user,
            customer__portal_account__status=CustomerPortalAccount.Status.ACTIVE,
        )
        .select_related("company", "branch", "warehouse", "customer", "created_by")
        .prefetch_related("items__variant__product", "items__stock_movements__inventory_movement")
        .order_by("-created_at", "-id")
    )
    company_raw = request.query_params.get("company", "").strip()
    if company_raw:
        if not company_raw.isdecimal():
            return Response({"company": ["La empresa debe ser un entero válido."]}, status=status.HTTP_400_BAD_REQUEST)
        orders = orders.filter(company_id=int(company_raw))
    return Response({"orders": OrderSerializer(orders, many=True).data})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def order_detail_view(request, order_id):
    order = (
        Order.objects.filter(
            pk=order_id,
            customer__portal_account__user=request.user,
            customer__portal_account__status=CustomerPortalAccount.Status.ACTIVE,
        )
        .select_related("company", "branch", "warehouse", "customer", "created_by")
        .prefetch_related("items__variant__product", "items__stock_movements__inventory_movement")
        .first()
    )
    if order is None:
        return Response({"detail": "El pedido no existe en tu historial."}, status=status.HTTP_404_NOT_FOUND)
    return Response({"order": OrderSerializer(order).data})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_order_view(request):
    idempotency_key = request.headers.get("Idempotency-Key", "").strip()
    if not idempotency_key:
        return Response({"detail": "Idempotency-Key es obligatorio."}, status=status.HTTP_400_BAD_REQUEST)
    if len(idempotency_key) > 100:
        return Response({"detail": "Idempotency-Key es demasiado largo."}, status=status.HTTP_400_BAD_REQUEST)

    serializer = PortalOrderCreateSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    try:
        order, created = create_portal_order(
            user=request.user,
            idempotency_key=idempotency_key,
            **serializer.validated_data,
        )
    except PortalConflictError as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
    except PortalStockError as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)

    order = (
        Order.objects.filter(pk=order.pk)
        .select_related("company", "branch", "warehouse", "customer", "created_by")
        .prefetch_related("items__variant__product", "items__stock_movements__inventory_movement")
        .get()
    )
    return Response(
        {"order": OrderSerializer(order).data, "idempotent_replay": not created},
        status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
    )
