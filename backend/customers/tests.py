from django.core.exceptions import ValidationError
from django.test import TestCase

from organizations.models import Company

from .models import Customer
from .serializers import (
    CustomerCreateSerializer,
    CustomerSerializer,
)


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

        serializer = CustomerSerializer(customer)

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
