import hashlib
import hmac
import os
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from catalog.models import Category, Product, ProductVariant
from customers.models import Customer
from inventory.models import InventoryStock
from orders.models import Order
from orders.services import OrderTransitionError, cancel_order, deliver_order, prepare_order
from organizations.models import Branch, Company, Warehouse
from portal.models import CustomerPortalAccount
from portal.services import create_portal_order
from sales.models import Payment, Sale

from .models import MercadoPagoCheckout, MercadoPagoWebhookReceipt
from .provider import validate_webhook_signature
from .services import (
    MercadoPagoConflictError,
    apply_payment_payload,
    create_or_get_checkout,
)

User = get_user_model()


class FakeMercadoPagoClient:
    return_base = "https://portal.example.test"
    webhook_url = "https://api.example.test/api/portal/payments/mercado-pago/webhook/"

    def __init__(self, payment=None):
        self.payment = payment
        self.created_payloads = []

    def create_preference(self, payload):
        self.created_payloads.append(payload)
        return {
            "id": "PREF-123",
            "init_point": "https://www.mercadopago.cl/checkout/v1/redirect?pref_id=PREF-123",
            "sandbox_init_point": "https://sandbox.mercadopago.cl/checkout/v1/redirect?pref_id=PREF-123",
        }

    def get_payment(self, payment_id):
        return {**self.payment, "id": payment_id}


@override_settings(MERCADO_PAGO_USE_SANDBOX_INIT_POINT=False, MERCADO_PAGO_ACCEPT_LIVE_MODE=False)
class MercadoPagoServiceTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name="Tienda Norte", legal_name="Tienda Norte SpA", is_active=True)
        self.branch = Branch.objects.create(company=self.company, code="CASA", name="Casa Matriz", is_active=True)
        self.warehouse = Warehouse.objects.create(company=self.company, branch=self.branch, code="BOD-1", name="Bodega Web")
        category = Category.objects.create(company=self.company, name="Alimentos")
        product = Product.objects.create(company=self.company, category=category, name="Café premium", status=Product.Status.ACTIVE)
        self.variant = ProductVariant.objects.create(product=product, sku="CAF-001", base_price=Decimal("12990.00"), status=ProductVariant.Status.ACTIVE)
        InventoryStock.objects.create(warehouse=self.warehouse, variant=self.variant, quantity=Decimal("10.000"))
        self.user = User.objects.create_user(username="cliente@example.com", email="cliente@example.com", password="Clave-segura-2026!")
        self.customer = Customer.objects.create(company=self.company, code="WEB-1", name="Cliente Portal", email="cliente@example.com")
        self.account = CustomerPortalAccount.objects.create(user=self.user, company=self.company, customer=self.customer)
        self.order, _ = create_portal_order(
            user=self.user,
            company=self.company,
            branch=self.branch,
            items=[{"variant": self.variant, "quantity": Decimal("2.000")}],
            delivery_address="Calle Uno 123",
            delivery_commune="Providencia",
            delivery_city="Santiago",
            notes="",
            idempotency_key="portal-order-mp",
        )

    def _checkout(self):
        client = FakeMercadoPagoClient()
        checkout, created = create_or_get_checkout(user=self.user, order=self.order, idempotency_key="mp-checkout-1", client=client)
        self.assertTrue(created)
        return checkout, client

    def _approved_payload(self, checkout, payment_id="9001"):
        return {
            "id": payment_id,
            "status": "approved",
            "status_detail": "accredited",
            "transaction_amount": str(checkout.amount),
            "currency_id": "CLP",
            "external_reference": checkout.external_reference,
            "live_mode": False,
            "date_created": "2026-09-03T18:00:00Z",
            "date_approved": "2026-09-03T18:00:02Z",
        }

    def test_create_preference_uses_server_total_and_is_stable(self):
        checkout, client = self._checkout()
        self.assertEqual(checkout.status, MercadoPagoCheckout.Status.READY)
        self.assertEqual(checkout.amount, Decimal("25980.00"))
        self.assertEqual(client.created_payloads[0]["items"][0]["unit_price"], 25980.0)
        self.assertEqual(client.created_payloads[0]["external_reference"], checkout.external_reference)
        replay, created = create_or_get_checkout(user=self.user, order=self.order, idempotency_key="mp-checkout-1", client=client)
        self.assertFalse(created)
        self.assertEqual(replay.pk, checkout.pk)
        self.assertEqual(len(client.created_payloads), 1)

    def test_approved_remote_payment_is_persisted_without_creating_sale_before_delivery(self):
        checkout, _ = self._checkout()
        checkout, remote, consistent = apply_payment_payload(payload=self._approved_payload(checkout))
        self.assertTrue(consistent)
        self.assertEqual(checkout.status, MercadoPagoCheckout.Status.APPROVED)
        self.assertEqual(remote.status, "approved")
        self.assertFalse(Sale.objects.filter(order=self.order).exists())

    def test_payment_amount_mismatch_never_approves_checkout(self):
        checkout, _ = self._checkout()
        payload = self._approved_payload(checkout)
        payload["transaction_amount"] = "100.00"
        checkout, _, consistent = apply_payment_payload(payload=payload)
        self.assertFalse(consistent)
        self.assertEqual(checkout.status, MercadoPagoCheckout.Status.UNCERTAIN)
        self.assertEqual(checkout.last_error_code, "PAYMENT_MISMATCH")

    def test_delivery_requires_approved_checkout_and_reconciles_internal_sale(self):
        checkout, _ = self._checkout()
        self.order = prepare_order(order=self.order, performed_by=self.user)
        with self.assertRaises(OrderTransitionError):
            deliver_order(order=self.order, performed_by=self.user)
        apply_payment_payload(payload=self._approved_payload(checkout, "9002"))
        delivered = deliver_order(order=self.order, performed_by=self.user)
        self.assertEqual(delivered.status, Order.Status.DELIVERED)
        sale = Sale.objects.get(order=self.order)
        self.assertEqual(sale.status, Sale.Status.PAID)
        self.assertEqual(sale.paid_amount, Decimal("25980.00"))
        self.assertEqual(Payment.objects.get(sale=sale).reference, "MP:9002")
        checkout.refresh_from_db()
        self.assertEqual(checkout.sale_id, sale.id)

    def test_order_with_approved_external_payment_cannot_be_cancelled(self):
        checkout, _ = self._checkout()
        apply_payment_payload(payload=self._approved_payload(checkout, "9003"))
        with self.assertRaises(OrderTransitionError):
            cancel_order(order=self.order, performed_by=self.user)

    def test_live_mode_payment_is_rejected_in_test_only_slice(self):
        checkout, _ = self._checkout()
        payload = self._approved_payload(checkout)
        payload["live_mode"] = True
        with self.assertRaises(MercadoPagoConflictError):
            apply_payment_payload(payload=payload)

    def test_webhook_signature_matches_official_manifest(self):
        secret = "secret-test"
        ts = "1704908010"
        data_id = "999999999"
        request_id = "req-123"
        manifest = f"id:{data_id};request-id:{request_id};ts:{ts};"
        digest = hmac.new(secret.encode(), manifest.encode(), hashlib.sha256).hexdigest()
        self.assertTrue(validate_webhook_signature(x_signature=f"ts={ts},v1={digest}", x_request_id=request_id, data_id=data_id, secret=secret))
        self.assertFalse(validate_webhook_signature(x_signature=f"ts={ts},v1=bad", x_request_id=request_id, data_id=data_id, secret=secret))

    @override_settings(
        MERCADO_PAGO_ENABLED=True,
        MERCADO_PAGO_ACCESS_TOKEN_ENV="MP_TEST_TOKEN",
        MERCADO_PAGO_WEBHOOK_SECRET_ENV="MP_WEBHOOK_SECRET",
        MERCADO_PAGO_RETURN_BASE_URL="https://portal.example.test",
        MERCADO_PAGO_WEBHOOK_URL="https://api.example.test/api/portal/payments/mercado-pago/webhook/",
    )
    def test_webhook_is_signature_checked_and_idempotent(self):
        checkout, _ = self._checkout()
        remote = self._approved_payload(checkout, "9010")
        secret = "webhook-secret"
        ts = "1704908010"
        request_id = "req-webhook-1"
        data_id = "9010"
        manifest = f"id:{data_id};request-id:{request_id};ts:{ts};"
        digest = hmac.new(secret.encode(), manifest.encode(), hashlib.sha256).hexdigest()
        body = {"id": "notif-1", "type": "payment", "action": "payment.updated", "live_mode": False, "data": {"id": data_id}}
        fake = FakeMercadoPagoClient(payment=remote)
        with patch.dict(os.environ, {"MP_TEST_TOKEN": "TEST-token", "MP_WEBHOOK_SECRET": secret}), patch("external_payments.views.MercadoPagoClient", return_value=fake):
            response = self.client.post(
                f"/api/portal/payments/mercado-pago/webhook/?data.id={data_id}&type=payment",
                body,
                content_type="application/json",
                HTTP_X_REQUEST_ID=request_id,
                HTTP_X_SIGNATURE=f"ts={ts},v1={digest}",
            )
            self.assertEqual(response.status_code, 200)
            replay = self.client.post(
                f"/api/portal/payments/mercado-pago/webhook/?data.id={data_id}&type=payment",
                body,
                content_type="application/json",
                HTTP_X_REQUEST_ID=request_id,
                HTTP_X_SIGNATURE=f"ts={ts},v1={digest}",
            )
            self.assertEqual(replay.status_code, 200)
        self.assertEqual(MercadoPagoWebhookReceipt.objects.filter(notification_id="notif-1").count(), 1)
        checkout.refresh_from_db()
        self.assertEqual(checkout.status, MercadoPagoCheckout.Status.APPROVED)
