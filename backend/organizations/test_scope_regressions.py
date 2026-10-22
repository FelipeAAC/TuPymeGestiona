from django.test import TestCase
from rest_framework.test import APIClient

from accounts.access import has_company_admin_access
from accounts.models import User
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
    Warehouse,
)


class CompanyScopeRegressionTests(TestCase):
    def setUp(self):
        self.admin_permission = Permission.objects.get_or_create(
            code="administration.manage",
            defaults={"scope_behavior": Permission.ScopeBehavior.COMPANY_ONLY},
        )[0]
        self.warehouse_permission = Permission.objects.get_or_create(
            code="organizations.warehouses.manage",
            defaults={"scope_behavior": Permission.ScopeBehavior.BRANCH_SCOPED},
        )[0]
        self.company = Company.objects.create(name="Scoped Company")
        self.other_company = Company.objects.create(name="Other Company")
        self.branch = Branch.objects.create(company=self.company, code="MAIN", name="Main")
        self.other_branch = Branch.objects.create(company=self.company, code="SECOND", name="Second")
        self.cross_company_branch = Branch.objects.create(
            company=self.other_company,
            code="OTHER",
            name="Other branch",
        )
        self.client = APIClient()

    def _user_with_role(self, username, permissions, *, branch=None, company=None):
        company = company or self.company
        user = User.objects.create_user(
            username=username,
            email=f"{username}@example.test",
            password="Strong-password-123!",
        )
        membership = CompanyMembership.objects.create(
            user=user,
            company=company,
            status=CompanyMembership.Status.ACTIVE,
        )
        role = CompanyRole.objects.create(
            company=company,
            name=f"{username} role",
            status=CompanyRole.Status.ACTIVE,
        )
        CompanyRolePermission.objects.bulk_create(
            [CompanyRolePermission(role=role, permission=permission) for permission in permissions]
        )
        if branch is not None:
            MembershipBranch.objects.create(membership=membership, branch=branch)
            RoleAssignment.objects.create(membership=membership, role=role, branch=branch)
        else:
            RoleAssignment.objects.create(membership=membership, role=role)
        return user, membership, role

    def test_company_wide_admin_can_manage_general_warehouse(self):
        user, _, _ = self._user_with_role(
            "company-admin",
            [self.admin_permission, self.warehouse_permission],
        )
        self.client.force_authenticate(user)

        create = self.client.post(
            "/api/organizations/warehouses/",
            {"company": self.company.id, "branch": None, "code": "GENERAL", "name": "General"},
            format="json",
        )
        self.assertEqual(create.status_code, 201, create.data)
        warehouse = Warehouse.objects.get(company=self.company, code="GENERAL")
        self.assertIsNone(warehouse.branch_id)
        self.assertTrue(
            has_permission(
                user=user,
                company=self.company,
                permission_code=self.warehouse_permission.code,
                branch=None,
            )
        )

        listed = self.client.get(
            "/api/organizations/warehouses/",
            {"company": self.company.id},
        )
        self.assertEqual(listed.status_code, 200)
        self.assertIn(warehouse.id, [item["id"] for item in listed.data["warehouses"]])

        updated = self.client.patch(
            f"/api/organizations/warehouses/{warehouse.id}/",
            {"company": self.company.id, "name": "General updated", "branch": None},
            format="json",
        )
        self.assertEqual(updated.status_code, 200, updated.data)
        self.assertEqual(updated.data["warehouse"]["name"], "General updated")

    def test_branch_scoped_user_cannot_cross_branch_or_company(self):
        user, _, _ = self._user_with_role(
            "branch-user",
            [self.warehouse_permission],
            branch=self.branch,
        )
        self.client.force_authenticate(user)

        allowed = self.client.post(
            "/api/organizations/warehouses/",
            {"company": self.company.id, "branch": self.branch.id, "code": "MAIN", "name": "Main warehouse"},
            format="json",
        )
        self.assertEqual(allowed.status_code, 201, allowed.data)
        warehouse = Warehouse.objects.get(company=self.company, code="MAIN")

        denied_create = self.client.post(
            "/api/organizations/warehouses/",
            {"company": self.company.id, "branch": self.other_branch.id, "code": "SECOND", "name": "Second warehouse"},
            format="json",
        )
        self.assertEqual(denied_create.status_code, 403)

        denied_update = self.client.patch(
            f"/api/organizations/warehouses/{warehouse.id}/",
            {"company": self.company.id, "branch": self.other_branch.id},
            format="json",
        )
        self.assertEqual(denied_update.status_code, 403)

        cross_company = self.client.post(
            "/api/organizations/warehouses/",
            {"company": self.company.id, "branch": self.cross_company_branch.id, "code": "CROSS", "name": "Cross"},
            format="json",
        )
        self.assertEqual(cross_company.status_code, 400)
        self.assertFalse(Warehouse.objects.filter(code="CROSS").exists())

    def test_inactive_company_membership_and_role_are_denied(self):
        user, membership, role = self._user_with_role(
            "inactive-user",
            [self.admin_permission, self.warehouse_permission],
        )
        self.assertTrue(has_company_admin_access(user, self.company.id))

        self.company.is_active = False
        self.company.save(update_fields=["is_active"])
        self.assertFalse(has_company_admin_access(user, self.company.id))
        self.client.force_authenticate(user)
        response = self.client.get(
            "/api/organizations/warehouses/",
            {"company": self.company.id},
        )
        self.assertEqual(response.status_code, 403)

        self.company.is_active = True
        self.company.save(update_fields=["is_active"])
        membership.status = CompanyMembership.Status.SUSPENDED
        membership.save(update_fields=["status"])
        self.assertFalse(has_company_admin_access(user, self.company.id))

        membership.status = CompanyMembership.Status.ACTIVE
        membership.save(update_fields=["status"])
        role.status = CompanyRole.Status.INACTIVE
        role.save(update_fields=["status"])
        self.assertFalse(has_company_admin_access(user, self.company.id))

    def test_unrelated_company_admin_cannot_manage_other_company(self):
        user, _, _ = self._user_with_role(
            "other-admin",
            [self.admin_permission, self.warehouse_permission],
            company=self.other_company,
        )
        self.client.force_authenticate(user)

        overview = self.client.get(
            "/api/administration/overview/",
            {"company": self.company.id},
        )
        self.assertEqual(overview.status_code, 404)

        warehouses = self.client.get(
            "/api/organizations/warehouses/",
            {"company": self.company.id},
        )
        self.assertEqual(warehouses.status_code, 403)
