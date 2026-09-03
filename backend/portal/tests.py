from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from catalog.models import Category, Product, ProductVariant
from customers.models import Customer
from inventory.models import InventoryStock
from orders.models import Order
from organizations.models import Branch, Company, Warehouse

from .models import CustomerPortalAccount, PortalOrderRequest

User = get_user_model()


class PortalApiTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            name="Tienda Norte",
            legal_name="Tienda Norte SpA",
            business_activity="Comercio",
            commune="Providencia",
            city="Santiago",
            is_active=True,
        )
        self.branch = Branch.objects.create(
            company=self.company,
            code="CASA",
            name="Casa Matriz",
            address="Av. Siempre Viva 123",
            commune="Providencia",
            city="Santiago",
            is_active=True,
        )
        self.warehouse = Warehouse.objects.create(
            company=self.company,
            branch=self.branch,
            code="BOD-1",
            name="Bodega Web",
        )
        self.category = Category.objects.create(company=self.company, name="Alimentos")
        self.product = Product.objects.create(
            company=self.company,
            category=self.category,
            name="Café premium",
            description="Café tostado de origen nacional.",
            image_url="https://example.com/cafe.jpg",
            status=Product.Status.ACTIVE,
        )
        self.variant = ProductVariant.objects.create(
            product=self.product,
            sku="CAF-001",
            base_price=Decimal("12990.00"),
            status=ProductVariant.Status.ACTIVE,
        )
        self.stock = InventoryStock.objects.create(
            warehouse=self.warehouse,
            variant=self.variant,
            quantity=Decimal("10.000"),
        )

    def _create_portal_user(self, email="cliente@example.com"):
        user = User.objects.create_user(
            username=email,
            email=email,
            password="Clave-segura-2026!",
            first_name="Cliente",
        )
        customer = Customer.objects.create(
            company=self.company,
            code=f"WEB-{user.id}",
            name="Cliente Portal",
            email=email,
            address="Calle Uno 123",
            commune="Providencia",
            city="Santiago",
        )
        CustomerPortalAccount.objects.create(
            user=user,
            company=self.company,
            customer=customer,
        )
        return user, customer

    def test_public_store_list_returns_only_active_stores(self):
        Company.objects.create(name="Oculta", is_active=False)
        response = self.client.get("/api/portal/stores/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual([item["name"] for item in response.json()["stores"]], ["Tienda Norte"])
        self.assertEqual(response.json()["stores"][0]["branches"][0]["name"], "Casa Matriz")

    def test_catalog_search_returns_published_products_and_availability(self):
        response = self.client.get(
            f"/api/portal/stores/{self.company.id}/catalog/",
            {"search": "café"},
        )
        self.assertEqual(response.status_code, 200)
        products = response.json()["products"]
        self.assertEqual(len(products), 1)
        self.assertEqual(products[0]["name"], "Café premium")
        self.assertTrue(products[0]["available"])
        self.assertEqual(products[0]["variants"][0]["available_quantity"], "10.000")

    def test_product_detail_exposes_description_image_variants_and_availability(self):
        response = self.client.get(
            f"/api/portal/stores/{self.company.id}/products/{self.product.id}/"
        )
        self.assertEqual(response.status_code, 200)
        product = response.json()["product"]
        self.assertEqual(product["description"], "Café tostado de origen nacional.")
        self.assertEqual(product["image_url"], "https://example.com/cafe.jpg")
        self.assertEqual(product["variants"][0]["sku"], "CAF-001")
        self.assertTrue(product["variants"][0]["available"])

    def test_registration_creates_user_customer_account_and_session(self):
        self.client.get("/api/auth/csrf/")
        response = self.client.post(
            "/api/portal/register/",
            {
                "company": self.company.id,
                "email": "nuevo@example.com",
                "password": "Clave-segura-2026!",
                "first_name": "Ana",
                "last_name": "Pérez",
                "phone": "+56912345678",
                "address": "Los Alerces 10",
                "commune": "Ñuñoa",
                "city": "Santiago",
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        account = CustomerPortalAccount.objects.select_related("customer").get(
            user__email="nuevo@example.com"
        )
        self.assertEqual(account.customer.address, "Los Alerces 10")
        me = self.client.get("/api/portal/account/")
        self.assertEqual(me.status_code, 200)
        self.assertEqual(me.json()["accounts"][0]["company"], self.company.id)

    def test_create_order_uses_server_price_confirms_stock_and_is_idempotent(self):
        user, customer = self._create_portal_user()
        self.client.force_login(user)
        payload = {
            "company": self.company.id,
            "branch": self.branch.id,
            "delivery_address": "Calle Uno 123",
            "delivery_commune": "Providencia",
            "delivery_city": "Santiago",
            "notes": "Entregar en recepción",
            "items": [{"variant": self.variant.id, "quantity": "2.000"}],
        }
        response = self.client.post(
            "/api/portal/orders/create/",
            payload,
            content_type="application/json",
            HTTP_IDEMPOTENCY_KEY="portal-order-1",
        )
        self.assertEqual(response.status_code, 201)
        order = Order.objects.get(pk=response.json()["order"]["id"])
        self.assertEqual(order.customer, customer)
        self.assertEqual(order.status, Order.Status.CONFIRMED)
        self.assertEqual(order.items.get().unit_price, Decimal("12990.00"))
        self.stock.refresh_from_db()
        self.assertEqual(self.stock.quantity, Decimal("8.000"))

        replay = self.client.post(
            "/api/portal/orders/create/",
            payload,
            content_type="application/json",
            HTTP_IDEMPOTENCY_KEY="portal-order-1",
        )
        self.assertEqual(replay.status_code, 200)
        self.assertTrue(replay.json()["idempotent_replay"])
        self.assertEqual(Order.objects.filter(customer=customer).count(), 1)
        self.stock.refresh_from_db()
        self.assertEqual(self.stock.quantity, Decimal("8.000"))

    def test_reused_idempotency_key_with_different_payload_is_rejected(self):
        user, _ = self._create_portal_user()
        self.client.force_login(user)
        base = {
            "company": self.company.id,
            "branch": self.branch.id,
            "delivery_address": "Calle Uno 123",
            "delivery_commune": "Providencia",
            "delivery_city": "Santiago",
            "notes": "",
            "items": [{"variant": self.variant.id, "quantity": "1.000"}],
        }
        self.client.post(
            "/api/portal/orders/create/",
            base,
            content_type="application/json",
            HTTP_IDEMPOTENCY_KEY="same-key",
        )
        changed = {**base, "items": [{"variant": self.variant.id, "quantity": "2.000"}]}
        response = self.client.post(
            "/api/portal/orders/create/",
            changed,
            content_type="application/json",
            HTTP_IDEMPOTENCY_KEY="same-key",
        )
        self.assertEqual(response.status_code, 409)

    def test_order_history_is_isolated_to_authenticated_customer(self):
        user, _ = self._create_portal_user()
        other_user, _ = self._create_portal_user("otro@example.com")
        self.client.force_login(user)
        payload = {
            "company": self.company.id,
            "branch": self.branch.id,
            "delivery_address": "Calle Uno 123",
            "delivery_commune": "Providencia",
            "delivery_city": "Santiago",
            "notes": "",
            "items": [{"variant": self.variant.id, "quantity": "1.000"}],
        }
        created = self.client.post(
            "/api/portal/orders/create/",
            payload,
            content_type="application/json",
            HTTP_IDEMPOTENCY_KEY="history-1",
        ).json()["order"]

        self.client.force_login(other_user)
        detail = self.client.get(f"/api/portal/orders/{created['id']}/")
        self.assertEqual(detail.status_code, 404)
        history = self.client.get("/api/portal/orders/")
        self.assertEqual(history.status_code, 200)
        self.assertEqual(history.json()["orders"], [])

    def test_order_rejects_when_no_single_warehouse_can_cover_stock(self):
        user, _ = self._create_portal_user()
        self.client.force_login(user)
        self.stock.quantity = Decimal("1.000")
        self.stock.save()
        response = self.client.post(
            "/api/portal/orders/create/",
            {
                "company": self.company.id,
                "branch": self.branch.id,
                "delivery_address": "Calle Uno 123",
                "delivery_commune": "Providencia",
                "delivery_city": "Santiago",
                "notes": "",
                "items": [{"variant": self.variant.id, "quantity": "2.000"}],
            },
            content_type="application/json",
            HTTP_IDEMPOTENCY_KEY="no-stock",
        )
        self.assertEqual(response.status_code, 409)
        self.assertEqual(PortalOrderRequest.objects.count(), 0)
