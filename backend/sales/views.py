from django.core.exceptions import ValidationError
from django.core.paginator import EmptyPage, Paginator
from django.db.models import Q

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from orders.models import Order
from organizations.authorization import has_permission
from organizations.models import (
    Branch,
    CompanyMembership,
    RoleAssignment,
)

from .models import Sale
from .serializers import (
    PaymentCreateSerializer,
    PaymentSerializer,
    SaleCreateSerializer,
    SaleListQuerySerializer,
    SaleSerializer,
)
from .services import (
    SaleIdempotencyConflictError,
    SaleTransitionError,
    cancel_sale,
    create_sale,
    record_payment,
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
        "order__customer",
        "created_by",
        "cancelled_by",
    ).prefetch_related(
        "payments",
        "events__payment",
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
    assignments = _get_sales_assignments(
        user=request.user,
        company=company,
    )
    branches = _get_authorized_branches(
        assignments=assignments,
        company=company,
    )
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
        sales = sales.filter(order__customer_id=query["customer"])

    if query.get("search"):
        search = query["search"]
        search_filter = (
            Q(order__customer__code__icontains=search)
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
