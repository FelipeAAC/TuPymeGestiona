from django.core.exceptions import ValidationError
from django.core.paginator import EmptyPage, Paginator
from django.db.models import Q

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from catalog.models import ProductVariant
from customers.models import Customer
from organizations.authorization import has_permission
from organizations.models import (
    Branch,
    CompanyMembership,
    RoleAssignment,
    Warehouse,
)

from .models import Order
from .serializers import (
    OrderCreateSerializer,
    OrderListQuerySerializer,
    OrderSerializer,
    OrderUpdateSerializer,
)
from .services import (
    OrderNotEditableError,
    OrderTransitionError,
    cancel_order,
    confirm_order,
    create_draft_order,
    deliver_order,
    prepare_order,
    update_draft_order,
)


ORDERS_MANAGE_PERMISSION_CODE = "orders.manage"


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


def _resolve_membership(*, request, source, location):
    raw_company_id = source.get("company")

    if raw_company_id in (None, ""):
        return None, Response(
            {
                "detail": (
                    f"El {location} company es obligatorio."
                ),
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    company_id = _parse_company_id(raw_company_id)

    if company_id is None:
        return None, Response(
            {
                "detail": (
                    f"El {location} company debe ser un entero valido."
                ),
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    membership = _get_active_membership(
        user=request.user,
        company_id=company_id,
    )

    if membership is None:
        return None, Response(
            {
                "detail": "No tienes acceso a esta empresa.",
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    return membership, None


def _get_order_assignments(*, user, company):
    return RoleAssignment.objects.filter(
        membership__user=user,
        membership__company=company,
        membership__status=CompanyMembership.Status.ACTIVE,
        role__company=company,
        role__permission_links__permission__code=(
            ORDERS_MANAGE_PERMISSION_CODE
        ),
        role__status="ACTIVE",
    ).distinct()


def _get_authorized_orders(*, user, company):
    assignments = _get_order_assignments(
        user=user,
        company=company,
    )

    orders = Order.objects.filter(
        company=company,
    )

    if not assignments.exists():
        return orders.none()

    if not assignments.filter(branch__isnull=True).exists():
        branch_ids = assignments.values_list(
            "branch_id",
            flat=True,
        )
        orders = orders.filter(
            branch_id__in=branch_ids,
        )

    return orders.select_related(
        "company",
        "branch",
        "warehouse",
        "customer",
        "created_by",
    ).prefetch_related(
        "items__variant__product",
        "items__stock_movements__inventory_movement",
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def order_options_view(request):
    membership, error_response = _resolve_membership(
        request=request,
        source=request.query_params,
        location="parametro",
    )

    if error_response is not None:
        return error_response

    company = membership.company
    assignments = _get_order_assignments(
        user=request.user,
        company=company,
    )
    can_manage = assignments.exists()

    branches = Branch.objects.none()
    warehouses = Warehouse.objects.none()
    customers = Customer.objects.none()
    variants = ProductVariant.objects.none()

    if can_manage:
        branches = Branch.objects.filter(company=company)

        if not assignments.filter(branch__isnull=True).exists():
            branch_ids = assignments.values_list(
                "branch_id",
                flat=True,
            )
            branches = branches.filter(id__in=branch_ids)
            warehouses = Warehouse.objects.filter(
                company=company,
            ).filter(
                Q(branch_id__in=branch_ids)
                | Q(branch__isnull=True)
            )
        else:
            warehouses = Warehouse.objects.filter(company=company)

        customers = Customer.objects.filter(
            company=company,
            status=Customer.Status.ACTIVE,
        )
        variants = ProductVariant.objects.filter(
            product__company=company,
            status=ProductVariant.Status.ACTIVE,
        ).select_related("product")

    return Response(
        {
            "permissions": {
                "manage": can_manage,
            },
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
                    "branch": warehouse.branch_id,
                    "code": warehouse.code,
                    "name": warehouse.name,
                }
                for warehouse in warehouses.order_by("name", "id")
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
                    "product": variant.product_id,
                    "product_name": variant.product.name,
                    "sku": variant.sku,
                    "base_price": variant.base_price,
                }
                for variant in variants.order_by(
                    "product__name",
                    "sku",
                    "id",
                )
            ],
        }
    )


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def order_list_create_view(request):
    if request.method == "POST":
        return _create_order(request)

    return _list_orders(request)


@api_view(["GET", "PATCH"])
@permission_classes([IsAuthenticated])
def order_detail_view(request, order_id):
    if request.method == "PATCH":
        return _update_order(
            request,
            order_id=order_id,
        )

    return _retrieve_order(
        request,
        order_id=order_id,
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def order_confirm_view(request, order_id):
    return _transition_order(
        request,
        order_id=order_id,
        transition=confirm_order,
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def order_prepare_view(request, order_id):
    return _transition_order(
        request,
        order_id=order_id,
        transition=prepare_order,
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def order_deliver_view(request, order_id):
    return _transition_order(
        request,
        order_id=order_id,
        transition=deliver_order,
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def order_cancel_view(request, order_id):
    return _transition_order(
        request,
        order_id=order_id,
        transition=cancel_order,
    )


def _list_orders(request):
    membership, error_response = _resolve_membership(
        request=request,
        source=request.query_params,
        location="parametro",
    )

    if error_response is not None:
        return error_response

    query_serializer = OrderListQuerySerializer(
        data=request.query_params,
    )
    query_serializer.is_valid(raise_exception=True)
    query = query_serializer.validated_data

    orders = _get_authorized_orders(
        user=request.user,
        company=membership.company,
    )

    if query.get("status"):
        orders = orders.filter(status=query["status"])

    if query.get("branch"):
        orders = orders.filter(branch_id=query["branch"])

    if query.get("customer"):
        orders = orders.filter(customer_id=query["customer"])

    if query.get("search"):
        search = query["search"]
        search_filter = (
            Q(customer__code__icontains=search)
            | Q(customer__name__icontains=search)
            | Q(notes__icontains=search)
        )

        if search.isdecimal():
            search_filter |= Q(number=int(search))

        orders = orders.filter(search_filter)

    ordering = query["ordering"]
    ordering_direction = "-" if ordering.startswith("-") else ""
    orders = orders.order_by(
        ordering,
        f"{ordering_direction}id",
    )

    paginator = Paginator(
        orders,
        query["page_size"],
    )

    try:
        order_page = paginator.page(query["page"])
    except EmptyPage:
        return Response(
            {
                "page": ["La pagina solicitada no existe."],
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    return Response(
        {
            "orders": OrderSerializer(
                order_page.object_list,
                many=True,
            ).data,
            "pagination": {
                "count": paginator.count,
                "page": order_page.number,
                "page_size": query["page_size"],
                "total_pages": paginator.num_pages,
                "next_page": (
                    order_page.next_page_number()
                    if order_page.has_next()
                    else None
                ),
                "previous_page": (
                    order_page.previous_page_number()
                    if order_page.has_previous()
                    else None
                ),
            },
        }
    )


def _create_order(request):
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

    serializer = OrderCreateSerializer(
        data=payload,
        context={
            "company": company,
        },
    )
    serializer.is_valid(raise_exception=True)

    branch = serializer.validated_data["branch"]

    if not has_permission(
        user=request.user,
        company=company,
        permission_code=ORDERS_MANAGE_PERMISSION_CODE,
        branch=branch,
    ):
        return Response(
            {
                "detail": (
                    "No tienes permiso para administrar "
                    "pedidos de esta sucursal."
                ),
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    try:
        order = create_draft_order(
            company=company,
            branch=branch,
            warehouse=serializer.validated_data["warehouse"],
            customer=serializer.validated_data["customer"],
            notes=serializer.validated_data["notes"],
            items=serializer.validated_data["items"],
            created_by=request.user,
        )
    except ValidationError as error:
        return Response(
            {
                "detail": error.message_dict,
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    order = _get_authorized_orders(
        user=request.user,
        company=company,
    ).get(pk=order.pk)

    return Response(
        {
            "order": OrderSerializer(order).data,
        },
        status=status.HTTP_201_CREATED,
    )


def _retrieve_order(request, *, order_id):
    membership, error_response = _resolve_membership(
        request=request,
        source=request.query_params,
        location="parametro",
    )

    if error_response is not None:
        return error_response

    order = _get_authorized_orders(
        user=request.user,
        company=membership.company,
    ).filter(pk=order_id).first()

    if order is None:
        return Response(
            {
                "detail": "El pedido no existe en el alcance autorizado.",
            },
            status=status.HTTP_404_NOT_FOUND,
        )

    return Response(
        {
            "order": OrderSerializer(order).data,
        }
    )


def _transition_order(request, *, order_id, transition):
    membership, error_response = _resolve_membership(
        request=request,
        source=request.data,
        location="campo",
    )

    if error_response is not None:
        return error_response

    company = membership.company
    order = _get_authorized_orders(
        user=request.user,
        company=company,
    ).filter(pk=order_id).first()

    if order is None:
        return Response(
            {
                "detail": "El pedido no existe en el alcance autorizado.",
            },
            status=status.HTTP_404_NOT_FOUND,
        )

    try:
        order = transition(
            order=order,
            performed_by=request.user,
        )
    except OrderTransitionError as error:
        return Response(
            {
                "detail": error.detail,
            },
            status=status.HTTP_409_CONFLICT,
        )
    except ValidationError as error:
        return Response(
            {
                "detail": error.message_dict,
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    order = _get_authorized_orders(
        user=request.user,
        company=company,
    ).get(pk=order.pk)

    return Response(
        {
            "order": OrderSerializer(order).data,
        }
    )

def _update_order(request, *, order_id):
    membership, error_response = _resolve_membership(
        request=request,
        source=request.data,
        location="campo",
    )

    if error_response is not None:
        return error_response

    company = membership.company
    order = _get_authorized_orders(
        user=request.user,
        company=company,
    ).filter(pk=order_id).first()

    if order is None:
        return Response(
            {
                "detail": "El pedido no existe en el alcance autorizado.",
            },
            status=status.HTTP_404_NOT_FOUND,
        )

    if order.status != Order.Status.DRAFT:
        return Response(
            {
                "detail": "Solo se pueden editar pedidos en borrador.",
            },
            status=status.HTTP_409_CONFLICT,
        )

    payload = request.data.copy()
    payload.pop("company", None)
    replace_items = "items" in payload

    serializer = OrderUpdateSerializer(
        order,
        data=payload,
        partial=True,
    )
    serializer.is_valid(raise_exception=True)

    final_branch = serializer.validated_data.get(
        "branch",
        order.branch,
    )

    if not has_permission(
        user=request.user,
        company=company,
        permission_code=ORDERS_MANAGE_PERMISSION_CODE,
        branch=final_branch,
    ):
        return Response(
            {
                "detail": (
                    "No tienes permiso para mover el pedido "
                    "a esta sucursal."
                ),
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    try:
        order = update_draft_order(
            order=order,
            validated_data=dict(serializer.validated_data),
            replace_items=replace_items,
        )
    except OrderNotEditableError:
        return Response(
            {
                "detail": "Solo se pueden editar pedidos en borrador.",
            },
            status=status.HTTP_409_CONFLICT,
        )
    except ValidationError as error:
        return Response(
            {
                "detail": error.message_dict,
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    order = _get_authorized_orders(
        user=request.user,
        company=company,
    ).get(pk=order.pk)

    return Response(
        {
            "order": OrderSerializer(order).data,
        }
    )
