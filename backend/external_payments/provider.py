import hashlib
import hmac
import os
from urllib.parse import urlparse

import requests
from django.conf import settings


class MercadoPagoNotConfigured(Exception):
    pass


class MercadoPagoProviderError(Exception):
    def __init__(self, detail, code="PROVIDER_ERROR"):
        self.detail = detail
        self.code = code
        super().__init__(detail)


class MercadoPagoUncertainError(Exception):
    pass


def _secret_from_env(setting_name):
    env_name = getattr(settings, setting_name, "").strip()
    return os.getenv(env_name, "").strip() if env_name else ""


def validate_public_configuration():
    if not settings.MERCADO_PAGO_ENABLED:
        raise MercadoPagoNotConfigured("Mercado Pago Sandbox no está habilitado.")
    token = _secret_from_env("MERCADO_PAGO_ACCESS_TOKEN_ENV")
    if not token:
        raise MercadoPagoNotConfigured("Falta el Access Token de prueba de Mercado Pago.")
    return_base = settings.MERCADO_PAGO_RETURN_BASE_URL.strip().rstrip("/")
    webhook_url = settings.MERCADO_PAGO_WEBHOOK_URL.strip()
    for label, value in (("MERCADO_PAGO_RETURN_BASE_URL", return_base), ("MERCADO_PAGO_WEBHOOK_URL", webhook_url)):
        parsed = urlparse(value)
        if parsed.scheme != "https" or not parsed.netloc:
            raise MercadoPagoNotConfigured(f"{label} debe ser una URL HTTPS pública.")
        if parsed.hostname in {"localhost", "127.0.0.1"}:
            raise MercadoPagoNotConfigured(f"{label} no puede usar localhost para Checkout Pro.")
    return token, return_base, webhook_url


class MercadoPagoClient:
    def __init__(self, session=None):
        self.session = session or requests.Session()
        self.token, self.return_base, self.webhook_url = validate_public_configuration()
        self.base_url = settings.MERCADO_PAGO_API_BASE_URL.rstrip("/")
        self.timeout = settings.MERCADO_PAGO_HTTP_TIMEOUT

    @property
    def headers(self):
        return {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json", "Accept": "application/json"}

    def _json(self, response):
        try:
            payload = response.json()
        except ValueError as exc:
            raise MercadoPagoProviderError("Mercado Pago respondió contenido no JSON.", "INVALID_RESPONSE") from exc
        if response.status_code >= 400:
            code = str(payload.get("error") or payload.get("code") or f"HTTP_{response.status_code}")
            message = payload.get("message") or "Mercado Pago rechazó la solicitud."
            raise MercadoPagoProviderError(message, code)
        return payload

    def create_preference(self, payload):
        try:
            response = self.session.post(f"{self.base_url}/checkout/preferences", headers=self.headers, json=payload, timeout=self.timeout)
        except (requests.Timeout, requests.ConnectionError) as exc:
            raise MercadoPagoUncertainError("No se pudo confirmar si Mercado Pago creó la preferencia.") from exc
        if response.status_code >= 500:
            raise MercadoPagoUncertainError("Mercado Pago respondió con un error remoto y no es seguro reenviar la creación a ciegas.")
        return self._json(response)

    def get_payment(self, payment_id):
        try:
            response = self.session.get(f"{self.base_url}/v1/payments/{payment_id}", headers=self.headers, timeout=self.timeout)
        except (requests.Timeout, requests.ConnectionError) as exc:
            raise MercadoPagoProviderError("No fue posible consultar el pago en Mercado Pago.", "NETWORK_ERROR") from exc
        return self._json(response)

    def search_preferences(self, external_reference):
        try:
            response = self.session.get(
                f"{self.base_url}/checkout/preferences/search",
                headers=self.headers,
                params={"external_reference": external_reference},
                timeout=self.timeout,
            )
        except (requests.Timeout, requests.ConnectionError) as exc:
            raise MercadoPagoProviderError("No fue posible buscar la preferencia en Mercado Pago.", "NETWORK_ERROR") from exc
        return self._json(response)


def validate_webhook_signature(*, x_signature, x_request_id, data_id, secret):
    if not x_signature or not secret:
        return False
    parts = {}
    for item in x_signature.split(","):
        if "=" in item:
            key, value = item.split("=", 1)
            parts[key.strip()] = value.strip()
    ts = parts.get("ts", "")
    received = parts.get("v1", "")
    if not ts or not received:
        return False
    manifest_parts = []
    if data_id:
        manifest_parts.append(f"id:{data_id};")
    if x_request_id:
        manifest_parts.append(f"request-id:{x_request_id};")
    manifest_parts.append(f"ts:{ts};")
    manifest = "".join(manifest_parts)
    expected = hmac.new(secret.encode("utf-8"), manifest.encode("utf-8"), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, received)
