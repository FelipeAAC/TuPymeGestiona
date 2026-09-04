from django.contrib.auth import get_user_model
from django.test import TestCase

from catalog.models import Category, Product
from catalog.views import CATEGORIES_MANAGE_PERMISSION_CODE, PRODUCTS_MANAGE_PERMISSION_CODE
from organizations.models import (
    Company,
    CompanyMembership,
    CompanyRole,
    CompanyRolePermission,
    Permission,
    RoleAssignment,
)

User = get_user_model()


class CatalogQaCorrectionsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="qa-catalog-user",
            email="qa-catalog@example.com",
            password="test-password",
        )
        self.company = Company.objects.create(name="Empresa QA Catalog")
        self.other_company = Company.objects.create(name="Otra Empresa QA")
        self.membership = CompanyMembership.objects.create(
            user=self.user,
            company=self.company,
            status=CompanyMembership.Status.ACTIVE,
        )
        self.active = Category.objects.create(company=self.company, name="Activa")
        self.inactive = Category.objects.create(
            company=self.company,
            name="Inactiva",
            status=Category.Status.INACTIVE,
        )
        self.other = Category.objects.create(company=self.other_company, name="Ajena")
        self._grant_permissions(CATEGORIES_MANAGE_PERMISSION_CODE, PRODUCTS_MANAGE_PERMISSION_CODE)
        self.client.force_login(self.user)

    def _grant_permissions(self, *codes):
        role = CompanyRole.objects.create(
            company=self.company,
            name="QA Catalog Manager",
            status=CompanyRole.Status.ACTIVE,
        )
        for code in codes:
            CompanyRolePermission.objects.create(
                role=role,
                permission=Permission.objects.get(code=code),
            )
        RoleAssignment.objects.create(membership=self.membership, role=role, branch=None)

    def test_category_defaults_to_active(self):
        category = Category.objects.create(company=self.company, name="Nueva")
        self.assertEqual(category.status, Category.Status.ACTIVE)

    def test_management_list_exposes_status_and_tenant_scope(self):
        response = self.client.get(
            "/api/catalog/categories/manage/",
            {"company": self.company.pk},
        )
        self.assertEqual(response.status_code, 200)
        rows = response.json()["categories"]
        by_id = {row["id"]: row for row in rows}
        self.assertEqual(by_id[self.active.pk]["status"], "ACTIVE")
        self.assertEqual(by_id[self.inactive.pk]["status"], "INACTIVE")
        self.assertNotIn(self.other.pk, by_id)

    def test_category_detail_patch_updates_and_disables(self):
        response = self.client.patch(
            f"/api/catalog/categories/{self.active.pk}/",
            {
                "company": self.company.pk,
                "name": "Activa editada",
                "status": "INACTIVE",
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.active.refresh_from_db()
        self.assertEqual(self.active.name, "Activa editada")
        self.assertEqual(self.active.status, Category.Status.INACTIVE)

    def test_category_detail_rejects_parent_from_other_company(self):
        response = self.client.patch(
            f"/api/catalog/categories/{self.active.pk}/",
            {"company": self.company.pk, "parent": self.other.pk},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_product_options_exclude_inactive_categories(self):
        response = self.client.get(
            "/api/catalog/products/options/",
            {"company": self.company.pk},
        )
        self.assertEqual(response.status_code, 200)
        ids = {category["id"] for category in response.json()["categories"]}
        self.assertIn(self.active.pk, ids)
        self.assertNotIn(self.inactive.pk, ids)

    def test_product_status_patch_does_not_require_reselecting_an_inactive_category(self):
        product = Product.objects.create(
            company=self.company,
            category=self.inactive,
            name="Producto legado",
            status=Product.Status.ACTIVE,
        )
        response = self.client.patch(
            f"/api/catalog/products/{product.pk}/",
            {"company": self.company.pk, "status": "INACTIVE"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        product.refresh_from_db()
        self.assertEqual(product.status, Product.Status.INACTIVE)
        self.assertEqual(product.category_id, self.inactive.pk)
