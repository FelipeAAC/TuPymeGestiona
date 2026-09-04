from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from administration.models import CompanySettings
from administration.services import ADMIN_PERMISSION_CODE
from catalog.models import Category, Product, ProductVariant
from inventory.models import InventoryStock
from organizations.authorization import has_permission
from organizations.models import Branch, Company, CompanyMembership, Warehouse

from .models import CustomerPortalAccount


User = get_user_model()


class IdentityOnboardingTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            name="Tienda Demo",
            legal_name="Tienda Demo SpA",
            business_activity="Comercio",
            commune="Santiago",
            city="Santiago",
            is_active=True,
        )
        self.branch = Branch.objects.create(
            company=self.company,
            code="CASA",
            name="Casa Matriz",
            address="Av. Demo 100",
            commune="Santiago",
            city="Santiago",
            is_active=True,
        )
        self.warehouse = Warehouse.objects.create(
            company=self.company,
            branch=self.branch,
            code="WEB",
            name="Bodega Web",
        )
        category = Category.objects.create(company=self.company, name="General")
        product = Product.objects.create(
            company=self.company,
            category=category,
            name="Producto Demo",
            description="Producto de prueba.",
            status=Product.Status.ACTIVE,
        )
        self.variant = ProductVariant.objects.create(
            product=product,
            sku="DEMO-1",
            base_price=Decimal("5000.00"),
            status=ProductVariant.Status.ACTIVE,
        )
        InventoryStock.objects.create(
            warehouse=self.warehouse,
            variant=self.variant,
            quantity=Decimal("10.000"),
        )

    def _register_person(self, email="persona@example.com"):
        self.client.get("/api/auth/csrf/")
        response = self.client.post(
            "/api/portal/register/",
            {
                "email": email,
                "password": "Clave-segura-2026!",
                "first_name": "Persona",
                "last_name": "Demo",
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201, response.content)
        return User.objects.get(email=email)

    def test_registration_creates_only_global_identity_without_store_choice(self):
        user = self._register_person()

        self.assertFalse(CustomerPortalAccount.objects.filter(user=user).exists())
        account_response = self.client.get("/api/portal/account/")
        self.assertEqual(account_response.status_code, 200)
        self.assertEqual(account_response.json()["accounts"], [])

    def test_first_purchase_creates_customer_relationship_for_selected_store(self):
        user = self._register_person()

        response = self.client.post(
            "/api/portal/orders/create/",
            {
                "company": self.company.id,
                "branch": self.branch.id,
                "delivery_address": "Calle Cliente 123",
                "delivery_commune": "Providencia",
                "delivery_city": "Santiago",
                "notes": "",
                "items": [{"variant": self.variant.id, "quantity": "1.000"}],
            },
            content_type="application/json",
            HTTP_IDEMPOTENCY_KEY="identity-order-1",
        )
        self.assertEqual(response.status_code, 201, response.content)

        account = CustomerPortalAccount.objects.select_related("customer").get(
            user=user,
            company=self.company,
        )
        self.assertEqual(account.customer.address, "Calle Cliente 123")
        self.assertEqual(account.customer.email, "persona@example.com")

    def test_authenticated_person_can_create_own_pyme_and_becomes_administrator(self):
        user = self._register_person("propietario@example.com")

        response = self.client.post(
            "/api/administration/self-service/companies/",
            {
                "name": "Mi Pyme",
                "rut": "12.345.678-5",
                "legal_name": "Mi Pyme SpA",
                "business_activity": "Comercio",
                "contact_email": "propietario@example.com",
                "phone": "+56 9 1111 2222",
                "address": "Av. Principal 100",
                "commune": "Providencia",
                "city": "Santiago",
                "is_active": True,
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201, response.content)

        company = Company.objects.get(name="Mi Pyme")
        membership = CompanyMembership.objects.get(user=user, company=company)
        self.assertEqual(membership.status, CompanyMembership.Status.ACTIVE)
        self.assertTrue(
            has_permission(
                user=user,
                company=company,
                permission_code=ADMIN_PERMISSION_CODE,
            )
        )
        self.assertTrue(CompanySettings.objects.filter(company=company).exists())
        self.assertTrue(company.branches.filter(code="CASA", is_active=True).exists())
