from django.db import IntegrityError, transaction
from django.test import TestCase
from rest_framework.test import APIClient

from administration.services import (
    SelfServiceConflictError,
    create_self_service_company_for_user,
)
from accounts.access import get_access_context, has_customer_access
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


class SelfServiceCompanyAccessTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="customer-onboarding",
            email="customer-onboarding@example.test",
            password="Strong-password-123!",
        )
        self.portal_company = Company.objects.create(name="Portal Store")
        customer = Customer.objects.create(
            company=self.portal_company,
            code="WEB-1",
            name="Customer Onboarding",
            email=self.user.email,
        )
        CustomerPortalAccount.objects.create(
            user=self.user,
            company=self.portal_company,
            customer=customer,
            status=CustomerPortalAccount.Status.ACTIVE,
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.payload = {
            "name": "Onboarding SpA",
            "legal_name": "Onboarding SpA",
            "business_activity": "Servicios",
            "contact_email": "owner@example.test",
            "phone": "+56 9 1234 5678",
            "address": "Av. Principal 123",
            "commune": "Santiago",
            "city": "Santiago",
            "is_active": True,
        }

    def test_customer_creates_company_once_and_keeps_portal_access(self):
        response = self.client.post(
            "/api/administration/self-service/companies/",
            self.payload,
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        company = Company.objects.get(name="Onboarding SpA")
        self.assertEqual(Company.objects.filter(name="Onboarding SpA").count(), 1)
        self.assertEqual(company.branches.get(code="CASA").name, "Casa Matriz")
        membership = CompanyMembership.objects.get(user=self.user, company=company)
        self.assertEqual(membership.status, CompanyMembership.Status.ACTIVE)
        self.assertEqual(membership.primary_for_user_id, self.user.id)
        self.assertEqual(
            CompanyMembership.objects.filter(primary_for_user=self.user).count(), 1
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                CompanyMembership.objects.create(
                    user=self.user,
                    company=Company.objects.create(name="Second Marker Company"),
                    status=CompanyMembership.Status.ACTIVE,
                    primary_for_user=self.user,
                )
        role = CompanyRole.objects.get(company=company, name="Administrador")
        self.assertTrue(
            role.permission_links.filter(permission__code="administration.manage").exists()
        )
        self.assertEqual(response.data["access_context"]["access_modes"], ["CUSTOMER", "COMPANY_ADMIN"])
        self.assertEqual(response.data["access_context"]["default_app"], "choose")
        self.assertNotIn("PLATFORM_ADMIN", response.data["access_context"]["access_modes"])
        self.assertTrue(has_customer_access(self.user))
        self.assertEqual(get_access_context(self.user)["portal_companies"], [{"id": self.portal_company.id, "name": self.portal_company.name}])
        self.assertTrue(response.data["access_context"]["managed_companies"])

    def test_customer_cannot_create_second_primary_company(self):
        first = self.client.post(
            "/api/administration/self-service/companies/",
            self.payload,
            format="json",
        )
        self.assertEqual(first.status_code, 201)

        second = self.client.post(
            "/api/administration/self-service/companies/",
            {**self.payload, "name": "Second SpA", "legal_name": "Second SpA"},
            format="json",
        )

        self.assertEqual(second.status_code, 409)
        self.assertEqual(Company.objects.filter(memberships__user=self.user).count(), 1)

    def test_assigned_company_admin_can_still_create_primary_company(self):
        assigned_company = Company.objects.create(name="Assigned Company")
        membership = CompanyMembership.objects.create(
            user=self.user,
            company=assigned_company,
            status=CompanyMembership.Status.ACTIVE,
        )
        role = CompanyRole.objects.create(
            company=assigned_company,
            name="Assigned Admin",
            status=CompanyRole.Status.ACTIVE,
        )
        permission = Permission.objects.get_or_create(
            code="administration.manage",
            defaults={"scope_behavior": Permission.ScopeBehavior.COMPANY_ONLY},
        )[0]
        CompanyRolePermission.objects.create(role=role, permission=permission)
        RoleAssignment.objects.create(membership=membership, role=role)

        response = self.client.post(
            "/api/administration/self-service/companies/",
            self.payload,
            format="json",
        )

        self.assertEqual(response.status_code, 201, response.data)
        primary = CompanyMembership.objects.get(primary_for_user=self.user)
        self.assertEqual(primary.user_id, self.user.id)
        self.assertNotEqual(primary.company_id, assigned_company.id)

    def test_service_duplicate_conflict_is_controlled(self):
        first = self.client.post(
            "/api/administration/self-service/companies/",
            self.payload,
            format="json",
        )
        self.assertEqual(first.status_code, 201)

        with self.assertRaises(SelfServiceConflictError):
            create_self_service_company_for_user(
                user=self.user,
                company_data={"name": "Race Candidate", "is_active": True},
            )

    def test_non_customer_cannot_use_self_service_onboarding(self):
        user = User.objects.create_user(
            username="admin-only",
            email="admin-only@example.test",
            password="Strong-password-123!",
        )
        company = Company.objects.create(name="Existing Company")
        membership = CompanyMembership.objects.create(
            user=user, company=company, status=CompanyMembership.Status.ACTIVE
        )
        role = CompanyRole.objects.create(
            company=company,
            name="Admin",
            status=CompanyRole.Status.ACTIVE,
        )
        permission = Permission.objects.get_or_create(
            code="administration.manage",
            defaults={"scope_behavior": Permission.ScopeBehavior.COMPANY_ONLY},
        )[0]
        CompanyRolePermission.objects.create(role=role, permission=permission)
        RoleAssignment.objects.create(membership=membership, role=role)

        self.client.force_authenticate(user)
        response = self.client.post(
            "/api/administration/self-service/companies/",
            self.payload,
            format="json",
        )

        self.assertEqual(response.status_code, 403)
