from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import User
from administration.models import CompanySettings, PaymentMethod
from catalog.models import Brand, Category, Product, ProductVariant, Supplier
from customers.models import Customer
from organizations.models import (
    Branch,
    Company,
    CompanyMembership,
    CompanyRole,
    CompanyRolePermission,
    Permission,
    Warehouse,
)
from portal.models import CustomerPortalAccount
from maintainers.serializers import MaintainerWarehouseSerializer
from maintainers.models import MaintainerAuditEvent


class MaintainerApiTests(TestCase):
    def setUp(self):
        self.platform = User.objects.create_user(
            username="platform",
            email="platform@example.test",
            password="Strong-password-123!",
            platform_admin=True,
        )
        self.company_admin = User.objects.create_user(
            username="company-admin",
            email="admin@example.test",
            password="Strong-password-123!",
        )
        self.customer_user = User.objects.create_user(
            username="customer",
            email="customer@example.test",
            password="Strong-password-123!",
        )
        self.permission = Permission.objects.get_or_create(
            code="administration.manage",
            defaults={"scope_behavior": Permission.ScopeBehavior.COMPANY_ONLY},
        )[0]
        self.company = self._company("Alpha")
        self.other_company = self._company("Beta")
        self.branch = Branch.objects.create(company=self.company, code="HQ", name="Alpha HQ")
        self.other_branch = Branch.objects.create(
            company=self.other_company,
            code="HQ",
            name="Beta HQ",
        )
        self.category = Category.objects.create(company=self.company, name="Alpha Category")
        self.other_category = Category.objects.create(
            company=self.other_company,
            name="Beta Category",
        )
        self.brand = Brand.objects.create(company=self.company, name="Alpha Brand")
        self.other_brand = Brand.objects.create(company=self.other_company, name="Beta Brand")
        self.product = Product.objects.create(
            company=self.company,
            category=self.category,
            brand=self.brand,
            name="Alpha Product",
            status=Product.Status.ACTIVE,
        )
        self.other_product = Product.objects.create(
            company=self.other_company,
            category=self.other_category,
            brand=self.other_brand,
            name="Beta Product",
            status=Product.Status.ACTIVE,
        )
        self.variant = ProductVariant.objects.create(
            product=self.product,
            sku="ALPHA-1",
            base_price="10.00",
            status=ProductVariant.Status.ACTIVE,
        )
        self.other_variant = ProductVariant.objects.create(
            product=self.other_product,
            sku="BETA-1",
            base_price="20.00",
            status=ProductVariant.Status.ACTIVE,
        )
        self.supplier = Supplier.objects.create(company=self.company, name="Alpha Supplier")
        self.other_supplier = Supplier.objects.create(company=self.other_company, name="Beta Supplier")
        self.warehouse = Warehouse.objects.create(
            company=self.company,
            branch=self.branch,
            code="MAIN",
            name="Alpha Warehouse",
        )
        self.other_warehouse = Warehouse.objects.create(
            company=self.other_company,
            branch=self.other_branch,
            code="MAIN",
            name="Beta Warehouse",
        )
        role = CompanyRole.objects.create(
            company=self.company,
            name="Administrator",
            status=CompanyRole.Status.ACTIVE,
        )
        CompanyRolePermission.objects.create(role=role, permission=self.permission)
        CompanyMembership.objects.create(
            user=self.company_admin,
            company=self.company,
            status=CompanyMembership.Status.ACTIVE,
        )
        self.membership = CompanyMembership.objects.get(
            user=self.company_admin,
            company=self.company,
        )
        from organizations.models import RoleAssignment

        RoleAssignment.objects.create(membership=self.membership, role=role)
        customer = Customer.objects.create(
            company=self.company,
            code="CUST-1",
            name="Portal Customer",
            email=self.customer_user.email,
        )
        CustomerPortalAccount.objects.create(
            user=self.customer_user,
            company=self.company,
            customer=customer,
            status=CustomerPortalAccount.Status.ACTIVE,
        )
        self.client = APIClient()

    def _company(self, name):
        return Company.objects.create(
            name=name,
            legal_name=f"{name} SpA",
            rut="",
            is_active=True,
        )

    def _authenticate(self, user):
        self.client.force_authenticate(user)

    def test_unauthenticated_users_receive_normal_authentication_response(self):
        response = self.client.get("/api/maintainers/context/")
        self.assertIn(response.status_code, (401, 403))

    def test_platform_without_membership_sees_context_and_summaries(self):
        self._authenticate(self.platform)

        response = self.client.get("/api/maintainers/context/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["user"]["id"], self.platform.id)
        company = next(item for item in response.data["companies"] if item["id"] == self.company.id)
        self.assertEqual(company["branches_count"], 1)
        self.assertEqual(company["products_count"], 1)
        self.assertEqual(response.data["summary"]["total_companies"], 2)
        self.assertEqual(response.data["summary"]["active_companies"], 2)

    def test_non_platform_users_are_forbidden_on_context_and_mutations(self):
        paths = [
            ("/api/maintainers/context/", "get", None),
            (f"/api/maintainers/companies/{self.company.id}/branches/", "post", {"code": "NEW", "name": "New"}),
            (f"/api/maintainers/companies/{self.company.id}/catalog/products/", "post", {"name": "New", "category": self.category.id, "variant": {"sku": "NEW", "base_price": "1.00"}}),
            (f"/api/maintainers/companies/{self.company.id}/warehouses/", "post", {"branch": self.branch.id, "code": "NEW", "name": "New"}),
        ]
        for user in (self.customer_user, self.company_admin):
            self._authenticate(user)
            for path, method, payload in paths:
                response = getattr(self.client, method)(path, payload, format="json") if payload else getattr(self.client, method)(path)
                self.assertEqual(response.status_code, 403, (user.username, path, response.data))

    def test_platform_reads_are_scoped_to_url_company(self):
        self._authenticate(self.platform)

        overview = self.client.get(f"/api/maintainers/companies/{self.company.id}/overview/")
        self.assertEqual(overview.status_code, 200)
        self.assertEqual({item["id"] for item in overview.data["branches"]}, {self.branch.id})
        self.assertNotIn(self.other_branch.id, {item["id"] for item in overview.data["branches"]})

        catalog = self.client.get(f"/api/maintainers/companies/{self.company.id}/catalog/")
        self.assertEqual(catalog.status_code, 200)
        self.assertEqual([item["id"] for item in catalog.data["products"]], [self.product.id])

        directories = self.client.get(f"/api/maintainers/companies/{self.company.id}/directories/")
        self.assertEqual(directories.status_code, 200)
        self.assertEqual(directories.data["warehouses"][0]["branch_id"], self.branch.id)
        self.assertEqual(directories.data["warehouses"][0]["branch_name"], self.branch.name)

    def test_warehouse_serializer_exposes_compatibility_aliases(self):
        payload = MaintainerWarehouseSerializer(self.warehouse).data
        self.assertEqual(payload["company"], self.company.id)
        self.assertEqual(payload["company_id"], self.company.id)
        self.assertEqual(payload["branch"], self.branch.id)
        self.assertEqual(payload["branch_id"], self.branch.id)

    def test_role_update_rejects_unicode_normalization_collision(self):
        import unicodedata

        self._authenticate(self.platform)
        first = self.client.post(
            f"/api/maintainers/companies/{self.company.id}/roles/",
            {"name": "Café", "status": "ACTIVE", "permission_codes": []},
            format="json",
        )
        second = self.client.post(
            f"/api/maintainers/companies/{self.company.id}/roles/",
            {"name": "Other", "status": "ACTIVE", "permission_codes": []},
            format="json",
        )
        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 201)
        decomposed = unicodedata.normalize("NFD", "Café")
        response = self.client.patch(
            f"/api/maintainers/companies/{self.company.id}/roles/{second.data['role']['id']}/",
            {"name": decomposed, "status": "ACTIVE", "permission_codes": []},
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_platform_mutations_use_url_company_and_reject_cross_company_references(self):
        self._authenticate(self.platform)

        branch = self.client.post(
            f"/api/maintainers/companies/{self.company.id}/branches/",
            {"company": self.other_company.id, "code": "NEW", "name": "New Branch"},
            format="json",
        )
        self.assertEqual(branch.status_code, 201)
        created_branch = Branch.objects.get(pk=branch.data["branch"]["id"])
        self.assertEqual(created_branch.company_id, self.company.id)

        invalid_warehouse = self.client.post(
            f"/api/maintainers/companies/{self.company.id}/warehouses/",
            {"branch": self.other_branch.id, "code": "BAD", "name": "Bad Warehouse"},
            format="json",
        )
        self.assertEqual(invalid_warehouse.status_code, 400)

        invalid_product = self.client.post(
            f"/api/maintainers/companies/{self.company.id}/catalog/products/",
            {
                "name": "Invalid",
                "category": self.other_category.id,
                "brand": self.brand.id,
                "variant": {"sku": "BAD", "base_price": "1.00"},
            },
            format="json",
        )
        self.assertEqual(invalid_product.status_code, 400)

        invalid_variant = self.client.patch(
            f"/api/maintainers/companies/{self.company.id}/catalog/products/{self.product.id}/variants/{self.other_variant.id}/",
            {"base_price": "99.00"},
            format="json",
        )
        self.assertEqual(invalid_variant.status_code, 404)

    def test_user_creation_accepts_mixed_scope_role_using_membership_branches(self):
        self._authenticate(self.platform)
        branch_permission = Permission.objects.create(
            code="maintainers.test.branch_scope",
            scope_behavior=Permission.ScopeBehavior.BRANCH_SCOPED,
        )
        mixed_role = CompanyRole.objects.create(
            company=self.company,
            name="Rol mixto de prueba",
            status=CompanyRole.Status.ACTIVE,
        )
        CompanyRolePermission.objects.create(role=mixed_role, permission=self.permission)
        CompanyRolePermission.objects.create(role=mixed_role, permission=branch_permission)

        response = self.client.post(
            f"/api/maintainers/companies/{self.company.id}/users/",
            {
                "email": "mixed-user@example.test",
                "password": "Strong-password-123!",
                "role_ids": [mixed_role.id],
                "branch_ids": [self.branch.id],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201, response.data)
        created_user = User.objects.get(email="mixed-user@example.test")
        membership = CompanyMembership.objects.get(user=created_user, company=self.company)
        self.assertEqual(
            list(membership.branch_memberships.values_list("branch_id", flat=True)),
            [self.branch.id],
        )
        self.assertTrue(
            membership.role_assignments.filter(role=mixed_role, branch__isnull=True).exists()
        )

    def test_user_creation_rejects_branch_role_without_selected_branch(self):
        self._authenticate(self.platform)
        branch_permission = Permission.objects.create(
            code="maintainers.test.branch_only",
            scope_behavior=Permission.ScopeBehavior.BRANCH_SCOPED,
        )
        branch_role = CompanyRole.objects.create(
            company=self.company,
            name="Rol por sucursal de prueba",
            status=CompanyRole.Status.ACTIVE,
        )
        CompanyRolePermission.objects.create(role=branch_role, permission=branch_permission)

        response = self.client.post(
            f"/api/maintainers/companies/{self.company.id}/users/",
            {
                "email": "branchless-user@example.test",
                "password": "Strong-password-123!",
                "role_ids": [branch_role.id],
                "branch_ids": [],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400, response.data)
        self.assertIn("requieren al menos una sucursal", str(response.data).lower())
        self.assertFalse(User.objects.filter(email="branchless-user@example.test").exists())

    def test_responses_do_not_expose_secrets(self):
        self._authenticate(self.platform)
        CompanySettings.objects.create(company=self.company)
        response = self.client.get(f"/api/maintainers/companies/{self.company.id}/overview/")
        self.assertEqual(response.status_code, 200)
        rendered = str(response.data)
        for secret_name in (
            "password",
            "token",
            "mercado_pago_access_token",
            "smtp_password",
            "sii_secret",
            "caf",
            "pfx",
        ):
            self.assertNotIn(secret_name, rendered.lower())

    def test_platform_can_deactivate_and_reactivate_resources(self):
        self._authenticate(self.platform)
        path = f"/api/maintainers/companies/{self.company.id}/lifecycle/branch/{self.branch.id}/"

        deactivate = self.client.post(path, {"action": "deactivate"}, format="json")
        self.assertEqual(deactivate.status_code, 200, deactivate.data)
        self.branch.refresh_from_db()
        self.assertFalse(self.branch.is_active)

        reactivate = self.client.post(path, {"action": "activate"}, format="json")
        self.assertEqual(reactivate.status_code, 200, reactivate.data)
        self.branch.refresh_from_db()
        self.assertTrue(self.branch.is_active)
        self.assertTrue(
            MaintainerAuditEvent.objects.filter(
                resource_type="branch",
                resource_id=str(self.branch.id),
                event_type="RESOURCE_REACTIVATED",
            ).exists()
        )

    def test_only_delegated_destructive_admin_can_delete_clean_resource(self):
        clean_brand = Brand.objects.create(company=self.company, name="Unused Brand")
        path = f"/api/maintainers/companies/{self.company.id}/lifecycle/brand/{clean_brand.id}/"

        self._authenticate(self.platform)
        forbidden = self.client.post(
            path,
            {"action": "challenge", "confirmation": f"ELIMINAR BRAND {clean_brand.id}", "reason": "Prueba controlada"},
            format="json",
        )
        self.assertEqual(forbidden.status_code, 403)

        self.platform.destructive_admin = True
        self.platform.save(update_fields=["destructive_admin"])
        preview = self.client.get(path)
        self.assertEqual(preview.status_code, 200)
        self.assertTrue(preview.data["can_hard_delete"])

        challenge = self.client.post(
            path,
            {"action": "challenge", "confirmation": preview.data["confirmation_phrase"], "reason": "Eliminar dato de prueba"},
            format="json",
        )
        self.assertEqual(challenge.status_code, 201, challenge.data)
        executed = self.client.post(
            path,
            {
                "action": "execute",
                "challenge_id": challenge.data["challenge_id"],
                "token": challenge.data["token"],
                "confirmation": preview.data["confirmation_phrase"],
            },
            format="json",
        )
        self.assertEqual(executed.status_code, 200, executed.data)
        self.assertFalse(Brand.objects.filter(pk=clean_brand.id).exists())
        self.assertTrue(
            MaintainerAuditEvent.objects.filter(
                resource_type="brand",
                resource_id=str(clean_brand.id),
                event_type="RESOURCE_HARD_DELETED",
            ).exists()
        )

    def test_hard_delete_preview_blocks_resources_with_history(self):
        self.platform.destructive_admin = True
        self.platform.save(update_fields=["destructive_admin"])
        self._authenticate(self.platform)
        path = f"/api/maintainers/companies/{self.company.id}/lifecycle/product/{self.product.id}/"
        response = self.client.get(path)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data["can_hard_delete"])
        self.assertTrue(response.data["impact"])
        self.assertEqual(
            self.client.post(
                path,
                {"action": "challenge", "confirmation": response.data["confirmation_phrase"], "reason": "Recurso de prueba con historial"},
                format="json",
            ).status_code,
            409,
        )

    def test_revoke_user_access_removes_roles_and_branches_but_keeps_identity(self):
        self._authenticate(self.platform)
        response = self.client.post(
            f"/api/maintainers/companies/{self.company.id}/users/{self.membership.id}/revoke/",
            {},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.membership.refresh_from_db()
        self.assertEqual(self.membership.status, CompanyMembership.Status.LEFT)
        self.assertFalse(self.membership.branch_memberships.exists())
        self.assertFalse(self.membership.role_assignments.exists())
        self.assertTrue(User.objects.filter(pk=self.company_admin.id).exists())

    def test_empty_company_can_be_deleted_after_generated_configuration_is_cleaned(self):
        from maintainers.services import prepare_company

        empty = Company.objects.create(name="Empty test company")
        prepare_company(empty)
        self.platform.destructive_admin = True
        self.platform.save(update_fields=["destructive_admin"])
        self._authenticate(self.platform)
        path = f"/api/maintainers/companies/{empty.id}/lifecycle/company/{empty.id}/"
        preview = self.client.get(path)
        self.assertEqual(preview.status_code, 200)
        self.assertTrue(preview.data["can_hard_delete"], preview.data)
        challenge = self.client.post(
            path,
            {
                "action": "challenge",
                "confirmation": preview.data["confirmation_phrase"],
                "reason": "Eliminar empresa de prueba vacía",
            },
            format="json",
        )
        self.assertEqual(challenge.status_code, 201, challenge.data)
        executed = self.client.post(
            path,
            {
                "action": "execute",
                "challenge_id": challenge.data["challenge_id"],
                "token": challenge.data["token"],
                "confirmation": preview.data["confirmation_phrase"],
            },
            format="json",
        )
        self.assertEqual(executed.status_code, 200, executed.data)
        self.assertFalse(Company.objects.filter(pk=empty.id).exists())

    def test_assigned_role_cannot_be_deleted_until_access_is_reassigned(self):
        self.platform.destructive_admin = True
        self.platform.save(update_fields=["destructive_admin"])
        self._authenticate(self.platform)
        path = f"/api/maintainers/companies/{self.company.id}/lifecycle/role/{self.membership.role_assignments.first().role_id}/"
        preview = self.client.get(path)
        self.assertEqual(preview.status_code, 200)
        self.assertFalse(preview.data["can_hard_delete"])
        self.assertTrue(any(item["relation"] == "assignments" for item in preview.data["impact"]))
