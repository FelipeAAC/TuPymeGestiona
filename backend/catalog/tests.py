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
from .views import (
    CATEGORIES_MANAGE_PERMISSION_CODE,
    PRODUCTS_MANAGE_PERMISSION_CODE,
    PRODUCTS_VIEW_PERMISSION_CODE,
)


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

    def test_products_view_permission_is_seeded(self):
        permission = Permission.objects.get(
            code=PRODUCTS_VIEW_PERMISSION_CODE,
        )

        self.assertEqual(
            permission.scope_behavior,
            Permission.ScopeBehavior.TENANT_GLOBAL,
        )

    def test_products_manage_permission_is_seeded(self):
        permission = Permission.objects.get(
            code=PRODUCTS_MANAGE_PERMISSION_CODE,
        )

        self.assertEqual(
            permission.scope_behavior,
            Permission.ScopeBehavior.COMPANY_ONLY,
        )

    def grant_products_view(
        self,
        *,
        company=None,
        membership=None,
    ):
        company = company or self.company_a
        membership = membership or self.membership_a

        permission = Permission.objects.get(
            code=PRODUCTS_VIEW_PERMISSION_CODE,
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


class ProductCreateApiTests(TestCase):
    def setUp(self):
        self.url = "/api/catalog/products/"

        self.user = User.objects.create_user(
            username="catalog-create-user",
            email="catalog-create-user@example.com",
            password="test-password",
        )

        self.company_a = Company.objects.create(
            name="Empresa Create A",
        )
        self.company_b = Company.objects.create(
            name="Empresa Create B",
        )

        self.membership_a = CompanyMembership.objects.create(
            user=self.user,
            company=self.company_a,
            status=CompanyMembership.Status.ACTIVE,
        )

        self.category_a = Category.objects.create(
            company=self.company_a,
            name="Categoria Create A",
        )
        self.category_b = Category.objects.create(
            company=self.company_b,
            name="Categoria Create B",
        )

        self.brand_a = Brand.objects.create(
            company=self.company_a,
            name="Marca Create A",
        )
        self.brand_b = Brand.objects.create(
            company=self.company_b,
            name="Marca Create B",
        )

    def product_payload(
        self,
        *,
        company=None,
        category=None,
        brand=None,
        name="Producto Creado",
        sku="SKU-CREATE-001",
        gtin="780000000010",
        base_price="19990.00",
    ):
        if company is None:
            company = self.company_a

        if category is None:
            category = self.category_a

        if brand is None:
            brand = self.brand_a

        return {
            "company": company.pk,
            "name": name,
            "category": category.pk,
            "brand": brand.pk,
            "variant": {
                "sku": sku,
                "gtin": gtin,
                "base_price": base_price,
            },
        }

    def grant_products_manage(
        self,
        *,
        company=None,
        membership=None,
    ):
        company = company or self.company_a
        membership = membership or self.membership_a

        permission = Permission.objects.get(
            code=PRODUCTS_MANAGE_PERMISSION_CODE,
        )

        role = CompanyRole.objects.create(
            company=company,
            name=f"Catalog Manager {company.pk}",
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

    def test_product_create_requires_authentication(self):
        response = self.client.post(
            self.url,
            self.product_payload(),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 403)

    def test_product_create_requires_company(self):
        self.client.force_login(self.user)

        payload = self.product_payload()
        payload.pop("company")

        response = self.client.post(
            self.url,
            payload,
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)

    def test_product_create_rejects_invalid_company(self):
        self.client.force_login(self.user)

        payload = self.product_payload()
        payload["company"] = "invalid"

        response = self.client.post(
            self.url,
            payload,
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)

    def test_product_create_denies_company_without_active_membership(self):
        self.client.force_login(self.user)

        response = self.client.post(
            self.url,
            self.product_payload(
                company=self.company_b,
                category=self.category_b,
                brand=self.brand_b,
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 403)

    def test_product_create_denies_active_membership_without_manage_permission(
        self,
    ):
        self.client.force_login(self.user)

        response = self.client.post(
            self.url,
            self.product_payload(),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 403)

    def test_products_view_permission_does_not_allow_product_create(self):
        permission = Permission.objects.get(
            code=PRODUCTS_VIEW_PERMISSION_CODE,
        )

        role = CompanyRole.objects.create(
            company=self.company_a,
            name="Catalog View Only",
            status=CompanyRole.Status.ACTIVE,
        )

        CompanyRolePermission.objects.create(
            role=role,
            permission=permission,
        )

        RoleAssignment.objects.create(
            membership=self.membership_a,
            role=role,
            branch=None,
        )

        self.client.force_login(self.user)

        response = self.client.post(
            self.url,
            self.product_payload(),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 403)

    def test_product_create_rejects_category_from_other_company(self):
        self.grant_products_manage()
        self.client.force_login(self.user)

        response = self.client.post(
            self.url,
            self.product_payload(
                category=self.category_b,
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)

        self.assertFalse(
            Product.objects.filter(
                name="Producto Creado",
            ).exists()
        )

    def test_product_create_rejects_brand_from_other_company(self):
        self.grant_products_manage()
        self.client.force_login(self.user)

        response = self.client.post(
            self.url,
            self.product_payload(
                brand=self.brand_b,
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)

        self.assertFalse(
            Product.objects.filter(
                name="Producto Creado",
            ).exists()
        )

    def test_product_create_creates_product_and_first_variant(self):
        self.grant_products_manage()
        self.client.force_login(self.user)

        response = self.client.post(
            self.url,
            self.product_payload(),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 201)

        product = Product.objects.get(
            company=self.company_a,
            name="Producto Creado",
        )

        self.assertEqual(
            product.category,
            self.category_a,
        )
        self.assertEqual(
            product.brand,
            self.brand_a,
        )
        self.assertEqual(
            product.status,
            Product.Status.DRAFT,
        )

        variant = product.variants.get()

        self.assertEqual(
            variant.sku,
            "SKU-CREATE-001",
        )
        self.assertEqual(
            variant.gtin,
            "780000000010",
        )
        self.assertEqual(
            variant.base_price,
            Decimal("19990.00"),
        )
        self.assertEqual(
            variant.status,
            ProductVariant.Status.DRAFT,
        )

        response_product = response.json()["product"]

        self.assertEqual(
            response_product["id"],
            product.pk,
        )
        self.assertEqual(
            response_product["status"],
            Product.Status.DRAFT,
        )
        self.assertEqual(
            len(response_product["variants"]),
            1,
        )

    def test_product_create_allows_missing_brand(self):
        self.grant_products_manage()
        self.client.force_login(self.user)

        payload = self.product_payload()
        payload.pop("brand")

        response = self.client.post(
            self.url,
            payload,
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 201)

        product = Product.objects.get(
            company=self.company_a,
            name="Producto Creado",
        )

        self.assertIsNone(product.brand)

    def test_duplicate_sku_returns_400_and_rolls_back_product(self):
        existing_product = Product.objects.create(
            company=self.company_a,
            category=self.category_a,
            brand=self.brand_a,
            name="Producto Existente",
        )

        ProductVariant.objects.create(
            product=existing_product,
            sku="SKU-DUPLICADO",
            base_price=Decimal("1000.00"),
        )

        self.grant_products_manage()
        self.client.force_login(self.user)

        product_count_before = Product.objects.filter(
            company=self.company_a,
        ).count()

        response = self.client.post(
            self.url,
            self.product_payload(
                name="Producto No Debe Quedar",
                sku="SKU-DUPLICADO",
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)

        self.assertEqual(
            Product.objects.filter(
                company=self.company_a,
            ).count(),
            product_count_before,
        )

        self.assertFalse(
            Product.objects.filter(
                company=self.company_a,
                name="Producto No Debe Quedar",
            ).exists()
        )

    def test_same_sku_can_be_created_in_different_companies(self):
        product_a = Product.objects.create(
            company=self.company_a,
            category=self.category_a,
            brand=self.brand_a,
            name="Producto Empresa A Existente",
        )

        ProductVariant.objects.create(
            product=product_a,
            sku="SKU-CROSS-COMPANY",
            base_price=Decimal("1000.00"),
        )

        membership_b = CompanyMembership.objects.create(
            user=self.user,
            company=self.company_b,
            status=CompanyMembership.Status.ACTIVE,
        )

        self.grant_products_manage(
            company=self.company_b,
            membership=membership_b,
        )

        self.client.force_login(self.user)

        response = self.client.post(
            self.url,
            self.product_payload(
                company=self.company_b,
                category=self.category_b,
                brand=self.brand_b,
                name="Producto Empresa B Nuevo",
                sku="SKU-CROSS-COMPANY",
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 201)

        self.assertTrue(
            ProductVariant.objects.filter(
                product__company=self.company_b,
                sku="SKU-CROSS-COMPANY",
            ).exists()
        )

    def test_suspended_membership_does_not_authorize_product_create(self):
        self.grant_products_manage()

        self.membership_a.status = CompanyMembership.Status.SUSPENDED
        self.membership_a.save(
            update_fields=["status"],
        )

        self.client.force_login(self.user)

        response = self.client.post(
            self.url,
            self.product_payload(),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 403)


class ProductOptionsApiTests(TestCase):
    def setUp(self):
        self.url = "/api/catalog/products/options/"

        self.user = User.objects.create_user(
            username="catalog-options-user",
            email="catalog-options-user@example.com",
            password="test-password",
        )

        self.company_a = Company.objects.create(
            name="Empresa Options A",
        )
        self.company_b = Company.objects.create(
            name="Empresa Options B",
        )

        self.membership_a = CompanyMembership.objects.create(
            user=self.user,
            company=self.company_a,
            status=CompanyMembership.Status.ACTIVE,
        )

        self.category_a = Category.objects.create(
            company=self.company_a,
            name="Categoria Options A",
        )
        self.category_b = Category.objects.create(
            company=self.company_b,
            name="Categoria Options B",
        )

        self.brand_a = Brand.objects.create(
            company=self.company_a,
            name="Marca Options A",
        )
        self.brand_b = Brand.objects.create(
            company=self.company_b,
            name="Marca Options B",
        )

    def grant_products_manage(
        self,
        *,
        company=None,
        membership=None,
    ):
        company = company or self.company_a
        membership = membership or self.membership_a

        permission = Permission.objects.get(
            code=PRODUCTS_MANAGE_PERMISSION_CODE,
        )

        role = CompanyRole.objects.create(
            company=company,
            name=f"Catalog Options Manager {company.pk}",
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

    def test_product_options_requires_authentication(self):
        response = self.client.get(
            self.url,
            {
                "company": self.company_a.pk,
            },
        )

        self.assertEqual(response.status_code, 403)

    def test_product_options_requires_company_parameter(self):
        self.client.force_login(self.user)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 400)

    def test_product_options_rejects_invalid_company_parameter(self):
        self.client.force_login(self.user)

        response = self.client.get(
            self.url,
            {
                "company": "invalid",
            },
        )

        self.assertEqual(response.status_code, 400)

    def test_product_options_denies_company_without_active_membership(self):
        self.client.force_login(self.user)

        response = self.client.get(
            self.url,
            {
                "company": self.company_b.pk,
            },
        )

        self.assertEqual(response.status_code, 403)

    def test_product_options_denies_active_membership_without_manage_permission(
        self,
    ):
        self.client.force_login(self.user)

        response = self.client.get(
            self.url,
            {
                "company": self.company_a.pk,
            },
        )

        self.assertEqual(response.status_code, 403)

    def test_products_view_permission_does_not_allow_product_options(self):
        permission = Permission.objects.get(
            code=PRODUCTS_VIEW_PERMISSION_CODE,
        )

        role = CompanyRole.objects.create(
            company=self.company_a,
            name="Catalog Options View Only",
            status=CompanyRole.Status.ACTIVE,
        )

        CompanyRolePermission.objects.create(
            role=role,
            permission=permission,
        )

        RoleAssignment.objects.create(
            membership=self.membership_a,
            role=role,
            branch=None,
        )

        self.client.force_login(self.user)

        response = self.client.get(
            self.url,
            {
                "company": self.company_a.pk,
            },
        )

        self.assertEqual(response.status_code, 403)

    def test_product_options_returns_only_requested_company_data(self):
        self.grant_products_manage()
        self.client.force_login(self.user)

        response = self.client.get(
            self.url,
            {
                "company": self.company_a.pk,
            },
        )

        self.assertEqual(response.status_code, 200)

        data = response.json()

        self.assertEqual(
            data["categories"],
            [
                {
                    "id": self.category_a.pk,
                    "name": "Categoria Options A",
                }
            ],
        )

        self.assertEqual(
            data["brands"],
            [
                {
                    "id": self.brand_a.pk,
                    "name": "Marca Options A",
                }
            ],
        )

        category_names = {
            category["name"]
            for category in data["categories"]
        }

        brand_names = {
            brand["name"]
            for brand in data["brands"]
        }

        self.assertNotIn(
            "Categoria Options B",
            category_names,
        )

        self.assertNotIn(
            "Marca Options B",
            brand_names,
        )

    def test_suspended_membership_does_not_authorize_product_options(self):
        self.grant_products_manage()

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


class CategoryPermissionSeedTests(TestCase):
    def test_categories_manage_permission_is_seeded(self):
        permission = Permission.objects.get(
            code="catalog.categories.manage",
        )

        self.assertEqual(
            permission.scope_behavior,
            Permission.ScopeBehavior.COMPANY_ONLY,
        )


class CategoryCreateApiTests(TestCase):
    def setUp(self):
        self.url = "/api/catalog/categories/"

        self.user = User.objects.create_user(
            username="catalog-category-create-user",
            email="catalog-category-create-user@example.com",
            password="test-password",
        )

        self.company_a = Company.objects.create(
            name="Empresa Category A",
        )
        self.company_b = Company.objects.create(
            name="Empresa Category B",
        )

        self.membership_a = CompanyMembership.objects.create(
            user=self.user,
            company=self.company_a,
            status=CompanyMembership.Status.ACTIVE,
        )

        self.parent_a = Category.objects.create(
            company=self.company_a,
            name="Categoria Padre A",
        )

        self.parent_b = Category.objects.create(
            company=self.company_b,
            name="Categoria Padre B",
        )

    def grant_categories_manage(self):
        permission = Permission.objects.get(
            code=CATEGORIES_MANAGE_PERMISSION_CODE,
        )

        role = CompanyRole.objects.create(
            company=self.company_a,
            name="Catalog Category Manager",
            status=CompanyRole.Status.ACTIVE,
        )

        CompanyRolePermission.objects.create(
            role=role,
            permission=permission,
        )

        RoleAssignment.objects.create(
            membership=self.membership_a,
            role=role,
            branch=None,
        )

    def test_category_create_requires_authentication(self):
        response = self.client.post(
            self.url,
            {
                "company": self.company_a.pk,
                "name": "Categoria Nueva",
            },
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 403)

    def test_category_create_requires_company(self):
        self.client.force_login(self.user)

        response = self.client.post(
            self.url,
            {
                "name": "Categoria Nueva",
            },
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)

    def test_category_create_rejects_invalid_company(self):
        self.client.force_login(self.user)

        response = self.client.post(
            self.url,
            {
                "company": "invalid",
                "name": "Categoria Nueva",
            },
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)

    def test_category_create_denies_company_without_active_membership(self):
        self.client.force_login(self.user)

        response = self.client.post(
            self.url,
            {
                "company": self.company_b.pk,
                "name": "Categoria Nueva",
            },
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 403)

    def test_category_create_denies_without_manage_permission(self):
        self.client.force_login(self.user)

        response = self.client.post(
            self.url,
            {
                "company": self.company_a.pk,
                "name": "Categoria Nueva",
            },
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 403)

    def test_products_manage_permission_does_not_allow_category_create(self):
        permission = Permission.objects.get(
            code=PRODUCTS_MANAGE_PERMISSION_CODE,
        )

        role = CompanyRole.objects.create(
            company=self.company_a,
            name="Catalog Products Only",
            status=CompanyRole.Status.ACTIVE,
        )

        CompanyRolePermission.objects.create(
            role=role,
            permission=permission,
        )

        RoleAssignment.objects.create(
            membership=self.membership_a,
            role=role,
            branch=None,
        )

        self.client.force_login(self.user)

        response = self.client.post(
            self.url,
            {
                "company": self.company_a.pk,
                "name": "Categoria Nueva",
            },
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 403)

    def test_category_create_creates_root_category(self):
        self.grant_categories_manage()
        self.client.force_login(self.user)

        response = self.client.post(
            self.url,
            {
                "company": self.company_a.pk,
                "name": "Categoria Nueva",
            },
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 201)

        category = Category.objects.get(
            company=self.company_a,
            name="Categoria Nueva",
        )

        self.assertIsNone(category.parent)

        self.assertEqual(
            response.json()["category"],
            {
                "id": category.pk,
                "name": "Categoria Nueva",
                "parent": None,
            },
        )

    def test_category_create_allows_parent_from_same_company(self):
        self.grant_categories_manage()
        self.client.force_login(self.user)

        response = self.client.post(
            self.url,
            {
                "company": self.company_a.pk,
                "name": "Subcategoria Nueva",
                "parent": self.parent_a.pk,
            },
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 201)

        category = Category.objects.get(
            company=self.company_a,
            name="Subcategoria Nueva",
        )

        self.assertEqual(
            category.parent,
            self.parent_a,
        )

        self.assertEqual(
            response.json()["category"]["parent"],
            {
                "id": self.parent_a.pk,
                "name": "Categoria Padre A",
            },
        )

    def test_category_create_rejects_parent_from_other_company(self):
        self.grant_categories_manage()
        self.client.force_login(self.user)

        response = self.client.post(
            self.url,
            {
                "company": self.company_a.pk,
                "name": "Subcategoria Invalida",
                "parent": self.parent_b.pk,
            },
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)

        self.assertFalse(
            Category.objects.filter(
                company=self.company_a,
                name="Subcategoria Invalida",
            ).exists()
        )

    def test_suspended_membership_does_not_authorize_category_create(self):
        self.grant_categories_manage()

        self.membership_a.status = CompanyMembership.Status.SUSPENDED
        self.membership_a.save(
            update_fields=["status"],
        )

        self.client.force_login(self.user)

        response = self.client.post(
            self.url,
            {
                "company": self.company_a.pk,
                "name": "Categoria Nueva",
            },
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 403)

    def test_category_list_requires_authentication(self):
        response = self.client.get(
            self.url,
            {
                "company": self.company_a.pk,
            },
        )

        self.assertEqual(response.status_code, 403)

    def test_category_list_requires_company(self):
        self.client.force_login(self.user)

        response = self.client.get(
            self.url,
        )

        self.assertEqual(response.status_code, 400)

    def test_category_list_rejects_invalid_company(self):
        self.client.force_login(self.user)

        response = self.client.get(
            self.url,
            {
                "company": "invalid",
            },
        )

        self.assertEqual(response.status_code, 400)

    def test_category_list_denies_company_without_active_membership(self):
        self.client.force_login(self.user)

        response = self.client.get(
            self.url,
            {
                "company": self.company_b.pk,
            },
        )

        self.assertEqual(response.status_code, 403)

    def test_category_list_denies_without_manage_permission(self):
        self.client.force_login(self.user)

        response = self.client.get(
            self.url,
            {
                "company": self.company_a.pk,
            },
        )

        self.assertEqual(response.status_code, 403)

    def test_category_list_returns_only_company_categories(self):
        child_a = Category.objects.create(
            company=self.company_a,
            parent=self.parent_a,
            name="Subcategoria Lista A",
        )

        self.grant_categories_manage()
        self.client.force_login(self.user)

        response = self.client.get(
            self.url,
            {
                "company": self.company_a.pk,
            },
        )

        self.assertEqual(response.status_code, 200)

        categories = response.json()["categories"]

        self.assertEqual(
            categories,
            [
                {
                    "id": self.parent_a.pk,
                    "name": "Categoria Padre A",
                    "parent": None,
                },
                {
                    "id": child_a.pk,
                    "name": "Subcategoria Lista A",
                    "parent": {
                        "id": self.parent_a.pk,
                        "name": "Categoria Padre A",
                    },
                },
            ],
        )

        category_ids = {
            category["id"]
            for category in categories
        }

        self.assertNotIn(
            self.parent_b.pk,
            category_ids,
        )

    def test_suspended_membership_does_not_authorize_category_list(self):
        self.grant_categories_manage()

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
