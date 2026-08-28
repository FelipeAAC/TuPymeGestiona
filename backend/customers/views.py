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
    CustomerSerializer,
    CustomerCreateSerializer,
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


    return Response(
        {
            "customers": CustomerSerializer(
                customers,
                many=True,
            ).data,
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


    serializer = CustomerCreateSerializer(
        data=request.data,
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
        },
        status=status.HTTP_201_CREATED,
    )
