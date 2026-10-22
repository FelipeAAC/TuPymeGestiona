from django.test import TestCase
from rest_framework.test import APIClient

from accounts.access import get_access_context, has_company_admin_access, has_customer_access
from accounts.models import User
from customers.models import Customer
from organizations.models import (
    Company,
    CompanyMembership,
    CompanyRole,
    CompanyRolePermission,
    Permission,
    RoleAssignment,
)
from portal.models import CustomerPortalAccount


class AccessModesTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name="Acme")
        self.user = User.objects.create_user(
            username="access-user", email="access@example.test", password="secret"
        )
        self.permission = Permission.objects.get_or_create(
            code="administration.manage",
            defaults={"scope_behavior": Permission.ScopeBehavior.COMPANY_ONLY},
        )[0]

    def add_portal_access(self, user=None, status=CustomerPortalAccount.Status.ACTIVE):
        user = user or self.user
        customer = Customer.objects.create(company=self.company, code=f"C-{user.pk}", name="Customer")
        return CustomerPortalAccount.objects.create(
            user=user, company=self.company, customer=customer, status=status
        )

    def add_company_admin(self, user=None, membership_status=CompanyMembership.Status.ACTIVE, role_status=CompanyRole.Status.ACTIVE):
        user = user or self.user
        membership = CompanyMembership.objects.create(user=user, company=self.company, status=membership_status)
        role = CompanyRole.objects.create(company=self.company, name=f"Admin {user.pk}", status=role_status)
        CompanyRolePermission.objects.create(role=role, permission=self.permission)
        RoleAssignment.objects.create(membership=membership, role=role)
        return membership

    def test_portal_only_user(self):
        self.add_portal_access()
        context = get_access_context(self.user)
        self.assertEqual(context["access_modes"], ["CUSTOMER"])
        self.assertEqual(context["default_app"], "portal")

    def test_company_admin_only_user(self):
        self.add_company_admin()
        context = get_access_context(self.user)
        self.assertEqual(context["access_modes"], ["COMPANY_ADMIN"])
        self.assertEqual(context["default_app"], "app")

    def test_dual_capability_user(self):
        self.add_portal_access()
        self.add_company_admin()
        context = get_access_context(self.user)
        self.assertEqual(context["access_modes"], ["CUSTOMER", "COMPANY_ADMIN"])
        self.assertEqual(context["default_app"], "choose")

    def test_platform_admin_without_membership(self):
        self.user.platform_admin = True
        self.user.save(update_fields=["platform_admin"])
        context = get_access_context(self.user)
        self.assertEqual(context["access_modes"], ["PLATFORM_ADMIN"])
        self.assertEqual(context["default_app"], "maintainers")

    def test_auth_endpoints_preserve_envelope_and_context(self):
        self.add_portal_access()
        client = APIClient()
        self.assertTrue(client.login(username="access-user", password="secret"))
        me = client.get("/api/auth/me/")
        self.assertEqual(set(me.data), {"user"})
        self.assertEqual(me.data["user"]["access_modes"], ["CUSTOMER"])
        login = client.post("/api/auth/login/", {"identifier": "access-user", "password": "secret"})
        self.assertEqual(set(login.data), {"user"})
        self.assertEqual(login.data["user"]["default_app"], "portal")

    def test_inactive_records_do_not_grant_capability(self):
        self.add_portal_access(status=CustomerPortalAccount.Status.SUSPENDED)
        self.add_company_admin(membership_status=CompanyMembership.Status.SUSPENDED)
        self.assertFalse(has_customer_access(self.user))
        self.assertFalse(has_company_admin_access(self.user))
        self.assertEqual(get_access_context(self.user)["access_modes"], [])

    def test_inactive_role_does_not_grant_capability(self):
        self.add_company_admin(role_status=CompanyRole.Status.INACTIVE)
        self.assertFalse(has_company_admin_access(self.user))

    def test_inactive_company_does_not_grant_capability(self):
        self.add_company_admin()
        self.company.is_active = False
        self.company.save(update_fields=["is_active"])
        self.assertFalse(has_company_admin_access(self.user))
        self.assertEqual(get_access_context(self.user)["managed_companies"], [])

    def test_many_serializer_resolves_each_user_context(self):
        other_company = Company.objects.create(name="Other")
        other = User.objects.create_user(
            username="other-user", email="other@example.test", password="secret"
        )
        CompanyMembership.objects.create(user=other, company=other_company, status=CompanyMembership.Status.ACTIVE)
        role = CompanyRole.objects.create(company=other_company, name="Other Admin", status=CompanyRole.Status.ACTIVE)
        CompanyRolePermission.objects.create(role=role, permission=self.permission)
        RoleAssignment.objects.create(
            membership=other.company_memberships.get(company=other_company), role=role
        )
        from accounts.serializers import CurrentUserSerializer

        payload = CurrentUserSerializer([self.user, other], many=True).data
        self.assertEqual(payload[0]["managed_companies"], [])
        self.assertEqual(payload[1]["managed_companies"], [{"id": other_company.id, "name": "Other"}])
