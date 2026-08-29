from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from rest_framework.test import APIClient

from organizations.models import (
    Company,
    CompanyMembership,
    CompanyRole,
    CompanyRolePermission,
    Permission,
    RoleAssignment,
)

from .models import Customer

from .serializers import (
    CustomerCreateSerializer,
    CustomerSerializer,
    CustomerUpdateSerializer,
)

from .views import CUSTOMERS_MANAGE_PERMISSION_CODE


User = get_user_model()


class CustomerModelTests(TestCase):

    def setUp(self):

        self.company = Company.objects.create(
            name="Empresa Test",
        )


    def test_create_customer(self):

        customer = Customer.objects.create(
            company=self.company,
            code="CLI001",
            name="Cliente Uno",
            tax_id="123456789",
            email="cliente@test.com",
            phone="999999999",
        )

        self.assertEqual(
            customer.name,
            "Cliente Uno",
        )

        self.assertEqual(
            customer.company,
            self.company,
        )


    def test_customer_code_unique_per_company(self):

        Customer.objects.create(
            company=self.company,
            code="CLI001",
            name="Cliente Uno",
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Customer.objects.create(
                    company=self.company,
                    code="CLI001",
                    name="Cliente Dos",
                )


    def test_customer_requires_name(self):

        customer = Customer(
            company=self.company,
            code="CLI001",
            name="",
        )

        with self.assertRaises(ValidationError):

            customer.clean()


    def test_customer_requires_code(self):

        customer = Customer(
            company=self.company,
            code="",
            name="Cliente Uno",
        )

        with self.assertRaises(ValidationError):

            customer.clean()


    def test_customers_can_share_code_between_companies(self):

        company_two = Company.objects.create(
            name="Otra Empresa",
        )

        customer_one = Customer.objects.create(
            company=self.company,
            code="CLI001",
            name="Cliente Uno",
        )

        customer_two = Customer.objects.create(
            company=company_two,
            code="CLI001",
            name="Cliente Dos",
        )

        self.assertNotEqual(
            customer_one.company,
            customer_two.company,
        )


    def test_customer_serializer_output(self):

        customer = Customer.objects.create(
            company=self.company,
            code="CLI001",
            name="Cliente Serializer",
            tax_id="12345",
            email="test@test.com",
            phone="111111",
        )

        serializer = CustomerSerializer(
            customer,
        )

        self.assertEqual(
            serializer.data["code"],
            "CLI001",
        )

        self.assertEqual(
            serializer.data["name"],
            "Cliente Serializer",
        )

        self.assertTrue(
            serializer.fields["company"].read_only,
        )


    def test_customer_create_serializer_valid(self):

        data = {
            "code": "CLI002",
            "name": "Cliente Nuevo",
            "tax_id": "98765",
            "email": "nuevo@test.com",
            "phone": "222222",
            "status": "ACTIVE",
        }

        serializer = CustomerCreateSerializer(
            data=data,
            context={
                "company": self.company,
            },
        )

        self.assertTrue(
            serializer.is_valid(),
            serializer.errors,
        )

        customer = serializer.save()

        self.assertEqual(
            customer.company,
            self.company,
        )

        self.assertNotIn(
            "company",
            serializer.fields,
        )


    def test_customer_update_serializer_does_not_expose_company(self):

        customer = Customer.objects.create(
            company=self.company,
            code="CLI003",
            name="Cliente Actualizable",
        )

        serializer = CustomerUpdateSerializer(
            customer,
            data={
                "name": "Cliente Modificado",
            },
            partial=True,
        )

        self.assertTrue(
            serializer.is_valid(),
            serializer.errors,
        )

        self.assertNotIn(
            "company",
            serializer.fields,
        )



class CustomerPermissionApiTests(TestCase):

    def setUp(self):

        self.client = APIClient()


        self.user = User.objects.create_user(
            username="customer-api-user",
            email="customer-api@example.com",
            password="test-password",
        )


        self.company = Company.objects.create(
            name="Empresa Customer API",
        )

        self.other_company = Company.objects.create(
            name="Otra Empresa Customer API",
        )


        self.membership = CompanyMembership.objects.create(
            user=self.user,
            company=self.company,
            status=CompanyMembership.Status.ACTIVE,
        )


        self.permission = Permission.objects.get(
            code="customers.manage",
        )


        self.role = CompanyRole.objects.create(
            company=self.company,
            name="Administrador Clientes",
            status=CompanyRole.Status.ACTIVE,
        )


        CompanyRolePermission.objects.create(
            role=self.role,
            permission=self.permission,
        )


        RoleAssignment.objects.create(
            membership=self.membership,
            role=self.role,
        )



    def test_list_customers_with_permission(self):

        Customer.objects.create(
            company=self.company,
            code="CLI001",
            name="Cliente Permitido",
        )


        self.client.force_login(
            self.user,
        )


        response = self.client.get(
            "/api/customers/",
            {
                "company": self.company.id,
            },
        )


        self.assertEqual(
            response.status_code,
            200,
        )


        self.assertEqual(
            len(response.data["customers"]),
            1,
        )



    def test_create_customer_with_permission(self):

        self.client.force_login(
            self.user,
        )


        response = self.client.post(
            "/api/customers/",
            {
                "company": self.company.id,
                "code": "CLI002",
                "name": "Cliente Nuevo",
            },
            content_type="application/json",
        )


        self.assertEqual(
            response.status_code,
            201,
        )


        self.assertEqual(
            response.data["customer"]["name"],
            "Cliente Nuevo",
        )

        customer = Customer.objects.get(
            code="CLI002",
        )

        self.assertEqual(
            customer.company,
            self.company,
        )



    def test_create_customer_without_permission_returns_403(self):

        RoleAssignment.objects.all().delete()


        self.client.force_login(
            self.user,
        )


        response = self.client.post(
            "/api/customers/",
            {
                "company": self.company.id,
                "code": "CLI003",
                "name": "Cliente Bloqueado",
            },
            content_type="application/json",
        )


        self.assertEqual(
            response.status_code,
            403,
        )


    def test_list_customers_does_not_expose_other_company(self):

        customer = Customer.objects.create(
            company=self.company,
            code="CLI004",
            name="Cliente Visible",
        )

        Customer.objects.create(
            company=self.other_company,
            code="CLI004",
            name="Cliente Oculto",
        )

        self.client.force_login(
            self.user,
        )

        response = self.client.get(
            "/api/customers/",
            {
                "company": self.company.id,
            },
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.assertEqual(
            [item["id"] for item in response.data["customers"]],
            [customer.id],
        )


    def test_create_customer_for_other_company_without_membership_returns_403(self):

        self.client.force_login(
            self.user,
        )

        response = self.client.post(
            "/api/customers/",
            {
                "company": self.other_company.id,
                "code": "CLI005",
                "name": "Cliente Cross Tenant",
            },
            content_type="application/json",
        )

        self.assertEqual(
            response.status_code,
            403,
        )

        self.assertFalse(
            Customer.objects.filter(
                code="CLI005",
            ).exists(),
        )


    def test_create_duplicate_customer_code_returns_400(self):

        Customer.objects.create(
            company=self.company,
            code="CLI006",
            name="Cliente Original",
        )

        self.client.force_login(
            self.user,
        )

        response = self.client.post(
            "/api/customers/",
            {
                "company": self.company.id,
                "code": "CLI006",
                "name": "Cliente Duplicado",
            },
            content_type="application/json",
        )

        self.assertEqual(
            response.status_code,
            400,
        )

        self.assertIn(
            "code",
            response.data,
        )


    def test_suspended_membership_does_not_authorize_customer_create(self):

        self.membership.status = CompanyMembership.Status.SUSPENDED
        self.membership.save(
            update_fields=["status"],
        )

        self.client.force_login(
            self.user,
        )

        response = self.client.post(
            "/api/customers/",
            {
                "company": self.company.id,
                "code": "CLI007",
                "name": "Cliente Suspendido",
            },
            content_type="application/json",
        )

        self.assertEqual(
            response.status_code,
            403,
        )


class CustomerApiPermissionMixin:

    def grant_customers_manage(
        self,
        *,
        company,
        membership,
        role_name,
    ):

        permission = Permission.objects.get(
            code=CUSTOMERS_MANAGE_PERMISSION_CODE,
        )

        role = CompanyRole.objects.create(
            company=company,
            name=role_name,
            status=CompanyRole.Status.ACTIVE,
        )

        CompanyRolePermission.objects.create(
            role=role,
            permission=permission,
        )

        RoleAssignment.objects.create(
            membership=membership,
            role=role,
        )

        return role


class CustomerDetailApiTests(
    CustomerApiPermissionMixin,
    TestCase,
):

    def setUp(self):

        self.user = User.objects.create_user(
            username="customer-detail-user",
            email="customer-detail@example.com",
            password="test-password",
        )

        self.company_a = Company.objects.create(
            name="Empresa Customer Detail A",
        )

        self.company_b = Company.objects.create(
            name="Empresa Customer Detail B",
        )

        self.membership_a = CompanyMembership.objects.create(
            user=self.user,
            company=self.company_a,
            status=CompanyMembership.Status.ACTIVE,
        )

        self.customer_a = Customer.objects.create(
            company=self.company_a,
            code="DET-A",
            name="Cliente Detail A",
            tax_id="11111111-1",
            email="detail-a@example.com",
            phone="+56 9 1111 1111",
        )

        self.customer_b = Customer.objects.create(
            company=self.company_b,
            code="DET-B",
            name="Cliente Detail B",
        )

        self.url = (
            f"/api/customers/{self.customer_a.pk}/"
        )


    def grant_manage(self):

        return self.grant_customers_manage(
            company=self.company_a,
            membership=self.membership_a,
            role_name="Customer Detail Manager",
        )


    def test_customer_detail_requires_authentication(self):

        response = self.client.get(
            self.url,
            {
                "company": self.company_a.pk,
            },
        )

        self.assertEqual(
            response.status_code,
            403,
        )


    def test_customer_detail_requires_company(self):

        self.client.force_login(
            self.user,
        )

        response = self.client.get(
            self.url,
        )

        self.assertEqual(
            response.status_code,
            400,
        )


    def test_customer_detail_rejects_invalid_company(self):

        self.client.force_login(
            self.user,
        )

        response = self.client.get(
            self.url,
            {
                "company": "invalid",
            },
        )

        self.assertEqual(
            response.status_code,
            400,
        )


    def test_customer_detail_denies_without_active_membership(self):

        self.client.force_login(
            self.user,
        )

        response = self.client.get(
            f"/api/customers/{self.customer_b.pk}/",
            {
                "company": self.company_b.pk,
            },
        )

        self.assertEqual(
            response.status_code,
            403,
        )


    def test_customer_detail_denies_without_permission(self):

        self.client.force_login(
            self.user,
        )

        response = self.client.get(
            self.url,
            {
                "company": self.company_a.pk,
            },
        )

        self.assertEqual(
            response.status_code,
            403,
        )


    def test_customer_detail_does_not_expose_other_company(self):

        self.grant_manage()
        self.client.force_login(
            self.user,
        )

        response = self.client.get(
            f"/api/customers/{self.customer_b.pk}/",
            {
                "company": self.company_a.pk,
            },
        )

        self.assertEqual(
            response.status_code,
            404,
        )


    def test_customer_detail_returns_customer(self):

        self.grant_manage()
        self.client.force_login(
            self.user,
        )

        response = self.client.get(
            self.url,
            {
                "company": self.company_a.pk,
            },
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        customer = response.data["customer"]

        self.assertEqual(
            customer["id"],
            self.customer_a.pk,
        )

        self.assertEqual(
            customer["company"],
            self.company_a.pk,
        )

        self.assertEqual(
            customer["code"],
            "DET-A",
        )


    def test_suspended_membership_does_not_authorize_customer_detail(self):

        self.grant_manage()

        self.membership_a.status = CompanyMembership.Status.SUSPENDED
        self.membership_a.save(
            update_fields=["status"],
        )

        self.client.force_login(
            self.user,
        )

        response = self.client.get(
            self.url,
            {
                "company": self.company_a.pk,
            },
        )

        self.assertEqual(
            response.status_code,
            403,
        )


    def test_inactive_role_does_not_authorize_customer_detail(self):

        role = self.grant_manage()
        role.status = CompanyRole.Status.INACTIVE
        role.save(
            update_fields=["status"],
        )

        self.client.force_login(
            self.user,
        )

        response = self.client.get(
            self.url,
            {
                "company": self.company_a.pk,
            },
        )

        self.assertEqual(
            response.status_code,
            403,
        )


class CustomerUpdateApiTests(
    CustomerApiPermissionMixin,
    TestCase,
):

    def setUp(self):

        self.user = User.objects.create_user(
            username="customer-update-user",
            email="customer-update@example.com",
            password="test-password",
        )

        self.company_a = Company.objects.create(
            name="Empresa Customer Update A",
        )

        self.company_b = Company.objects.create(
            name="Empresa Customer Update B",
        )

        self.membership_a = CompanyMembership.objects.create(
            user=self.user,
            company=self.company_a,
            status=CompanyMembership.Status.ACTIVE,
        )

        self.customer_a = Customer.objects.create(
            company=self.company_a,
            code="UPD-A",
            name="Cliente Update A",
            tax_id="11111111-1",
            email="update-a@example.com",
            phone="+56 9 1111 1111",
        )

        self.customer_a_second = Customer.objects.create(
            company=self.company_a,
            code="UPD-A-2",
            name="Cliente Update A Segundo",
        )

        self.customer_b = Customer.objects.create(
            company=self.company_b,
            code="UPD-B",
            name="Cliente Update B",
        )

        self.url = (
            f"/api/customers/{self.customer_a.pk}/"
        )


    def grant_manage_a(self):

        return self.grant_customers_manage(
            company=self.company_a,
            membership=self.membership_a,
            role_name="Customer Update Manager A",
        )


    def test_customer_update_requires_authentication(self):

        response = self.client.patch(
            self.url,
            {
                "company": self.company_a.pk,
                "name": "Cliente Modificado",
            },
            content_type="application/json",
        )

        self.assertEqual(
            response.status_code,
            403,
        )


    def test_customer_update_requires_company(self):

        self.client.force_login(
            self.user,
        )

        response = self.client.patch(
            self.url,
            {
                "name": "Cliente Modificado",
            },
            content_type="application/json",
        )

        self.assertEqual(
            response.status_code,
            400,
        )


    def test_customer_update_rejects_invalid_company(self):

        self.client.force_login(
            self.user,
        )

        response = self.client.patch(
            self.url,
            {
                "company": "invalid",
                "name": "Cliente Modificado",
            },
            content_type="application/json",
        )

        self.assertEqual(
            response.status_code,
            400,
        )


    def test_customer_update_denies_without_permission(self):

        self.client.force_login(
            self.user,
        )

        response = self.client.patch(
            self.url,
            {
                "company": self.company_a.pk,
                "name": "Cliente Modificado",
            },
            content_type="application/json",
        )

        self.assertEqual(
            response.status_code,
            403,
        )


    def test_customer_update_does_not_modify_other_company_customer(self):

        self.grant_manage_a()
        self.client.force_login(
            self.user,
        )

        response = self.client.patch(
            f"/api/customers/{self.customer_b.pk}/",
            {
                "company": self.company_a.pk,
                "name": "Intento Cross Tenant",
            },
            content_type="application/json",
        )

        self.assertEqual(
            response.status_code,
            404,
        )

        self.customer_b.refresh_from_db()

        self.assertEqual(
            self.customer_b.name,
            "Cliente Update B",
        )


    def test_customer_update_cannot_move_customer_to_another_company(self):

        self.grant_manage_a()

        membership_b = CompanyMembership.objects.create(
            user=self.user,
            company=self.company_b,
            status=CompanyMembership.Status.ACTIVE,
        )

        self.grant_customers_manage(
            company=self.company_b,
            membership=membership_b,
            role_name="Customer Update Manager B",
        )

        self.client.force_login(
            self.user,
        )

        response = self.client.patch(
            self.url,
            {
                "company": self.company_b.pk,
                "name": "Intento de Cambio de Empresa",
            },
            content_type="application/json",
        )

        self.assertEqual(
            response.status_code,
            404,
        )

        self.customer_a.refresh_from_db()

        self.assertEqual(
            self.customer_a.company,
            self.company_a,
        )

        self.assertEqual(
            self.customer_a.name,
            "Cliente Update A",
        )


    def test_customer_update_can_modify_editable_fields(self):

        self.grant_manage_a()
        self.client.force_login(
            self.user,
        )

        response = self.client.patch(
            self.url,
            {
                "company": self.company_a.pk,
                "code": "UPD-A-NEW",
                "name": "Cliente Modificado",
                "tax_id": "22222222-2",
                "email": "modified@example.com",
                "phone": "+56 9 9999 9999",
                "status": Customer.Status.INACTIVE,
            },
            content_type="application/json",
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.customer_a.refresh_from_db()

        self.assertEqual(
            self.customer_a.company,
            self.company_a,
        )

        self.assertEqual(
            self.customer_a.code,
            "UPD-A-NEW",
        )

        self.assertEqual(
            self.customer_a.name,
            "Cliente Modificado",
        )

        self.assertEqual(
            self.customer_a.status,
            Customer.Status.INACTIVE,
        )


    def test_customer_update_is_partial(self):

        self.grant_manage_a()
        self.client.force_login(
            self.user,
        )

        response = self.client.patch(
            self.url,
            {
                "company": self.company_a.pk,
                "name": "Solo Nombre Modificado",
            },
            content_type="application/json",
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.customer_a.refresh_from_db()

        self.assertEqual(
            self.customer_a.name,
            "Solo Nombre Modificado",
        )

        self.assertEqual(
            self.customer_a.code,
            "UPD-A",
        )

        self.assertEqual(
            self.customer_a.email,
            "update-a@example.com",
        )


    def test_customer_update_rejects_duplicate_code(self):

        self.grant_manage_a()
        self.client.force_login(
            self.user,
        )

        response = self.client.patch(
            self.url,
            {
                "company": self.company_a.pk,
                "code": self.customer_a_second.code,
            },
            content_type="application/json",
        )

        self.assertEqual(
            response.status_code,
            400,
        )

        self.assertIn(
            "code",
            response.data,
        )

        self.customer_a.refresh_from_db()

        self.assertEqual(
            self.customer_a.code,
            "UPD-A",
        )


    def test_customer_update_rejects_blank_name(self):

        self.grant_manage_a()
        self.client.force_login(
            self.user,
        )

        response = self.client.patch(
            self.url,
            {
                "company": self.company_a.pk,
                "name": "   ",
            },
            content_type="application/json",
        )

        self.assertEqual(
            response.status_code,
            400,
        )

        self.assertIn(
            "name",
            response.data,
        )


    def test_customer_update_rejects_invalid_email(self):

        self.grant_manage_a()
        self.client.force_login(
            self.user,
        )

        response = self.client.patch(
            self.url,
            {
                "company": self.company_a.pk,
                "email": "invalid-email",
            },
            content_type="application/json",
        )

        self.assertEqual(
            response.status_code,
            400,
        )

        self.assertIn(
            "email",
            response.data,
        )


class CustomerListFilterPaginationApiTests(
    CustomerApiPermissionMixin,
    TestCase,
):

    def setUp(self):

        self.client = APIClient()

        self.user = User.objects.create_user(
            username="customer-list-user",
            email="customer-list@example.com",
            password="test-password",
        )

        self.company = Company.objects.create(
            name="Empresa Customer List",
        )

        self.other_company = Company.objects.create(
            name="Otra Empresa Customer List",
        )

        self.membership = CompanyMembership.objects.create(
            user=self.user,
            company=self.company,
            status=CompanyMembership.Status.ACTIVE,
        )

        self.grant_customers_manage(
            company=self.company,
            membership=self.membership,
            role_name="Customer List Manager",
        )

        self.alpha = Customer.objects.create(
            company=self.company,
            code="CLI-100",
            name="Acme Norte",
            tax_id="76.111.111-1",
            email="ventas@acme.test",
            phone="+56 9 1111 1000",
            status=Customer.Status.ACTIVE,
        )

        self.beta = Customer.objects.create(
            company=self.company,
            code="VIP-200",
            name="Beta Sur",
            tax_id="76.222.222-2",
            email="compras@beta.test",
            phone="+56 9 2222 2000",
            status=Customer.Status.INACTIVE,
        )

        self.gamma = Customer.objects.create(
            company=self.company,
            code="CLI-300",
            name="Acme Centro",
            tax_id="77.333.333-3",
            email="contacto@gamma.test",
            phone="+56 9 3333 3000",
            status=Customer.Status.ACTIVE,
        )

        self.repeated_one = Customer.objects.create(
            company=self.company,
            code="ORD-400",
            name="Repetido",
            status=Customer.Status.ACTIVE,
        )

        self.repeated_two = Customer.objects.create(
            company=self.company,
            code="ORD-500",
            name="Repetido",
            status=Customer.Status.ACTIVE,
        )

        self.other_customer = Customer.objects.create(
            company=self.other_company,
            code="CLI-999",
            name="Acme Fantasma",
            tax_id="99.999.999-9",
            email="hidden@example.com",
            phone="+56 9 9999 9999",
        )

        self.client.force_login(
            self.user,
        )


    def list_customers(self, **params):

        return self.client.get(
            "/api/customers/",
            {
                "company": self.company.pk,
                **params,
            },
        )


    def create_pagination_customers(self, count=20):

        customers = []

        for index in range(count):
            customers.append(
                Customer.objects.create(
                    company=self.company,
                    code=f"PAGE-{index:03d}",
                    name=f"Cliente Paginado {index:03d}",
                )
            )

        return customers


    def test_customer_list_uses_default_pagination(self):

        self.create_pagination_customers()

        response = self.list_customers()

        self.assertEqual(
            response.status_code,
            200,
        )

        self.assertEqual(
            len(response.data["customers"]),
            20,
        )

        self.assertEqual(
            response.data["pagination"],
            {
                "count": 25,
                "page": 1,
                "page_size": 20,
                "total_pages": 2,
                "next_page": 2,
                "previous_page": None,
            },
        )


    def test_customer_list_returns_second_page_without_duplicates(self):

        self.create_pagination_customers()

        first_response = self.list_customers()
        second_response = self.list_customers(page=2)

        self.assertEqual(
            second_response.status_code,
            200,
        )

        first_ids = {
            customer["id"]
            for customer in first_response.data["customers"]
        }
        second_ids = {
            customer["id"]
            for customer in second_response.data["customers"]
        }

        self.assertEqual(
            len(second_ids),
            5,
        )

        self.assertFalse(
            first_ids & second_ids,
        )

        self.assertEqual(
            second_response.data["pagination"]["previous_page"],
            1,
        )

        self.assertIsNone(
            second_response.data["pagination"]["next_page"],
        )


    def test_customer_list_accepts_custom_page_size(self):

        response = self.list_customers(
            page=2,
            page_size=2,
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.assertEqual(
            len(response.data["customers"]),
            2,
        )

        self.assertEqual(
            response.data["pagination"],
            {
                "count": 5,
                "page": 2,
                "page_size": 2,
                "total_pages": 3,
                "next_page": 3,
                "previous_page": 1,
            },
        )


    def test_customer_list_rejects_invalid_pagination_values(self):

        invalid_queries = (
            ({"page": "invalid"}, "page"),
            ({"page": 0}, "page"),
            ({"page_size": 0}, "page_size"),
            ({"page_size": 101}, "page_size"),
        )

        for query, error_field in invalid_queries:
            with self.subTest(query=query):
                response = self.list_customers(**query)

                self.assertEqual(
                    response.status_code,
                    400,
                )

                self.assertIn(
                    error_field,
                    response.data,
                )


    def test_customer_list_rejects_page_outside_result_set(self):

        response = self.list_customers(
            page=2,
        )

        self.assertEqual(
            response.status_code,
            400,
        )

        self.assertIn(
            "page",
            response.data,
        )


    def test_customer_list_filters_by_partial_code(self):

        response = self.list_customers(
            code="cli-",
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.assertEqual(
            {
                customer["id"]
                for customer in response.data["customers"]
            },
            {
                self.alpha.pk,
                self.gamma.pk,
            },
        )


    def test_customer_list_filters_by_partial_name(self):

        response = self.list_customers(
            name="ACME",
        )

        self.assertEqual(
            {
                customer["id"]
                for customer in response.data["customers"]
            },
            {
                self.alpha.pk,
                self.gamma.pk,
            },
        )


    def test_customer_list_filters_by_partial_tax_id(self):

        response = self.list_customers(
            tax_id="333.333",
        )

        self.assertEqual(
            [
                customer["id"]
                for customer in response.data["customers"]
            ],
            [self.gamma.pk],
        )


    def test_customer_list_filters_by_status(self):

        response = self.list_customers(
            status=Customer.Status.INACTIVE,
        )

        self.assertEqual(
            [
                customer["id"]
                for customer in response.data["customers"]
            ],
            [self.beta.pk],
        )


    def test_customer_list_rejects_invalid_status(self):

        response = self.list_customers(
            status="SUSPENDED",
        )

        self.assertEqual(
            response.status_code,
            400,
        )

        self.assertIn(
            "status",
            response.data,
        )


    def test_customer_list_searches_across_supported_fields(self):

        searches = (
            ("vip-200", self.beta.pk),
            ("centro", self.gamma.pk),
            ("76.111.111", self.alpha.pk),
            ("compras@beta", self.beta.pk),
            ("9 2222 2000", self.beta.pk),
        )

        for search, expected_id in searches:
            with self.subTest(search=search):
                response = self.list_customers(
                    search=search,
                )

                self.assertEqual(
                    response.status_code,
                    200,
                )

                self.assertEqual(
                    [
                        customer["id"]
                        for customer in response.data["customers"]
                    ],
                    [expected_id],
                )


    def test_customer_list_combines_filters(self):

        response = self.list_customers(
            name="acme",
            status=Customer.Status.ACTIVE,
            search="CLI-300",
        )

        self.assertEqual(
            [
                customer["id"]
                for customer in response.data["customers"]
            ],
            [self.gamma.pk],
        )


    def test_customer_list_uses_id_as_ascending_tiebreaker(self):

        response = self.list_customers(
            name="Repetido",
            ordering="name",
        )

        self.assertEqual(
            [
                customer["id"]
                for customer in response.data["customers"]
            ],
            [
                self.repeated_one.pk,
                self.repeated_two.pk,
            ],
        )


    def test_customer_list_uses_id_as_descending_tiebreaker(self):

        response = self.list_customers(
            name="Repetido",
            ordering="-name",
        )

        self.assertEqual(
            [
                customer["id"]
                for customer in response.data["customers"]
            ],
            [
                self.repeated_two.pk,
                self.repeated_one.pk,
            ],
        )


    def test_customer_list_orders_by_allowed_field(self):

        response = self.list_customers(
            ordering="-code",
        )

        self.assertEqual(
            [
                customer["code"]
                for customer in response.data["customers"]
            ],
            [
                "VIP-200",
                "ORD-500",
                "ORD-400",
                "CLI-300",
                "CLI-100",
            ],
        )


    def test_customer_list_rejects_invalid_ordering(self):

        response = self.list_customers(
            ordering="company",
        )

        self.assertEqual(
            response.status_code,
            400,
        )

        self.assertIn(
            "ordering",
            response.data,
        )


    def test_customer_list_pagination_excludes_other_company(self):

        response = self.list_customers(
            search="Acme",
        )

        returned_ids = {
            customer["id"]
            for customer in response.data["customers"]
        }

        self.assertEqual(
            response.data["pagination"]["count"],
            2,
        )

        self.assertNotIn(
            self.other_customer.pk,
            returned_ids,
        )
