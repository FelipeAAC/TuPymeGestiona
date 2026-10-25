from decimal import Decimal

from django.test import TestCase

from accounts.models import User
from catalog.models import Category, Product, ProductVariant
from customers.models import Customer
from external_payments.models import MercadoPagoCheckout
from organizations.models import Branch, Company, Warehouse
from portal.models import CustomerPortalAccount

from .models import Order, OrderItem
from .serializers import OrderSerializer


class OrderPaymentVisibilityTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="orders-payment-admin",
            email="orders-payment-admin@example.test",
            password="Strong-password-123!",
        )
        self.company = Company.objects.create(name="Payment visibility company")
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
            code="CUS-001",
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

    def test_admin_serializer_exposes_approved_payment_summary(self):
        checkout = MercadoPagoCheckout.objects.create(
            order=self.order,
            portal_account=self.portal_account,
            status=MercadoPagoCheckout.Status.APPROVED,
            external_reference="TPG-MP-1-1",
            amount=Decimal("3420.00"),
            currency="CLP",
            idempotency_key="payment-visibility-key",
            request_hash="payment-visibility-hash",
            preference_id="pref-payment-visibility",
            init_point="https://example.test/pay",
            provider_status="approved",
            provider_status_detail="accredited",
            last_payment_id="payment-visibility-001",
        )

        payload = OrderSerializer(
            self.order,
            context={"include_payment": True},
        ).data

        self.assertEqual(payload["payment"]["status"], MercadoPagoCheckout.Status.APPROVED)
        self.assertEqual(payload["payment"]["provider_status"], "approved")
        self.assertEqual(payload["payment"]["last_payment_id"], "payment-visibility-001")
        self.assertEqual(payload["payment"]["sale"], checkout.sale_id)

    def test_admin_serializer_reports_missing_payment_as_none(self):
        payload = OrderSerializer(
            self.order,
            context={"include_payment": True},
        ).data

        self.assertIsNone(payload["payment"])

    def test_portal_serializer_context_does_not_expose_payment_details(self):
        checkout = MercadoPagoCheckout.objects.create(
            order=self.order,
            portal_account=self.portal_account,
            status=MercadoPagoCheckout.Status.APPROVED,
            external_reference="TPG-MP-1-2",
            amount=Decimal("3420.00"),
            currency="CLP",
            idempotency_key="payment-visibility-key-2",
            request_hash="payment-visibility-hash-2",
            preference_id="pref-payment-visibility-2",
            init_point="https://example.test/pay-2",
            provider_status="approved",
        )

        payload = OrderSerializer(self.order).data

        self.assertIsNone(payload["payment"])
