from django.test import TestCase

# Create your tests here.
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from .models import Branch, Company, Warehouse


class OrganizationModelsTests(TestCase):
    def setUp(self):
        self.company_a = Company.objects.create(name="Empresa A")
        self.company_b = Company.objects.create(name="Empresa B")

        self.branch_a = Branch.objects.create(
            company=self.company_a,
            code="SUC-001",
            name="Sucursal Principal",
        )

    def test_branch_belongs_to_company(self):
        self.assertEqual(self.branch_a.company, self.company_a)
        self.assertIn(self.branch_a, self.company_a.branches.all())

    def test_warehouse_can_belong_to_branch(self):
        warehouse = Warehouse(
            company=self.company_a,
            branch=self.branch_a,
            code="BOD-001",
            name="Bodega Sucursal",
        )

        warehouse.full_clean()
        warehouse.save()

        self.assertEqual(warehouse.company, self.company_a)
        self.assertEqual(warehouse.branch, self.branch_a)

    def test_warehouse_can_exist_without_branch(self):
        warehouse = Warehouse(
            company=self.company_a,
            branch=None,
            code="BOD-CENTRAL",
            name="Bodega Central",
        )

        warehouse.full_clean()
        warehouse.save()

        self.assertIsNone(warehouse.branch)
        self.assertEqual(warehouse.company, self.company_a)

    def test_warehouse_cannot_use_branch_from_another_company(self):
        warehouse = Warehouse(
            company=self.company_b,
            branch=self.branch_a,
            code="BOD-INVALIDA",
            name="Bodega inválida",
        )

        with self.assertRaises(ValidationError) as context:
            warehouse.full_clean()

        self.assertIn("branch", context.exception.message_dict)

    def test_branch_code_is_unique_inside_company(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Branch.objects.create(
                    company=self.company_a,
                    code="SUC-001",
                    name="Otra sucursal",
                )

    def test_same_branch_code_can_exist_in_different_companies(self):
        branch = Branch.objects.create(
            company=self.company_b,
            code="SUC-001",
            name="Sucursal Empresa B",
        )

        self.assertEqual(branch.code, self.branch_a.code)
        self.assertNotEqual(branch.company, self.branch_a.company)

    def test_warehouse_code_is_unique_inside_company(self):
        Warehouse.objects.create(
            company=self.company_a,
            code="BOD-001",
            name="Bodega Uno",
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Warehouse.objects.create(
                    company=self.company_a,
                    code="BOD-001",
                    name="Bodega Dos",
                )

    def test_same_warehouse_code_can_exist_in_different_companies(self):
        warehouse_a = Warehouse.objects.create(
            company=self.company_a,
            code="BOD-001",
            name="Bodega Empresa A",
        )

        warehouse_b = Warehouse.objects.create(
            company=self.company_b,
            code="BOD-001",
            name="Bodega Empresa B",
        )

        self.assertEqual(warehouse_a.code, warehouse_b.code)
        self.assertNotEqual(warehouse_a.company, warehouse_b.company)
