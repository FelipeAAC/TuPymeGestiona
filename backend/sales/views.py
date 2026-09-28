from django.core.exceptions import ValidationError
from django.core.paginator import EmptyPage, Paginator
from django.db.models import Q, Sum

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from administration.models import PaymentMethod
from catalog.models import Product, ProductVariant
from customers.models import Customer
from inventory.models import InventoryStock
from orders.models import Order
from organizations.authorization import has_permission
from organizations.models import (
    Branch,
    CompanyMembership,
    RoleAssignment,
    Warehouse,
)

from .models import Sale
from .serializers import (
    PaymentCreateSerializer,
    PaymentSerializer,
    PosSaleCreateSerializer,
    PosSaleOptionsQuerySerializer,
    PosSaleReversalSerializer,
    SaleCreateSerializer,
    SaleListQuerySerializer,
    SaleSerializer,
)
from .services import (
    SaleIdempotencyConflictError,
    SaleTransitionError,
    cancel_sale,
    create_pos_sale,
    create_sale,
    record_payment,
    reverse_pos_sale,
)


SALES_MANAGE_PERMISSION_CODE = "sales.manage"


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


def _resolve_membership(*, request, source, location):
    raw_company_id = source.get("company")

    if raw_company_id in (None, ""):
        return None, Response(
            {"detail": f"El {location} company es obligatorio."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    company_id = _parse_company_id(raw_company_id)

    if company_id is None:
        return None, Response(
            {
                "detail": (
                    f"El {location} company debe ser un entero valido."
                )
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    membership = (
        CompanyMembership.objects.filter(
            user=request.user,
            company_id=company_id,
            status=CompanyMembership.Status.ACTIVE,
        )
        .select_related("company")
        .first()
    )

    if membership is None:
        return None, Response(
            {"detail": "No tienes acceso a esta empresa."},
            status=status.HTTP_403_FORBIDDEN,
        )

    return membership, None


def _get_sales_assignments(*, user, company):
    return RoleAssignment.objects.filter(
        membership__user=user,
        membership__company=company,
        membership__status=CompanyMembership.Status.ACTIVE,
        role__company=company,
        role__permission_links__permission__code=(
            SALES_MANAGE_PERMISSION_CODE
        ),
        role__status="ACTIVE",
    ).distinct()


def _get_authorized_sales(*, user, company):
    assignments = _get_sales_assignments(user=user, company=company)
    sales = Sale.objects.filter(company=company)

    if not assignments.exists():
        return sales.none()

    if not assignments.filter(branch__isnull=True).exists():
        branch_ids = assignments.values_list("branch_id", flat=True)
        sales = sales.filter(branch_id__in=branch_ids)

    return sales.select_related(
        "company",
        "branch",
        "warehouse",
        "customer",
        "order__customer",
        "order__warehouse",
        "created_by",
        "cancelled_by",
    ).prefetch_related(
        "payments",
        "payments__payment_method",
        "events__payment",
        "items",
    )


def _get_authorized_branches(*, assignments, company):
    branches = Branch.objects.filter(company=company)

    if not assignments.exists():
        return branches.none()

    if not assignments.filter(branch__isnull=True).exists():
        branch_ids = assignments.values_list("branch_id", flat=True)
        branches = branches.filter(id__in=branch_ids)

    return branches


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def sale_options_view(request):
    membership, error_response = _resolve_membership(
        request=request,
        source=request.query_params,
        location="parametro",
    )

    if error_response is not None:
        return error_response

    company = membership.company
    query_serializer = PosSaleOptionsQuerySerializer(data=request.query_params)
    query_serializer.is_valid(raise_exception=True)
    options_query = query_serializer.validated_data
    assignments = _get_sales_assignments(
        user=request.user,
        company=company,
    )
    branches = _get_authorized_branches(
        assignments=assignments,
        company=company,
    )
    if options_query.get("branch"):
        if not branches.filter(pk=options_query["branch"]).exists():
            return Response(
                {"detail": "La sucursal no esta en el alcance autorizado."},
                status=status.HTTP_403_FORBIDDEN,
            )
        branches = branches.filter(pk=options_query["branch"])

    warehouses = (
        Warehouse.objects.filter(company=company)
        .filter(Q(branch__in=branches) | Q(branch__isnull=True))
        if assignments.exists()
        else Warehouse.objects.none()
    )
    if options_query.get("warehouse"):
        if not warehouses.filter(pk=options_query["warehouse"]).exists():
            return Response(
                {"detail": "La bodega no esta en el alcance autorizado."},
                status=status.HTTP_403_FORBIDDEN,
            )
        selected_warehouse = warehouses.get(pk=options_query["warehouse"])
    else:
        selected_warehouse = None

    payment_methods = PaymentMethod.objects.filter(
        company=company,
        is_active=True,
        kind__in=(PaymentMethod.Kind.CASH, PaymentMethod.Kind.TRANSFER),
    ) if assignments.exists() else PaymentMethod.objects.none()
    customers = Customer.objects.filter(
        company=company,
        status=Customer.Status.ACTIVE,
    ) if assignments.exists() else Customer.objects.none()

    variants = ProductVariant.objects.none()
    stock_by_variant = {}
    if assignments.exists() and selected_warehouse is not None:
        variants = ProductVariant.objects.filter(
            product__company=company,
            product__status=Product.Status.ACTIVE,
            status=ProductVariant.Status.ACTIVE,
        ).select_related("product")
        if options_query.get("search"):
            search = options_query["search"].strip()
            variants = variants.filter(
                Q(sku__icontains=search) | Q(product__name__icontains=search)
            )
        stock_by_variant = {
            stock.variant_id: stock.quantity
            for stock in InventoryStock.objects.filter(
                warehouse=selected_warehouse,
                variant__in=variants,
            )
        }
    delivered_orders = Order.objects.none()

    if assignments.exists():
        delivered_orders = (
            Order.objects.filter(
                company=company,
                status=Order.Status.DELIVERED,
                sale__isnull=True,
            )
            .filter(branch__in=branches)
            .select_related("branch", "customer")
            .prefetch_related("items")
        )

    return Response(
        {
            "permissions": {"manage": assignments.exists()},
            "branches": [
                {
                    "id": branch.id,
                    "code": branch.code,
                    "name": branch.name,
                }
                for branch in branches.order_by("name", "id")
            ],
            "warehouses": [
                {
                    "id": warehouse.id,
                    "code": warehouse.code,
                    "name": warehouse.name,
                    "branch": warehouse.branch_id,
                }
                for warehouse in warehouses.order_by("name", "id")
            ],
            "payment_methods": [
                {
                    "id": method.id,
                    "code": method.code,
                    "name": method.name,
                    "kind": method.kind,
                }
                for method in payment_methods.order_by("sort_order", "name", "id")
            ],
            "customers": [
                {
                    "id": customer.id,
                    "code": customer.code,
                    "name": customer.name,
                }
                for customer in customers.order_by("name", "id")
            ],
            "variants": [
                {
                    "id": variant.id,
                    "sku": variant.sku,
                    "name": variant.product.name,
                    "unit_price": f"{variant.base_price:.2f}",
                    "stock": f"{stock_by_variant.get(variant.id, 0):.3f}",
                }
                for variant in variants.order_by("product__name", "sku", "id")
            ],
            "delivered_orders": [
                {
                    "id": order.id,
                    "number": order.number,
                    "branch": order.branch_id,
                    "customer": order.customer_id,
                    "customer_code": order.customer.code,
                    "customer_name": order.customer.name,
                    "total": f"{order.total:.2f}",
                }
                for order in delivered_orders.order_by("-number", "-id")
            ],
        }
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def pos_sale_create_view(request):
    membership, error_response = _resolve_membership(
        request=request,
        source=request.data,
        location="campo",
    )
    if error_response is not None:
        return error_response

    company = membership.company
    payload = request.data.copy()
    payload.pop("company", None)
    serializer = PosSaleCreateSerializer(
        data=payload,
        context={"company": company},
    )
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data

    if not has_permission(
        user=request.user,
        company=company,
        permission_code=SALES_MANAGE_PERMISSION_CODE,
        branch=data["branch"],
    ):
        return Response(
            {"detail": "No tienes permiso para administrar ventas de esta sucursal."},
            status=status.HTTP_403_FORBIDDEN,
        )

    try:
        sale, payment, created = create_pos_sale(
            company=company,
            branch=data["branch"],
            warehouse=data["warehouse"],
            customer=data.get("customer"),
            items=data["items"],
            payment_method=data["payment_method"],
            reference=data["reference"],
            idempotency_key=data["idempotency_key"],
            created_by=request.user,
        )
    except (SaleIdempotencyConflictError, SaleTransitionError) as error:
        return Response(
            {"detail": error.detail},
            status=status.HTTP_409_CONFLICT,
        )
    except ValidationError as error:
        return Response(
            {"detail": error.message_dict},
            status=status.HTTP_400_BAD_REQUEST,
        )

    sale = _get_authorized_sales(
        user=request.user,
        company=company,
    ).get(pk=sale.pk)
    return Response(
        {
            "sale": SaleSerializer(sale).data,
            "payment": PaymentSerializer(payment).data,
            "idempotent_replay": not created,
        },
        status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def sale_reverse_view(request, sale_id):
    membership, error_response = _resolve_membership(
        request=request,
        source=request.data,
        location="campo",
    )
    if error_response is not None:
        return error_response

    company = membership.company
    sale = _get_authorized_sales(
        user=request.user,
        company=company,
    ).filter(pk=sale_id).first()
    if sale is None:
        return Response(
            {"detail": "La venta no existe en el alcance autorizado."},
            status=status.HTTP_404_NOT_FOUND,
        )
    serializer = PosSaleReversalSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    if not has_permission(
        user=request.user,
        company=company,
        permission_code=SALES_MANAGE_PERMISSION_CODE,
        branch=sale.branch,
    ):
        return Response(
            {"detail": "No tienes permiso para revertir ventas de esta sucursal."},
            status=status.HTTP_403_FORBIDDEN,
        )

    try:
        sale, reversal, changed = reverse_pos_sale(
            sale=sale,
            reference=serializer.validated_data["reference"],
            performed_by=request.user,
        )
    except (SaleIdempotencyConflictError, SaleTransitionError) as error:
        return Response(
            {"detail": error.detail},
            status=status.HTTP_409_CONFLICT,
        )
    except ValidationError as error:
        return Response(
            {"detail": error.message_dict},
            status=status.HTTP_400_BAD_REQUEST,
        )

    sale = _get_authorized_sales(
        user=request.user,
        company=company,
    ).get(pk=sale.pk)
    return Response(
        {
            "sale": SaleSerializer(sale).data,
            "reversal": {
                "id": reversal.id,
                "amount": f"{reversal.amount:.2f}",
                "reference": reversal.reference,
                "performed_by": reversal.performed_by_id,
                "created_at": reversal.created_at,
            },
            "already_reversed": not changed,
        },
        status=status.HTTP_201_CREATED if changed else status.HTTP_200_OK,
    )


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def sale_list_create_view(request):
    if request.method == "POST":
        return _create_sale(request)
    return _list_sales(request)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def sale_detail_view(request, sale_id):
    membership, error_response = _resolve_membership(
        request=request,
        source=request.query_params,
        location="parametro",
    )

    if error_response is not None:
        return error_response

    sale = _get_authorized_sales(
        user=request.user,
        company=membership.company,
    ).filter(pk=sale_id).first()

    if sale is None:
        return Response(
            {"detail": "La venta no existe en el alcance autorizado."},
            status=status.HTTP_404_NOT_FOUND,
        )

    return Response({"sale": SaleSerializer(sale).data})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def sale_payment_view(request, sale_id):
    membership, error_response = _resolve_membership(
        request=request,
        source=request.data,
        location="campo",
    )

    if error_response is not None:
        return error_response

    company = membership.company
    sale = _get_authorized_sales(
        user=request.user,
        company=company,
    ).filter(pk=sale_id).first()

    if sale is None:
        return Response(
            {"detail": "La venta no existe en el alcance autorizado."},
            status=status.HTTP_404_NOT_FOUND,
        )

    payload = request.data.copy()
    payload.pop("company", None)
    serializer = PaymentCreateSerializer(data=payload)
    serializer.is_valid(raise_exception=True)

    try:
        sale, payment, created = record_payment(
            sale=sale,
            amount=serializer.validated_data["amount"],
            reference=serializer.validated_data["reference"],
            idempotency_key=serializer.validated_data["idempotency_key"],
            performed_by=request.user,
            payment_method=serializer.validated_data.get("payment_method"),
        )
    except (SaleIdempotencyConflictError, SaleTransitionError) as error:
        return Response(
            {"detail": error.detail},
            status=status.HTTP_409_CONFLICT,
        )
    except ValidationError as error:
        return Response(
            {"detail": error.message_dict},
            status=status.HTTP_400_BAD_REQUEST,
        )

    sale = _get_authorized_sales(
        user=request.user,
        company=company,
    ).get(pk=sale.pk)
    return Response(
        {
            "sale": SaleSerializer(sale).data,
            "payment": PaymentSerializer(payment).data,
            "idempotent_replay": not created,
        },
        status=(
            status.HTTP_201_CREATED
            if created
            else status.HTTP_200_OK
        ),
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def sale_cancel_view(request, sale_id):
    membership, error_response = _resolve_membership(
        request=request,
        source=request.data,
        location="campo",
    )

    if error_response is not None:
        return error_response

    company = membership.company
    sale = _get_authorized_sales(
        user=request.user,
        company=company,
    ).filter(pk=sale_id).first()

    if sale is None:
        return Response(
            {"detail": "La venta no existe en el alcance autorizado."},
            status=status.HTTP_404_NOT_FOUND,
        )

    try:
        sale, changed = cancel_sale(
            sale=sale,
            performed_by=request.user,
        )
    except SaleTransitionError as error:
        return Response(
            {"detail": error.detail},
            status=status.HTTP_409_CONFLICT,
        )

    sale = _get_authorized_sales(
        user=request.user,
        company=company,
    ).get(pk=sale.pk)
    return Response(
        {
            "sale": SaleSerializer(sale).data,
            "already_cancelled": not changed,
        }
    )


def _list_sales(request):
    membership, error_response = _resolve_membership(
        request=request,
        source=request.query_params,
        location="parametro",
    )

    if error_response is not None:
        return error_response

    query_serializer = SaleListQuerySerializer(data=request.query_params)
    query_serializer.is_valid(raise_exception=True)
    query = query_serializer.validated_data
    sales = _get_authorized_sales(
        user=request.user,
        company=membership.company,
    )

    if query.get("status"):
        sales = sales.filter(status=query["status"])

    if query.get("branch"):
        sales = sales.filter(branch_id=query["branch"])

    if query.get("customer"):
        sales = sales.filter(customer_id=query["customer"])

    if query.get("search"):
        search = query["search"]
        search_filter = (
            Q(customer__code__icontains=search)
            | Q(customer__name__icontains=search)
            | Q(order__customer__code__icontains=search)
            | Q(order__customer__name__icontains=search)
            | Q(payments__reference__icontains=search)
        )

        if search.isdecimal():
            search_filter |= Q(number=int(search))
            search_filter |= Q(order__number=int(search))

        sales = sales.filter(search_filter).distinct()

    ordering = query["ordering"]
    direction = "-" if ordering.startswith("-") else ""
    sales = sales.order_by(ordering, f"{direction}id")
    paginator = Paginator(sales, query["page_size"])

    try:
        sale_page = paginator.page(query["page"])
    except EmptyPage:
        return Response(
            {"page": ["La pagina solicitada no existe."]},
            status=status.HTTP_400_BAD_REQUEST,
        )

    return Response(
        {
            "sales": SaleSerializer(
                sale_page.object_list,
                many=True,
            ).data,
            "pagination": {
                "count": paginator.count,
                "page": sale_page.number,
                "page_size": query["page_size"],
                "total_pages": paginator.num_pages,
                "next_page": (
                    sale_page.next_page_number()
                    if sale_page.has_next()
                    else None
                ),
                "previous_page": (
                    sale_page.previous_page_number()
                    if sale_page.has_previous()
                    else None
                ),
            },
        }
    )


def _create_sale(request):
    membership, error_response = _resolve_membership(
        request=request,
        source=request.data,
        location="campo",
    )

    if error_response is not None:
        return error_response

    company = membership.company
    payload = request.data.copy()
    payload.pop("company", None)
    serializer = SaleCreateSerializer(
        data=payload,
        context={"company": company},
    )
    serializer.is_valid(raise_exception=True)
    order = serializer.validated_data["order"]

    if not has_permission(
        user=request.user,
        company=company,
        permission_code=SALES_MANAGE_PERMISSION_CODE,
        branch=order.branch,
    ):
        return Response(
            {
                "detail": (
                    "No tienes permiso para administrar ventas "
                    "de esta sucursal."
                )
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    try:
        sale, created = create_sale(
            company=company,
            order=order,
            idempotency_key=serializer.validated_data["idempotency_key"],
            created_by=request.user,
        )
    except (SaleIdempotencyConflictError, SaleTransitionError) as error:
        return Response(
            {"detail": error.detail},
            status=status.HTTP_409_CONFLICT,
        )
    except ValidationError as error:
        return Response(
            {"detail": error.message_dict},
            status=status.HTTP_400_BAD_REQUEST,
        )

    sale = _get_authorized_sales(
        user=request.user,
        company=company,
    ).get(pk=sale.pk)
    return Response(
        {
            "sale": SaleSerializer(sale).data,
            "idempotent_replay": not created,
        },
        status=(
            status.HTTP_201_CREATED
            if created
            else status.HTTP_200_OK
        ),
    )
