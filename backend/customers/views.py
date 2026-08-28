from rest_framework import status
from rest_framework.response import Response
from rest_framework.decorators import api_view

from .models import Customer
from .serializers import (
    CustomerSerializer,
    CustomerCreateSerializer,
)


@api_view(["GET", "POST"])
def customer_list_create_view(request):

    if request.method == "GET":

        customers = Customer.objects.all()

        serializer = CustomerSerializer(
            customers,
            many=True,
        )

        return Response(
            serializer.data,
        )

    serializer = CustomerCreateSerializer(
        data=request.data,
    )

    if serializer.is_valid():

        customer = serializer.save()

        return Response(
            CustomerSerializer(customer).data,
            status=status.HTTP_201_CREATED,
        )

    return Response(
        serializer.errors,
        status=status.HTTP_400_BAD_REQUEST,
    )
