from django.shortcuts import render

# Create your views here.
from django.contrib.auth import authenticate, login, logout
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from accounts.models import User
from accounts.serializers import CurrentUserSerializer, LoginSerializer


def resolve_username(identifier: str) -> str:
    user = User.objects.filter(username=identifier).only("username").first()

    if user is not None:
        return user.username

    user = User.objects.filter(email__iexact=identifier).only("username").first()

    if user is not None:
        return user.username

    return identifier


@ensure_csrf_cookie
@api_view(["GET"])
@permission_classes([AllowAny])
def csrf_cookie(request):
    return Response(
        {
            "detail": "CSRF cookie set.",
        }
    )


@csrf_protect
@api_view(["POST"])
@permission_classes([AllowAny])
def login_view(request):
    serializer = LoginSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    identifier = serializer.validated_data["identifier"]
    password = serializer.validated_data["password"]
    remember_me = serializer.validated_data["remember_me"]

    username = resolve_username(identifier)

    user = authenticate(
        request=request,
        username=username,
        password=password,
    )

    if user is None:
        return Response(
            {
                "detail": "Credenciales inválidas.",
            },
            status=status.HTTP_401_UNAUTHORIZED,
        )

    login(request, user)

    if remember_me:
        request.session.set_expiry(None)
    else:
        request.session.set_expiry(0)

    return Response(
        {
            "user": CurrentUserSerializer(user).data,
        },
        status=status.HTTP_200_OK,
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def me_view(request):
    return Response(
        {
            "user": CurrentUserSerializer(request.user).data,
        }
    )


@csrf_protect
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def logout_view(request):
    logout(request)

    return Response(status=status.HTTP_204_NO_CONTENT)
