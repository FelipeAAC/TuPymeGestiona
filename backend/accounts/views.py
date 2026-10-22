from urllib.parse import urlencode

from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.tokens import default_token_generator
from django.db import transaction
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from accounts.models import User
from accounts.serializers import (
    CurrentUserSerializer,
    LoginSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
)
from django.conf import settings
from transactional_notifications.services import enqueue_password_reset_notification


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


PASSWORD_RESET_DETAIL = "Si existe una cuenta con ese correo, recibirás instrucciones para restablecer tu contraseña."


def _password_reset_url(user):
    base = settings.PASSWORD_RESET_FRONTEND_BASE_URL.rstrip("/?")
    separator = "&" if "?" in base else "?"
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    return f"{base}{separator}{urlencode({'uid': uid, 'token': token})}"


@csrf_protect
@api_view(["POST"])
@permission_classes([AllowAny])
def password_reset_request_view(request):
    serializer = PasswordResetRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    user = (
        User.objects.filter(
            email__iexact=serializer.validated_data["email"],
            is_active=True,
        )
        .order_by("id")
        .first()
    )
    if user is not None:
        enqueue_password_reset_notification(user, _password_reset_url(user))
    return Response({"detail": PASSWORD_RESET_DETAIL}, status=status.HTTP_202_ACCEPTED)


@csrf_protect
@api_view(["POST"])
@permission_classes([AllowAny])
def password_reset_confirm_view(request):
    serializer = PasswordResetConfirmSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    user = serializer.validated_data["user"]
    with transaction.atomic():
        user = User.objects.select_for_update().get(pk=user.pk, is_active=True)
        if not default_token_generator.check_token(user, serializer.validated_data["token"]):
            return Response(
                {"detail": "El enlace de recuperación no es válido o expiró."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        user.set_password(serializer.validated_data["password"])
        user.save(update_fields=("password",))
    return Response(status=status.HTTP_204_NO_CONTENT)
