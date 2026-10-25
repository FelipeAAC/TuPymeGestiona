from decimal import Decimal
import os
from unittest.mock import patch

from django.test import override_settings
from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import User
from catalog.models import Category, Product, ProductVariant
from customers.models import Customer
from orders.models import Order, OrderItem
from organizations.models import Branch, Company, Warehouse
from portal.models import CustomerPortalAccount

from .models import MercadoPagoCheckout, MercadoPagoEvent, MercadoPagoRemotePayment
from .services import MercadoPagoConflictError, apply_payment_payload


class MercadoPagoPaymentSyncTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="payment-sync-user",
            email="payment-sync@example.test",
            password="Strong-password-123!",
        )
        self.company = Company.objects.create(name="Payment Sync Company")
        self.branch = Branch.objects.create(company=self.company, code="MAIN", name="Main")
        self.warehouse = Warehouse.objects.create(
            company=self.company,
            branch=self.branch,
            code="WH-MAIN",
            name="Main warehouse",
        )
        category = Category.objects.create(company=self.company, name="General")
        product = Product.objects.create(
            company=self.company,
            category=category,
            name="Payment product",
            status=Product.Status.ACTIVE,
        )
        variant = ProductVariant.objects.create(
            product=product,
            sku="PAY-001",
            base_price=Decimal("3420.00"),
            status=ProductVariant.Status.ACTIVE,
        )
        customer = Customer.objects.create(
            company=self.company,
            code="PAY-CUS-001",
            name="Payment customer",
            email="customer@example.test",
        )
        self.portal_account = CustomerPortalAccount.objects.create(
            user=self.user,
            company=self.company,
            customer=customer,
        )
        self.order = Order.objects.create(
            company=self.company,
            branch=self.branch,
            warehouse=self.warehouse,
            customer=customer,
            number=1,
            status=Order.Status.CONFIRMED,
            created_by=self.user,
        )
        OrderItem.objects.create(
            order=self.order,
            variant=variant,
            quantity=1,
            unit_price=Decimal("3420.00"),
        )
        self.checkout = MercadoPagoCheckout.objects.create(
            order=self.order,
            portal_account=self.portal_account,
            status=MercadoPagoCheckout.Status.READY,
            external_reference=f"TPG-MP-{self.order.id}",
            amount=Decimal("3420.00"),
            currency="CLP",
            idempotency_key="payment-sync-key",
            request_hash="payment-sync-hash",
            preference_id="pref-payment-sync",
            init_point="https://example.test/pay",
        )

    def _payload(self, *, live_mode="false"):
        return {
            "id": "payment-sync-001",
            "external_reference": self.checkout.external_reference,
            "status": "approved",
            "status_detail": "accredited",
            "transaction_amount": "3420.00",
            "currency_id": "CLP",
            "live_mode": live_mode,
        }

    @patch("transactional_notifications.services.enqueue_payment_status_notification")
    def test_string_false_is_treated_as_sandbox_and_approves_payment(self, enqueue_notification):
        checkout, payment, created = apply_payment_payload(
            payload=self._payload(live_mode="false"),
            correlation_id="return:payment-sync-001",
        )

        self.assertTrue(created)
        self.assertEqual(checkout.status, MercadoPagoCheckout.Status.APPROVED)
        self.assertFalse(payment.live_mode)
        self.assertEqual(
            MercadoPagoRemotePayment.objects.get(provider_payment_id="payment-sync-001").status,
            "approved",
        )
        enqueue_notification.assert_called_once()

    @override_settings(
        MERCADO_PAGO_ENABLED=True,
        MERCADO_PAGO_ACCESS_TOKEN_ENV="PAYMENT_TEST_ACCESS_TOKEN",
        MERCADO_PAGO_WEBHOOK_SECRET_ENV="PAYMENT_TEST_WEBHOOK_SECRET",
        MERCADO_PAGO_RETURN_BASE_URL="https://example.test",
        MERCADO_PAGO_WEBHOOK_URL="https://example.test/webhook/",
    )
    @patch.dict(
        os.environ,
        {
            "PAYMENT_TEST_ACCESS_TOKEN": "test-token",
            "PAYMENT_TEST_WEBHOOK_SECRET": "test-secret",
        },
    )
    @patch("transactional_notifications.services.enqueue_payment_status_notification")
    def test_refresh_endpoint_accepts_sandbox_string_and_is_idempotent(self, enqueue_notification):
        client = APIClient()
        client.force_authenticate(user=self.user)
        with patch(
            "external_payments.provider.MercadoPagoClient.get_payment",
            return_value=self._payload(live_mode="false"),
        ):
            first = client.post(
                f"/api/portal/payments/orders/{self.order.id}/mercado-pago/refresh/",
                {"payment_id": "payment-sync-001"},
                format="json",
            )
            second = client.post(
                f"/api/portal/payments/orders/{self.order.id}/mercado-pago/refresh/",
                {"payment_id": "payment-sync-001"},
                format="json",
            )

        self.assertEqual(first.status_code, 200, first.data)
        self.assertEqual(second.status_code, 200, second.data)
        self.assertEqual(first.data["payment"]["status"], "APPROVED")
        self.assertEqual(second.data["payment"]["status"], "APPROVED")
        self.assertEqual(
            MercadoPagoEvent.objects.filter(
                checkout=self.checkout,
                event_type=MercadoPagoEvent.EventType.PAYMENT_APPROVED,
            ).count(),
            1,
        )
        enqueue_notification.assert_called_once()

    def test_true_live_mode_is_still_rejected_in_sandbox(self):
        with self.assertRaises(MercadoPagoConflictError):
            apply_payment_payload(
                payload=self._payload(live_mode="true"),
                correlation_id="return:payment-sync-live",
            )
