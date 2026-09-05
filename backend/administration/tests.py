from django.contrib.auth import get_user_model
from django.test import TestCase

from organizations.authorization import has_permission
from organizations.models import (
    Branch,
    Company,
    CompanyMembership,
    CompanyRole,
    CompanyRolePermission,
    MembershipBranch,
    Permission,
    RoleAssignment,
)

from administration.models import CompanySettings, PaymentMethod
from administration.services import ADMIN_PERMISSION_CODE


User = get_user_model()


class AdministrationApiTests(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_user(
            username="admin-user",
            email="admin@example.com",
            password="test-password",
            first_name="Ana",
            last_name="Admin",
        )
        self.company = Company.objects.create(name="Comercial Andina")
        self.other_company = Company.objects.create(name="Empresa Ajena")
        self.branch = Branch.objects.create(
            company=self.company,
            code="CASA",
            name="Casa Matriz",
        )
        self.other_branch = Branch.objects.create(
            company=self.other_company,
            code="OTRA",
            name="Sucursal Ajena",
        )
        self.membership = CompanyMembership.objects.create(
            user=self.admin_user,
            company=self.company,
            status=CompanyMembership.Status.ACTIVE,
        )
        MembershipBranch.objects.create(membership=self.membership, branch=self.branch)
        self.admin_permission = Permission.objects.get(code=ADMIN_PERMISSION_CODE)
        self.orders_permission = Permission.objects.get(code="orders.manage")
        self.role = CompanyRole.objects.create(
            company=self.company,
            name="Administrador",
            status=CompanyRole.Status.ACTIVE,
        )
        CompanyRolePermission.objects.create(role=self.role, permission=self.admin_permission)
        CompanyRolePermission.objects.create(role=self.role, permission=self.orders_permission)
        RoleAssignment.objects.create(membership=self.membership, role=self.role, branch=None)
        self.client.force_login(self.admin_user)

    def test_overview_requires_administration_permission_and_is_company_scoped(self):
        outsider = User.objects.create_user(
            username="outsider",
            email="outsider@example.com",
            password="test-password",
        )
        outsider_membership = CompanyMembership.objects.create(
            user=outsider,
            company=self.other_company,
            status=CompanyMembership.Status.ACTIVE,
        )
        outsider_role = CompanyRole.objects.create(
            company=self.other_company,
            name="Vendedor",
            status=CompanyRole.Status.ACTIVE,
        )
        RoleAssignment.objects.create(
            membership=outsider_membership,
            role=outsider_role,
            branch=None,
        )

        response = self.client.get(
            "/api/administration/overview/",
            {"company": self.company.id},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["company"]["id"], self.company.id)
        self.assertEqual(len(data["branches"]), 1)
        self.assertNotIn("Empresa Ajena", str(data))
        self.assertTrue(any(item["code"] == "CASH" for item in data["payment_methods"]))
        self.assertGreaterEqual(len(data["order_statuses"]), 5)

        self.client.force_login(outsider)
        forbidden = self.client.get(
            "/api/administration/overview/",
            {"company": self.other_company.id},
        )
        self.assertEqual(forbidden.status_code, 404)

    def test_admin_can_create_new_company_and_receives_administrator_membership(self):
        response = self.client.post(
            "/api/administration/companies/",
            data={
                "name": "Nueva Tienda",
                "rut": "76.123.456-0",
                "legal_name": "Nueva Tienda SpA",
                "business_activity": "Comercio",
                "contact_email": "contacto@nueva.cl",
                "is_active": True,
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201, response.content)
        company = Company.objects.get(name="Nueva Tienda")
        membership = CompanyMembership.objects.get(user=self.admin_user, company=company)
        self.assertEqual(membership.status, CompanyMembership.Status.ACTIVE)
        self.assertTrue(
            has_permission(
                user=self.admin_user,
                company=company,
                permission_code=ADMIN_PERMISSION_CODE,
            )
        )
        self.assertTrue(CompanySettings.objects.filter(company=company).exists())

    def test_create_user_hashes_password_and_assigns_role_and_branch(self):
        seller_role = CompanyRole.objects.create(
            company=self.company,
            name="Vendedor",
            status=CompanyRole.Status.ACTIVE,
        )
        response = self.client.post(
            "/api/administration/users/",
            data={
                "company": self.company.id,
                "username": "vendedor1",
                "email": "vendedor1@example.com",
                "first_name": "Valentina",
                "last_name": "Vera",
                "password": "Clave-segura-123",
                "role_ids": [seller_role.id],
                "branch_ids": [self.branch.id],
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201, response.content)
        user = User.objects.get(email="vendedor1@example.com")
        self.assertNotEqual(user.password, "Clave-segura-123")
        self.assertTrue(user.check_password("Clave-segura-123"))
        membership = CompanyMembership.objects.get(user=user, company=self.company)
        self.assertEqual(
            set(membership.branch_memberships.values_list("branch_id", flat=True)),
            {self.branch.id},
        )
        self.assertEqual(
            set(membership.role_assignments.values_list("role_id", flat=True)),
            {seller_role.id},
        )

    def test_existing_global_identity_can_be_linked_without_changing_password(self):
        existing = User.objects.create_user(
            username="shared-user",
            email="shared@example.com",
            password="original-password",
        )
        CompanyMembership.objects.create(
            user=existing,
            company=self.other_company,
            status=CompanyMembership.Status.ACTIVE,
        )
        response = self.client.post(
            "/api/administration/users/",
            data={
                "company": self.company.id,
                "email": "shared@example.com",
                "role_ids": [],
                "branch_ids": [],
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201, response.content)
        existing.refresh_from_db()
        self.assertTrue(existing.check_password("original-password"))
        self.assertTrue(
            CompanyMembership.objects.filter(user=existing, company=self.company).exists()
        )

    def test_admin_cannot_remove_own_last_administration_access(self):
        response = self.client.patch(
            f"/api/administration/users/{self.membership.id}/",
            data={
                "company": self.company.id,
                "role_ids": [],
                "branch_ids": [self.branch.id],
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 409)
        self.assertTrue(has_permission(
            user=self.admin_user,
            company=self.company,
            permission_code=ADMIN_PERMISSION_CODE,
        ))

    def test_create_role_with_selected_permissions(self):
        response = self.client.post(
            "/api/administration/roles/",
            data={
                "company": self.company.id,
                "name": "Supervisor",
                "status": "ACTIVE",
                "permission_codes": ["orders.manage"],
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201, response.content)
        role = CompanyRole.objects.get(company=self.company, name="Supervisor")
        self.assertEqual(
            list(role.permission_links.values_list("permission__code", flat=True)),
            ["orders.manage"],
        )

    def test_create_and_update_branch_with_commercial_fields(self):
        response = self.client.post(
            "/api/administration/branches/",
            data={
                "company": self.company.id,
                "code": "PROV",
                "name": "Providencia",
                "address": "Av. Providencia 123",
                "commune": "Providencia",
                "city": "Santiago",
                "phone": "+56 2 2000 0000",
                "is_active": True,
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201, response.content)
        branch_id = response.json()["branch"]["id"]
        update = self.client.patch(
            f"/api/administration/branches/{branch_id}/",
            data={"company": self.company.id, "phone": "+56 2 2111 1111"},
            content_type="application/json",
        )
        self.assertEqual(update.status_code, 200)
        self.assertEqual(update.json()["branch"]["phone"], "+56 2 2111 1111")

    def test_company_rut_is_validated_and_normalized(self):
        invalid = self.client.patch(
            f"/api/administration/companies/{self.company.id}/",
            data={"rut": "12.345.678-9"},
            content_type="application/json",
        )
        self.assertEqual(invalid.status_code, 400)
        valid = self.client.patch(
            f"/api/administration/companies/{self.company.id}/",
            data={"rut": "12.345.678-5", "legal_name": "Comercial Andina SpA"},
            content_type="application/json",
        )
        self.assertEqual(valid.status_code, 200, valid.content)
        self.assertEqual(valid.json()["company"]["rut"], "12345678-5")

    def test_payment_method_and_settings_are_configurable_without_secrets(self):
        self.client.get("/api/administration/overview/", {"company": self.company.id})
        method = PaymentMethod.objects.get(company=self.company, code="TRANSFER")
        response = self.client.patch(
            f"/api/administration/payment-methods/{method.id}/",
            data={"company": self.company.id, "name": "Transferencia bancaria", "is_active": False},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        settings_response = self.client.patch(
            "/api/administration/settings/",
            data={
                "company": self.company.id,
                "vat_rate": "19.00",
                "currency": "CLP",
                "timezone": "America/Santiago",
                "payment_provider": "MERCADO_PAGO",
                "payment_sandbox_enabled": True,
                "notification_sender_email": "ventas@example.com",
            },
            content_type="application/json",
        )
        self.assertEqual(settings_response.status_code, 200, settings_response.content)
        settings_object = CompanySettings.objects.get(company=self.company)
        self.assertEqual(settings_object.notification_sender_email, "ventas@example.com")
        self.assertNotIn("password", settings_response.json())
        self.assertNotIn("token", settings_response.json())

    def test_order_status_configuration_changes_label_not_operational_code(self):
        overview = self.client.get("/api/administration/overview/", {"company": self.company.id})
        item = overview.json()["order_statuses"][0]
        response = self.client.patch(
            f"/api/administration/order-statuses/{item['id']}/",
            data={
                "company": self.company.id,
                "display_name": "Borrador interno",
                "sort_order": 5,
                "is_active": True,
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["order_status"]["code"], item["code"])
        self.assertEqual(response.json()["order_status"]["display_name"], "Borrador interno")

    def test_context_exposes_effective_permissions_and_all_branches_for_company_wide_role(self):
        Branch.objects.create(company=self.company, code="SEG", name="Segunda")
        response = self.client.get("/api/organizations/context/")
        self.assertEqual(response.status_code, 200)
        membership = response.json()["memberships"][0]
        self.assertIn(ADMIN_PERMISSION_CODE, membership["permissions"])
        self.assertEqual({branch["code"] for branch in membership["branches"]}, {"CASA", "SEG"})

    def test_superuser_permission_helper_bypasses_company_rbac(self):
        superuser = User.objects.create_superuser(
            username="root",
            email="root@example.com",
            password="test-password",
        )
        self.assertTrue(
            has_permission(
                user=superuser,
                company=self.company,
                permission_code=ADMIN_PERMISSION_CODE,
            )
        )
