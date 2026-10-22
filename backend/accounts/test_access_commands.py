import json
from io import StringIO
from unittest.mock import patch

from django.core.management import CommandError, call_command
from django.test import TestCase

from accounts.models import User
from organizations.models import Company, CompanyMembership, CompanyRole, CompanyRolePermission, Permission, RoleAssignment
from portal.models import CustomerPortalAccount
from customers.models import Customer


class AccessCommandTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name="Command Company")
        self.permission = Permission.objects.get_or_create(
            code="administration.manage",
            defaults={"scope_behavior": Permission.ScopeBehavior.COMPANY_ONLY},
        )[0]

    def _user(self, *, email, platform_admin=False):
        return User.objects.create_user(
            username=email.split("@", 1)[0],
            email=email,
            password="UnrelatedPassword123!",
            platform_admin=platform_admin,
        )

    def _add_company_admin(self, user):
        membership = CompanyMembership.objects.create(
            user=user,
            company=self.company,
            status=CompanyMembership.Status.ACTIVE,
        )
        role = CompanyRole.objects.create(
            company=self.company,
            name=f"Admin {user.pk}",
            status=CompanyRole.Status.ACTIVE,
        )
        CompanyRolePermission.objects.create(role=role, permission=self.permission)
        RoleAssignment.objects.create(membership=membership, role=role)

    def _add_customer(self, user):
        customer = Customer.objects.create(
            company=self.company,
            code=f"C-{user.pk}",
            name="Portal Customer",
            email=user.email,
        )
        CustomerPortalAccount.objects.create(
            user=user,
            company=self.company,
            customer=customer,
            status=CustomerPortalAccount.Status.ACTIVE,
        )

    def test_promote_platform_admin_by_email_preserves_password(self):
        user = self._user(email="platform@example.test")
        old_hash = user.password
        output = StringIO()

        call_command("promote_platform_admin", email=user.email, stdout=output)

        user.refresh_from_db()
        self.assertTrue(user.platform_admin)
        self.assertEqual(user.password, old_hash)
        self.assertIn(user.email, output.getvalue())
        self.assertNotIn(old_hash, output.getvalue())

    def test_promote_platform_admin_is_idempotent(self):
        user = self._user(email="already@example.test", platform_admin=True)
        old_hash = user.password
        output = StringIO()

        call_command("promote_platform_admin", email=user.email, stdout=output)

        user.refresh_from_db()
        self.assertTrue(user.platform_admin)
        self.assertEqual(user.password, old_hash)
        self.assertIn("ya", output.getvalue().lower())

    def test_promote_platform_admin_rejects_missing_and_unknown_email(self):
        with self.assertRaises(CommandError):
            call_command("promote_platform_admin")
        with self.assertRaises(CommandError):
            call_command("promote_platform_admin", email="unknown@example.test")

    def test_promote_platform_admin_rejects_ambiguous_case_insensitive_email(self):
        first = self._user(email="one@example.test")
        second = self._user(email="two@example.test")
        manager = User.objects
        with patch.object(manager, "filter") as filter_mock:
            filter_mock.return_value.order_by.return_value = [first, second]
            with self.assertRaises(CommandError):
                call_command("promote_platform_admin", email="same@example.test")
        first.refresh_from_db()
        second.refresh_from_db()
        self.assertFalse(first.platform_admin)
        self.assertFalse(second.platform_admin)

    def test_audit_access_modes_is_deterministic_read_only_json(self):
        customer = self._user(email="customer@example.test")
        self._add_customer(customer)
        company_admin = self._user(email="admin@example.test")
        self._add_company_admin(company_admin)
        dual = self._user(email="dual@example.test", platform_admin=True)
        self._add_customer(dual)
        self._add_company_admin(dual)
        unclassified = self._user(email="none@example.test")
        old_flags = {u.pk: u.platform_admin for u in User.objects.all()}

        first_output = StringIO()
        call_command("audit_access_modes", stdout=first_output, format="json")
        second_output = StringIO()
        call_command("audit_access_modes", stdout=second_output, format="json")

        self.assertEqual(first_output.getvalue(), second_output.getvalue())
        report = json.loads(first_output.getvalue())
        self.assertEqual(report["summary"]["total_users"], 4)
        self.assertEqual(report["summary"]["ambiguous"], 1)
        self.assertEqual(report["summary"]["unclassified"], 1)
        rows = {row["email"]: row for row in report["users"]}
        self.assertEqual(rows[customer.email]["access_modes"], ["CUSTOMER"])
        self.assertEqual(rows[company_admin.email]["access_modes"], ["COMPANY_ADMIN"])
        self.assertEqual(rows[dual.email]["access_modes"], ["CUSTOMER", "COMPANY_ADMIN", "PLATFORM_ADMIN"])
        self.assertTrue(rows[dual.email]["ambiguous"])
        self.assertEqual(rows[unclassified.email]["access_modes"], [])
        self.assertEqual(old_flags, {u.pk: u.platform_admin for u in User.objects.all()})
