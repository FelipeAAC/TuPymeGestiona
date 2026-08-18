from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from organizations.authorization import has_permission
from organizations.models import CompanyMembership

from catalog.models import Product
from catalog.serializers import ProductSerializer


PRODUCTS_VIEW_PERMISSION_CODE = "catalog.products.view"


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def product_list_view(request):
    company_id = request.query_params.get("company")

    if not company_id:
        return Response(
            {
                "detail": "El parametro company es obligatorio.",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        company_id = int(company_id)
    except (TypeError, ValueError):
        return Response(
            {
                "detail": "El parametro company debe ser un entero valido.",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    if company_id <= 0:
        return Response(
            {
                "detail": "El parametro company debe ser un entero valido.",
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
