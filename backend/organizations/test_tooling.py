from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from catalog.models import Product
from customers.models import Customer
from orders.models import Order
from portal.models import CustomerPortalAccount
from organizations.models import Company, CompanyMembership


class DatabaseToolingTests(TestCase):
    def test_mysql_diagnostic_refuses_non_mysql_by_default(self):
        with self.assertRaises(CommandError):
            call_command("diagnose_mysql", strict=True)

    def test_mysql_diagnostic_can_validate_orm_integrity_on_sqlite_for_qa(self):
        call_command("diagnose_mysql", strict=True, allow_non_mysql=True, verbosity=0)

    def test_demo_seed_is_small_configurable_and_idempotent(self):
        options = {
            "seed": "qa-tooling",
            "companies": 1,
            "products": 4,
            "customers": 5,
            "orders": 4,
            "allow_sqlite": True,
            "force_production": True,
            "verbosity": 0,
        }
        call_command("seed_demo_data", **options)

        self.assertEqual(Company.objects.count(), 1)
        self.assertEqual(Product.objects.count(), 4)
        self.assertEqual(Customer.objects.count(), 5)
        self.assertEqual(Order.objects.count(), 4)
        self.assertEqual(CompanyMembership.objects.filter(status="ACTIVE").count(), 4)
        portal_account = CustomerPortalAccount.objects.get()
        self.assertEqual(Order.objects.filter(customer=portal_account.customer).count(), 4)

        before = (
            Company.objects.count(),
            Product.objects.count(),
            Customer.objects.count(),
            Order.objects.count(),
        )
        call_command("seed_demo_data", **options)
        after = (
            Company.objects.count(),
            Product.objects.count(),
            Customer.objects.count(),
            Order.objects.count(),
        )
        self.assertEqual(after, before)
