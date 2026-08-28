from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
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
)


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

        with self.assertRaises(Exception):

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


    def test_customer_create_serializer_valid(self):

        data = {
            "company": self.company.id,
            "code": "CLI002",
            "name": "Cliente Nuevo",
            "tax_id": "98765",
            "email": "nuevo@test.com",
            "phone": "222222",
            "status": "ACTIVE",
        }

        serializer = CustomerCreateSerializer(
            data=data,
        )

        self.assertTrue(
            serializer.is_valid(),
            serializer.errors,
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
