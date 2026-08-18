from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from organizations.models import (
    Company,
    CompanyMembership,
    CompanyRole,
    CompanyRolePermission,
    Permission,
    RoleAssignment,
)

from .models import Brand, Category, Product, ProductVariant
from .views import PRODUCTS_VIEW_PERMISSION_CODE


User = get_user_model()


class CatalogModelsTests(TestCase):
    def setUp(self):
        self.company_a = Company.objects.create(
            name="Empresa Catalog A",
        )
        self.company_b = Company.objects.create(
            name="Empresa Catalog B",
        )

        self.category_a = Category.objects.create(
            company=self.company_a,
            name="Categoria A",
        )
        self.category_b = Category.objects.create(
            company=self.company_b,
            name="Categoria B",
        )

        self.brand_a = Brand.objects.create(
            company=self.company_a,
            name="Marca A",
        )
        self.brand_b = Brand.objects.create(
            company=self.company_b,
            name="Marca B",
        )

    def test_category_can_be_root(self):
        self.assertIsNone(self.category_a.parent)

    def test_category_can_have_parent_from_same_company(self):
        child = Category.objects.create(
            company=self.company_a,
            parent=self.category_a,
            name="Subcategoria A",
        )

        self.assertEqual(child.parent, self.category_a)

    def test_category_parent_must_belong_to_same_company(self):
        with self.assertRaises(ValidationError):
            Category.objects.create(
                company=self.company_a,
                parent=self.category_b,
                name="Subcategoria Invalida",
            )

    def test_category_cannot_be_its_own_parent(self):
        category = Category.objects.create(
            company=self.company_a,
            name="Categoria Self",
        )

        category.parent = category

        with self.assertRaises(ValidationError):
            category.save()

    def test_category_hierarchy_cannot_contain_indirect_cycle(self):
        parent = Category.objects.create(
            company=self.company_a,
            name="Categoria Parent",
        )

        child = Category.objects.create(
            company=self.company_a,
            parent=parent,
            name="Categoria Child",
        )

        parent.parent = child

        with self.assertRaises(ValidationError):
            parent.save()

    def test_product_category_must_belong_to_same_company(self):
        with self.assertRaises(ValidationError):
            Product.objects.create(
                company=self.company_a,
                category=self.category_b,
                name="Producto Categoria Invalida",
            )

    def test_product_can_exist_without_brand(self):
        product = Product.objects.create(
            company=self.company_a,
            category=self.category_a,
            name="Producto Sin Marca",
        )

        self.assertIsNone(product.brand)

    def test_product_brand_must_belong_to_same_company(self):
        with self.assertRaises(ValidationError):
            Product.objects.create(
                company=self.company_a,
                category=self.category_a,
                brand=self.brand_b,
                name="Producto Marca Invalida",
            )

    def test_product_defaults_to_draft(self):
        product = Product.objects.create(
            company=self.company_a,
            category=self.category_a,
            brand=self.brand_a,
            name="Producto Draft",
        )

        self.assertEqual(
            product.status,
            Product.Status.DRAFT,
        )

    def test_product_variant_defaults_to_draft(self):
        product = Product.objects.create(
            company=self.company_a,
            category=self.category_a,
            name="Producto Variante",
        )

        variant = ProductVariant.objects.create(
            product=product,
            sku="SKU-001",
            base_price=Decimal("12990.00"),
        )

        self.assertEqual(
            variant.status,
            ProductVariant.Status.DRAFT,
        )
        self.assertEqual(
            variant.base_price,
            Decimal("12990.00"),
        )

    def test_sku_must_be_unique_inside_company(self):
        product_a = Product.objects.create(
            company=self.company_a,
            category=self.category_a,
            name="Producto A1",
        )
        product_a_2 = Product.objects.create(
            company=self.company_a,
            category=self.category_a,
            name="Producto A2",
        )

        ProductVariant.objects.create(
            product=product_a,
            sku="SKU-SHARED",
            base_price=Decimal("1000.00"),
        )

        with self.assertRaises(ValidationError):
            ProductVariant.objects.create(
                product=product_a_2,
                sku="SKU-SHARED",
                base_price=Decimal("2000.00"),
            )

    def test_same_sku_can_exist_in_different_companies(self):
        product_a = Product.objects.create(
            company=self.company_a,
            category=self.category_a,
            name="Producto Empresa A",
        )
        product_b = Product.objects.create(
            company=self.company_b,
            category=self.category_b,
            name="Producto Empresa B",
        )

        variant_a = ProductVariant.objects.create(
            product=product_a,
            sku="SKU-COMPARTIDO",
            base_price=Decimal("1000.00"),
        )
        variant_b = ProductVariant.objects.create(
            product=product_b,
            sku="SKU-COMPARTIDO",
            base_price=Decimal("2000.00"),
        )

        self.assertEqual(
            variant_a.sku,
            variant_b.sku,
        )


class ProductListApiTests(TestCase):
    def setUp(self):
        self.url = "/api/catalog/products/"

        self.user = User.objects.create_user(
            username="catalog-api-user",
            email="catalog-api-user@example.com",
            password="test-password",
        )

        self.company_a = Company.objects.create(
            name="Empresa API A",
        )
        self.company_b = Company.objects.create(
            name="Empresa API B",
        )

        self.membership_a = CompanyMembership.objects.create(
            user=self.user,
            company=self.company_a,
            status=CompanyMembership.Status.ACTIVE,
        )

        self.category_a = Category.objects.create(
            company=self.company_a,
            name="Categoria API A",
        )
        self.category_b = Category.objects.create(
            company=self.company_b,
            name="Categoria API B",
        )

        self.brand_a = Brand.objects.create(
            company=self.company_a,
            name="Marca API A",
        )

        self.product_a = Product.objects.create(
            company=self.company_a,
            category=self.category_a,
            brand=self.brand_a,
            name="Producto API A",
            status=Product.Status.ACTIVE,
        )

        self.product_a_without_brand = Product.objects.create(
            company=self.company_a,
            category=self.category_a,
            name="Producto API A Sin Marca",
        )

        self.product_b = Product.objects.create(
            company=self.company_b,
            category=self.category_b,
            name="Producto API B",
            status=Product.Status.ACTIVE,
        )

        ProductVariant.objects.create(
            product=self.product_a,
            sku="SKU-API-A",
            gtin="780000000001",
            base_price=Decimal("12990.00"),
            status=ProductVariant.Status.ACTIVE,
        )

    def grant_products_view(
        self,
        *,
        company=None,
        membership=None,
    ):
        company = company or self.company_a
        membership = membership or self.membership_a

        permission, _ = Permission.objects.get_or_create(
            code=PRODUCTS_VIEW_PERMISSION_CODE,
            defaults={
                "scope_behavior": Permission.ScopeBehavior.TENANT_GLOBAL,
            },
        )

        role = CompanyRole.objects.create(
            company=company,
            name=f"Catalog Viewer {company.pk}",
            status=CompanyRole.Status.ACTIVE,
        )

        CompanyRolePermission.objects.create(
            role=role,
            permission=permission,
        )

        RoleAssignment.objects.create(
            membership=membership,
            role=role,
            branch=None,
        )

    def test_product_list_requires_authentication(self):
        response = self.client.get(
            self.url,
            {
                "company": self.company_a.pk,
            },
        )

        self.assertEqual(response.status_code, 403)

    def test_product_list_requires_company_parameter(self):
        self.client.force_login(self.user)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 400)

    def test_product_list_rejects_invalid_company_parameter(self):
        self.client.force_login(self.user)

        response = self.client.get(
            self.url,
            {
                "company": "invalid",
            },
        )

        self.assertEqual(response.status_code, 400)

    def test_product_list_denies_company_without_active_membership(self):
        self.client.force_login(self.user)

        response = self.client.get(
            self.url,
            {
                "company": self.company_b.pk,
            },
        )

        self.assertEqual(response.status_code, 403)

    def test_product_list_denies_active_membership_without_permission(self):
        self.client.force_login(self.user)

        response = self.client.get(
            self.url,
            {
                "company": self.company_a.pk,
            },
        )

        self.assertEqual(response.status_code, 403)

    def test_product_list_returns_only_requested_company_products(self):
        self.grant_products_view()
        self.client.force_login(self.user)

        response = self.client.get(
            self.url,
            {
                "company": self.company_a.pk,
            },
        )

        self.assertEqual(response.status_code, 200)

        products = response.json()["products"]

        self.assertEqual(len(products), 2)

        product_names = {
            product["name"]
            for product in products
        }

        self.assertEqual(
            product_names,
            {
                "Producto API A",
                "Producto API A Sin Marca",
            },
        )

        self.assertNotIn(
            "Producto API B",
            product_names,
        )

    def test_product_list_serializes_catalog_relations(self):
        self.grant_products_view()
        self.client.force_login(self.user)

        response = self.client.get(
            self.url,
            {
                "company": self.company_a.pk,
            },
        )

        self.assertEqual(response.status_code, 200)

        products = response.json()["products"]

        product = next(
            item
            for item in products
            if item["name"] == "Producto API A"
        )

        self.assertEqual(
            product["category"],
            {
                "id": self.category_a.pk,
                "name": "Categoria API A",
            },
        )

        self.assertEqual(
            product["brand"],
            {
                "id": self.brand_a.pk,
                "name": "Marca API A",
            },
        )

        self.assertEqual(
            len(product["variants"]),
            1,
        )

        variant = product["variants"][0]

        self.assertEqual(
            variant["sku"],
            "SKU-API-A",
        )
        self.assertEqual(
            variant["gtin"],
            "780000000001",
        )
        self.assertEqual(
            variant["base_price"],
            "12990.00",
        )
        self.assertEqual(
            variant["status"],
            ProductVariant.Status.ACTIVE,
        )

    def test_permission_from_other_company_does_not_authorize(self):
        membership_b = CompanyMembership.objects.create(
            user=self.user,
            company=self.company_b,
            status=CompanyMembership.Status.ACTIVE,
        )

        self.grant_products_view(
            company=self.company_b,
            membership=membership_b,
        )

        self.client.force_login(self.user)

        response = self.client.get(
            self.url,
            {
                "company": self.company_a.pk,
            },
        )

        self.assertEqual(response.status_code, 403)

    def test_suspended_membership_does_not_authorize(self):
        self.grant_products_view()

        self.membership_a.status = CompanyMembership.Status.SUSPENDED
        self.membership_a.save(
            update_fields=["status"],
        )

        self.client.force_login(self.user)

        response = self.client.get(
            self.url,
            {
                "company": self.company_a.pk,
            },
        )

        self.assertEqual(response.status_code, 403)
