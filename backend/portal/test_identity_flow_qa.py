from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from catalog.models import Category, Product, ProductVariant
from inventory.models import InventoryStock
from organizations.models import Branch, Company, CompanyMembership, Warehouse

from .models import CustomerPortalAccount


User = get_user_model()


class IdentityFlowQATests(TestCase):
    def _create_store(self, *, name, suffix):
        company = Company.objects.create(
            name=name,
            legal_name=f"{name} SpA",
            business_activity="Comercio",
            commune="Santiago",
            city="Santiago",
            is_active=True,
        )
        branch = Branch.objects.create(
            company=company,
            code=f"CASA-{suffix}",
            name="Casa Matriz",
            address=f"Av. {suffix} 100",
            commune="Santiago",
            city="Santiago",
            is_active=True,
        )
        warehouse = Warehouse.objects.create(
            company=company,
            branch=branch,
            code=f"WEB-{suffix}",
            name="Bodega Web",
        )
        category = Category.objects.create(
            company=company,
            name=f"General {suffix}",
        )
        product = Product.objects.create(
            company=company,
            category=category,
            name=f"Producto {suffix}",
            description="Producto QA.",
            status=Product.Status.ACTIVE,
        )
        variant = ProductVariant.objects.create(
            product=product,
            sku=f"QA-{suffix}",
            base_price=Decimal("10000.00"),
            status=ProductVariant.Status.ACTIVE,
        )
        InventoryStock.objects.create(
            warehouse=warehouse,
            variant=variant,
            quantity=Decimal("20.000"),
        )
        return company, branch, variant

    def _register(self, *, email="qa.persona@example.com"):
        self.client.get("/api/auth/csrf/")
        response = self.client.post(
            "/api/portal/register/",
            {
                "email": email,
                "password": "Clave-segura-2026!",
                "first_name": "Persona",
                "last_name": "QA",
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201, response.content)
        self.assertIsNone(response.json()["account"])
        return User.objects.get(email=email)

    def _buy(self, *, company, branch, variant, key, address):
        response = self.client.post(
            "/api/portal/orders/create/",
            {
                "company": company.id,
                "branch": branch.id,
                "delivery_address": address,
                "delivery_commune": "Providencia",
                "delivery_city": "Santiago",
                "notes": "",
                "items": [{"variant": variant.id, "quantity": "1.000"}],
            },
            content_type="application/json",
            HTTP_IDEMPOTENCY_KEY=key,
        )
        self.assertEqual(response.status_code, 201, response.content)
        return response.json()["order"]

    def test_same_identity_can_buy_from_two_stores_without_re_registration(self):
        store_a = self._create_store(name="Tienda A", suffix="A")
        store_b = self._create_store(name="Tienda B", suffix="B")
        user = self._register()

        self._buy(
            company=store_a[0],
            branch=store_a[1],
            variant=store_a[2],
            key="identity-flow-a",
            address="Calle A 123",
        )
        self._buy(
            company=store_b[0],
            branch=store_b[1],
            variant=store_b[2],
            key="identity-flow-b",
            address="Calle B 456",
        )

        accounts = CustomerPortalAccount.objects.filter(user=user).order_by("company_id")
        self.assertEqual(accounts.count(), 2)
        self.assertEqual(
            set(accounts.values_list("company_id", flat=True)),
            {store_a[0].id, store_b[0].id},
        )

        history = self.client.get("/api/portal/orders/")
        self.assertEqual(history.status_code, 200)
        self.assertEqual(len(history.json()["orders"]), 2)

    def test_second_purchase_in_same_store_reuses_customer_relationship(self):
        company, branch, variant = self._create_store(name="Tienda Reuso", suffix="R")
        user = self._register(email="reuso@example.com")

        self._buy(
            company=company,
            branch=branch,
            variant=variant,
            key="identity-reuse-1",
            address="Calle Uno 10",
        )
        first_account = CustomerPortalAccount.objects.get(user=user, company=company)

        self._buy(
            company=company,
            branch=branch,
            variant=variant,
            key="identity-reuse-2",
            address="Calle Dos 20",
        )
        second_account = CustomerPortalAccount.objects.get(user=user, company=company)

        self.assertEqual(first_account.id, second_account.id)
        self.assertEqual(
            CustomerPortalAccount.objects.filter(user=user, company=company).count(),
            1,
        )

    def test_customer_can_become_owner_without_losing_customer_history(self):
        company, branch, variant = self._create_store(name="Tienda Cliente", suffix="C")
        user = self._register(email="owner.customer@example.com")
        self._buy(
            company=company,
            branch=branch,
            variant=variant,
            key="identity-owner-history",
            address="Calle Cliente 99",
        )

        create_company = self.client.post(
            "/api/administration/self-service/companies/",
            {
                "name": "Mi Negocio QA",
                "rut": "11.111.111-1",
                "legal_name": "Mi Negocio QA SpA",
                "business_activity": "Comercio",
                "contact_email": "owner.customer@example.com",
                "phone": "",
                "address": "Av. Negocio 1",
                "commune": "Providencia",
                "city": "Santiago",
                "is_active": True,
            },
            content_type="application/json",
        )
        self.assertEqual(create_company.status_code, 201, create_company.content)
        owned_company_id = create_company.json()["company"]["id"]

        self.assertTrue(
            CompanyMembership.objects.filter(
                user=user,
                company_id=owned_company_id,
                status=CompanyMembership.Status.ACTIVE,
            ).exists()
        )
        self.assertTrue(
            CustomerPortalAccount.objects.filter(user=user, company=company).exists()
        )

        context = self.client.get("/api/organizations/context/")
        self.assertEqual(context.status_code, 200)
        self.assertIn(
            owned_company_id,
            [item["company"]["id"] for item in context.json()["memberships"]],
        )

        history = self.client.get("/api/portal/orders/")
        self.assertEqual(history.status_code, 200)
        self.assertEqual(len(history.json()["orders"]), 1)
