from django.core.paginator import EmptyPage, Paginator
from django.db.models import Q

from rest_framework import status
from rest_framework.decorators import (
    api_view,
    permission_classes,
)
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from organizations.authorization import has_permission

from organizations.models import CompanyMembership

from .models import Customer
from .serializers import (
    CustomerCreateSerializer,
    CustomerListQuerySerializer,
    CustomerSerializer,
    CustomerUpdateSerializer,
)


CUSTOMERS_MANAGE_PERMISSION_CODE = (
    "customers.manage"
)


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
def customer_list_create_view(request):

    if request.method == "POST":
        return _create_customer(request)

    return _list_customers(request)


@api_view(["GET", "PATCH"])
@permission_classes([IsAuthenticated])
def customer_detail_view(request, customer_id):

    if request.method == "PATCH":
        return _update_customer(
            request,
            customer_id=customer_id,
        )

    return _retrieve_customer(
        request,
        customer_id=customer_id,
    )



def _list_customers(request):

    raw_company_id = request.query_params.get(
        "company",
    )

    if raw_company_id in (None, ""):
        return Response(
            {
                "detail": (
                    "El parametro company es obligatorio."
                ),
            },
            status=status.HTTP_400_BAD_REQUEST,
        )


    company_id = _parse_company_id(
        raw_company_id,
    )


    if company_id is None:
        return Response(
            {
                "detail": (
                    "El parametro company debe ser un entero valido."
                ),
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
                "detail": (
                    "No tienes acceso a esta empresa."
                ),
            },
            status=status.HTTP_403_FORBIDDEN,
        )


    if not has_permission(
        user=request.user,
        company=membership.company,
        permission_code=(
            CUSTOMERS_MANAGE_PERMISSION_CODE
        ),
    ):
        return Response(
            {
                "detail": (
                    "No tienes permiso para administrar clientes."
                ),
            },
            status=status.HTTP_403_FORBIDDEN,
        )


    customers = Customer.objects.filter(
        company=membership.company,
    )


    query_serializer = CustomerListQuerySerializer(
        data=request.query_params,
    )

    query_serializer.is_valid(
        raise_exception=True,
    )

    query = query_serializer.validated_data


    if query.get("code"):
        customers = customers.filter(
            code__icontains=query["code"],
        )

    if query.get("name"):
        customers = customers.filter(
            name__icontains=query["name"],
        )

    if query.get("tax_id"):
        customers = customers.filter(
            tax_id__icontains=query["tax_id"],
        )

    if query.get("status"):
        customers = customers.filter(
            status=query["status"],
        )

    if query.get("search"):
        search = query["search"]
        customers = customers.filter(
            Q(code__icontains=search)
            | Q(name__icontains=search)
            | Q(tax_id__icontains=search)
            | Q(email__icontains=search)
            | Q(phone__icontains=search)
        )


    ordering = query["ordering"]
    ordering_direction = (
        "-" if ordering.startswith("-") else ""
    )

    customers = customers.order_by(
        ordering,
        f"{ordering_direction}id",
    )


    paginator = Paginator(
        customers,
        query["page_size"],
    )

    try:
        customer_page = paginator.page(
            query["page"],
        )
    except EmptyPage:
        return Response(
            {
                "page": [
                    "La página solicitada no existe.",
                ],
            },
            status=status.HTTP_400_BAD_REQUEST,
        )


    return Response(
        {
            "customers": CustomerSerializer(
                customer_page.object_list,
                many=True,
            ).data,
            "pagination": {
                "count": paginator.count,
                "page": customer_page.number,
                "page_size": query["page_size"],
                "total_pages": paginator.num_pages,
                "next_page": (
                    customer_page.next_page_number()
                    if customer_page.has_next()
                    else None
                ),
                "previous_page": (
                    customer_page.previous_page_number()
                    if customer_page.has_previous()
                    else None
                ),
            },
        }
    )



def _create_customer(request):

    raw_company_id = request.data.get(
        "company",
    )


    if raw_company_id in (None, ""):
        return Response(
            {
                "detail": (
                    "El campo company es obligatorio."
                ),
            },
            status=status.HTTP_400_BAD_REQUEST,
        )


    company_id = _parse_company_id(
        raw_company_id,
    )


    if company_id is None:
        return Response(
            {
                "detail": (
                    "El campo company debe ser un entero valido."
                ),
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
                "detail": (
                    "No tienes acceso a esta empresa."
                ),
            },
            status=status.HTTP_403_FORBIDDEN,
        )


    if not has_permission(
        user=request.user,
        company=membership.company,
        permission_code=(
            CUSTOMERS_MANAGE_PERMISSION_CODE
        ),
    ):
        return Response(
            {
                "detail": (
                    "No tienes permiso para administrar clientes."
                ),
            },
            status=status.HTTP_403_FORBIDDEN,
        )


    company = membership.company

    payload = request.data.copy()
    payload.pop("company", None)


    serializer = CustomerCreateSerializer(
        data=payload,
        context={
            "company": company,
        },
    )


    serializer.is_valid(
        raise_exception=True,
    )


    customer = serializer.save(
        company=company,
    )


    return Response(
        {
            "customer": CustomerSerializer(
                customer,
            ).data,
        },
        status=status.HTTP_201_CREATED,
    )


def _retrieve_customer(request, *, customer_id):

    raw_company_id = request.query_params.get(
        "company",
    )

    if raw_company_id in (None, ""):
        return Response(
            {
                "detail": (
                    "El parametro company es obligatorio."
                ),
            },
            status=status.HTTP_400_BAD_REQUEST,
        )


    company_id = _parse_company_id(
        raw_company_id,
    )


    if company_id is None:
        return Response(
            {
                "detail": (
                    "El parametro company debe ser un entero valido."
                ),
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
                "detail": (
                    "No tienes acceso a esta empresa."
                ),
            },
            status=status.HTTP_403_FORBIDDEN,
        )


    company = membership.company

    if not has_permission(
        user=request.user,
        company=company,
        permission_code=(
            CUSTOMERS_MANAGE_PERMISSION_CODE
        ),
    ):
        return Response(
            {
                "detail": (
                    "No tienes permiso para administrar clientes."
                ),
            },
            status=status.HTTP_403_FORBIDDEN,
        )


    customer = Customer.objects.filter(
        pk=customer_id,
        company=company,
    ).first()


    if customer is None:
        return Response(
            {
                "detail": (
                    "El cliente no existe en esta empresa."
                ),
            },
            status=status.HTTP_404_NOT_FOUND,
        )


    return Response(
        {
            "customer": CustomerSerializer(
                customer,
            ).data,
        }
    )


def _update_customer(request, *, customer_id):

    raw_company_id = request.data.get(
        "company",
    )

    if raw_company_id in (None, ""):
        return Response(
            {
                "detail": (
                    "El campo company es obligatorio."
                ),
            },
            status=status.HTTP_400_BAD_REQUEST,
        )


    company_id = _parse_company_id(
        raw_company_id,
    )


    if company_id is None:
        return Response(
            {
                "detail": (
                    "El campo company debe ser un entero valido."
                ),
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
                "detail": (
                    "No tienes acceso a esta empresa."
                ),
            },
            status=status.HTTP_403_FORBIDDEN,
        )


    company = membership.company

    if not has_permission(
        user=request.user,
        company=company,
        permission_code=(
            CUSTOMERS_MANAGE_PERMISSION_CODE
        ),
    ):
        return Response(
            {
                "detail": (
                    "No tienes permiso para administrar clientes."
                ),
            },
            status=status.HTTP_403_FORBIDDEN,
        )


    customer = Customer.objects.filter(
        pk=customer_id,
        company=company,
    ).first()


    if customer is None:
        return Response(
            {
                "detail": (
                    "El cliente no existe en esta empresa."
                ),
            },
            status=status.HTTP_404_NOT_FOUND,
        )


    payload = request.data.copy()
    payload.pop("company", None)

    serializer = CustomerUpdateSerializer(
        customer,
        data=payload,
        partial=True,
    )

    serializer.is_valid(
        raise_exception=True,
    )

    customer = serializer.save()


    return Response(
        {
            "customer": CustomerSerializer(
                customer,
            ).data,
        }
    )
