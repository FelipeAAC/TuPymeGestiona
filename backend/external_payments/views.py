import hashlib
import json
import os

from django.conf import settings
from django.db import IntegrityError
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from orders.models import Order

from .models import MercadoPagoEvent, MercadoPagoWebhookReceipt
from .provider import (
    MercadoPagoClient,
    MercadoPagoNotConfigured,
    MercadoPagoProviderError,
    MercadoPagoUncertainError,
    validate_webhook_signature,
)
from .services import (
    MercadoPagoConflictError,
    MercadoPagoOwnershipError,
    apply_payment_payload,
    checkout_summary,
    create_or_get_checkout,
    get_customer_checkout,
    list_customer_checkouts,
    refresh_checkout_payment,
    resolve_uncertain_preference,
)


def _owned_order(request, order_id):
    order = Order.objects.filter(pk=order_id).select_related("company", "customer").prefetch_related("items__variant__product").first()
    if order is None:
        return None
    try:
        get_customer_checkout(user=request.user, order=order)
    except MercadoPagoOwnershipError:
        return None
    return order


def _error(exc, *, default_status=status.HTTP_409_CONFLICT):
    if isinstance(exc, MercadoPagoNotConfigured):
        return Response({"detail": str(exc), "code": "MERCADO_PAGO_NOT_CONFIGURED"}, status=status.HTTP_409_CONFLICT)
    if isinstance(exc, MercadoPagoProviderError):
        return Response({"detail": exc.detail, "code": exc.code}, status=status.HTTP_502_BAD_GATEWAY)
    if isinstance(exc, MercadoPagoUncertainError):
        return Response({"detail": str(exc), "code": "MERCADO_PAGO_UNCERTAIN"}, status=status.HTTP_409_CONFLICT)
    return Response({"detail": str(exc)}, status=default_status)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def checkout_list_view(request):
    return Response({"payments": [checkout_summary(item) for item in list_customer_checkouts(user=request.user)]})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def checkout_detail_view(request, order_id):
    order = Order.objects.filter(pk=order_id).select_related("company", "customer").first()
    if order is None:
        return Response({"detail": "El pedido no existe."}, status=status.HTTP_404_NOT_FOUND)
    try:
        checkout = get_customer_checkout(user=request.user, order=order)
    except MercadoPagoOwnershipError:
        return Response({"detail": "El pedido no existe en tu cuenta."}, status=status.HTTP_404_NOT_FOUND)
    return Response({"payment": checkout_summary(checkout) if checkout else None})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_preference_view(request, order_id):
    idempotency_key = request.headers.get("Idempotency-Key", "").strip()
    if not idempotency_key or len(idempotency_key) > 100:
        return Response({"detail": "Idempotency-Key es obligatorio y admite hasta 100 caracteres."}, status=status.HTTP_400_BAD_REQUEST)
    order = Order.objects.filter(pk=order_id).select_related("company", "customer").prefetch_related("items__variant__product").first()
    if order is None:
        return Response({"detail": "El pedido no existe."}, status=status.HTTP_404_NOT_FOUND)
    try:
        checkout, created = create_or_get_checkout(user=request.user, order=order, idempotency_key=idempotency_key)
    except MercadoPagoOwnershipError:
        return Response({"detail": "El pedido no existe en tu cuenta."}, status=status.HTTP_404_NOT_FOUND)
    except (MercadoPagoConflictError, MercadoPagoNotConfigured, MercadoPagoProviderError, MercadoPagoUncertainError) as exc:
        return _error(exc)
    return Response({"payment": checkout_summary(checkout), "idempotent_replay": not created}, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def resolve_preference_view(request, order_id):
    order = Order.objects.filter(pk=order_id).select_related("company", "customer").first()
    if order is None:
        return Response({"detail": "El pedido no existe."}, status=status.HTTP_404_NOT_FOUND)
    try:
        checkout, resolved = resolve_uncertain_preference(user=request.user, order=order)
    except MercadoPagoOwnershipError:
        return Response({"detail": "El pedido no existe en tu cuenta."}, status=status.HTTP_404_NOT_FOUND)
    except (MercadoPagoConflictError, MercadoPagoNotConfigured, MercadoPagoProviderError) as exc:
        return _error(exc)
    return Response({"payment": checkout_summary(checkout), "resolved": resolved})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def refresh_payment_view(request, order_id):
    payment_id = str(request.data.get("payment_id") or "").strip()
    if not payment_id:
        return Response({"detail": "payment_id es obligatorio."}, status=status.HTTP_400_BAD_REQUEST)
    order = Order.objects.filter(pk=order_id).select_related("company", "customer").first()
    if order is None:
        return Response({"detail": "El pedido no existe."}, status=status.HTTP_404_NOT_FOUND)
    try:
        checkout = refresh_checkout_payment(user=request.user, order=order, payment_id=payment_id)
    except MercadoPagoOwnershipError:
        return Response({"detail": "El pedido no existe en tu cuenta."}, status=status.HTTP_404_NOT_FOUND)
    except (MercadoPagoConflictError, MercadoPagoNotConfigured, MercadoPagoProviderError) as exc:
        return _error(exc)
    return Response({"payment": checkout_summary(checkout)})


@csrf_exempt
@api_view(["POST"])
@permission_classes([AllowAny])
def webhook_view(request):
    if not settings.MERCADO_PAGO_ENABLED:
        return Response({"detail": "Mercado Pago está deshabilitado."}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
    data_id = str(request.query_params.get("data.id") or request.query_params.get("data_id") or (request.data.get("data") or {}).get("id") or "")
    request_id = request.headers.get("x-request-id", "")
    x_signature = request.headers.get("x-signature", "")
    secret_env = settings.MERCADO_PAGO_WEBHOOK_SECRET_ENV.strip()
    secret = os.getenv(secret_env, "").strip() if secret_env else ""
    if not validate_webhook_signature(x_signature=x_signature, x_request_id=request_id, data_id=data_id, secret=secret):
        return Response({"detail": "Firma webhook inválida."}, status=status.HTTP_401_UNAUTHORIZED)
    if str(request.data.get("type") or request.query_params.get("type") or "") != "payment":
        return Response(status=status.HTTP_200_OK)
    notification_id = str(request.data.get("id") or f"request:{request_id}:{data_id}")[:100]
    payload_hash = hashlib.sha256(json.dumps(request.data, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")).hexdigest()
    try:
        receipt, created = MercadoPagoWebhookReceipt.objects.get_or_create(
            notification_id=notification_id,
            defaults={"request_id": request_id[:100], "data_id": data_id[:100], "payload_hash": payload_hash},
        )
    except IntegrityError:
        return Response(status=status.HTTP_200_OK)
    if not created:
        return Response(status=status.HTTP_200_OK)
    try:
        client = MercadoPagoClient()
        remote = client.get_payment(data_id)
        checkout, payment, _ = apply_payment_payload(payload=remote, correlation_id=request_id)
        if checkout:
            MercadoPagoEvent.objects.create(
                checkout=checkout,
                event_type=MercadoPagoEvent.EventType.WEBHOOK_RECEIVED,
                provider_payment=payment,
                correlation_id=request_id[:100],
                metadata={"notification_id": notification_id},
            )
        receipt.result = "PROCESSED" if checkout else "IGNORED"
        receipt.save(update_fields=("result",))
    except MercadoPagoConflictError:
        receipt.result = "REJECTED"
        receipt.save(update_fields=("result",))
        return Response({"detail": "Pago remoto inconsistente."}, status=status.HTTP_409_CONFLICT)
    except (MercadoPagoNotConfigured, MercadoPagoProviderError):
        receipt.result = "PROVIDER_ERROR"
        receipt.save(update_fields=("result",))
        return Response({"detail": "No fue posible consultar el pago."}, status=status.HTTP_502_BAD_GATEWAY)
    return Response(status=status.HTTP_200_OK)
