from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from .models import (
    Branch,
    Company,
    CompanyMembership,
    CompanyRole,
    MembershipBranch,
    Permission,
    Warehouse,
)


User = get_user_model()


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


class CompanyMembershipModelsTests(TestCase):
    def setUp(self):
        self.company_a = Company.objects.create(name="Empresa A")
        self.company_b = Company.objects.create(name="Empresa B")

        self.branch_a = Branch.objects.create(
            company=self.company_a,
            code="SUC-A",
            name="Sucursal A",
        )

        self.branch_b = Branch.objects.create(
            company=self.company_b,
            code="SUC-B",
            name="Sucursal B",
        )

        self.user = User.objects.create_user(
            username="felipe",
            email="felipe@example.com",
            password="test-password",
        )

        self.membership = CompanyMembership.objects.create(
            user=self.user,
            company=self.company_a,
        )

    def test_membership_connects_user_and_company(self):
        self.assertEqual(self.membership.user, self.user)
        self.assertEqual(self.membership.company, self.company_a)

    def test_membership_defaults_to_invited(self):
        self.assertEqual(
            self.membership.status,
            CompanyMembership.Status.INVITED,
        )

    def test_user_can_belong_to_different_companies(self):
        second_membership = CompanyMembership.objects.create(
            user=self.user,
            company=self.company_b,
            status=CompanyMembership.Status.ACTIVE,
        )

        self.assertEqual(second_membership.company, self.company_b)

    def test_user_cannot_have_duplicate_membership_inside_company(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                CompanyMembership.objects.create(
                    user=self.user,
                    company=self.company_a,
                )

    def test_membership_can_exist_without_branches(self):
        self.assertFalse(self.membership.branch_memberships.exists())

    def test_membership_can_belong_to_branch_of_same_company(self):
        membership_branch = MembershipBranch(
            membership=self.membership,
            branch=self.branch_a,
        )

        membership_branch.full_clean()
        membership_branch.save()

        self.assertEqual(membership_branch.membership, self.membership)
        self.assertEqual(membership_branch.branch, self.branch_a)

    def test_membership_cannot_use_branch_from_another_company(self):
        membership_branch = MembershipBranch(
            membership=self.membership,
            branch=self.branch_b,
        )

        with self.assertRaises(ValidationError) as context:
            membership_branch.full_clean()

        self.assertIn("branch", context.exception.message_dict)

    def test_membership_branch_cannot_be_duplicated(self):
        MembershipBranch.objects.create(
            membership=self.membership,
            branch=self.branch_a,
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                MembershipBranch.objects.create(
                    membership=self.membership,
                    branch=self.branch_a,
                )


class RbacModelsTests(TestCase):
    def setUp(self):
        self.company_a = Company.objects.create(name="Empresa A")
        self.company_b = Company.objects.create(name="Empresa B")

    def test_permission_code_is_globally_unique(self):
        Permission.objects.create(
            code="products.view",
            scope_behavior=Permission.ScopeBehavior.TENANT_GLOBAL,
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Permission.objects.create(
                    code="products.view",
                    scope_behavior=Permission.ScopeBehavior.BRANCH_SCOPED,
                )

    def test_permission_scope_behaviors_are_the_expected_three(self):
        values = {
            value
            for value, _label in Permission.ScopeBehavior.choices
        }

        self.assertEqual(
            values,
            {
                Permission.ScopeBehavior.COMPANY_ONLY,
                Permission.ScopeBehavior.TENANT_GLOBAL,
                Permission.ScopeBehavior.BRANCH_SCOPED,
            },
        )

    def test_permission_rejects_invalid_scope_behavior(self):
        permission = Permission(
            code="products.invalid",
            scope_behavior="INVALID",
        )

        with self.assertRaises(ValidationError) as context:
            permission.full_clean()

        self.assertIn("scope_behavior", context.exception.message_dict)

    def test_role_belongs_to_company(self):
        role = CompanyRole.objects.create(
            company=self.company_a,
            name="Administrador",
            status=CompanyRole.Status.ACTIVE,
        )

        self.assertEqual(role.company, self.company_a)
        self.assertIn(role, self.company_a.roles.all())

    def test_role_name_is_normalized(self):
        role = CompanyRole.objects.create(
            company=self.company_a,
            name="  Administrador   General  ",
            status=CompanyRole.Status.ACTIVE,
        )

        self.assertEqual(
            role.name_normalized,
            "administrador general",
        )

    def test_valid_role_passes_full_clean(self):
        role = CompanyRole(
            company=self.company_a,
            name="  Administrador   General  ",
            status=CompanyRole.Status.ACTIVE,
        )

        role.full_clean()

        self.assertEqual(
            role.name_normalized,
            "administrador general",
        )

    def test_normalized_role_name_is_unique_inside_company(self):
        CompanyRole.objects.create(
            company=self.company_a,
            name="Administrador General",
            status=CompanyRole.Status.ACTIVE,
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                CompanyRole.objects.create(
                    company=self.company_a,
                    name="  ADMINISTRADOR   GENERAL ",
                    status=CompanyRole.Status.INACTIVE,
                )

    def test_same_role_name_can_exist_in_different_companies(self):
        role_a = CompanyRole.objects.create(
            company=self.company_a,
            name="Administrador",
            status=CompanyRole.Status.ACTIVE,
        )

        role_b = CompanyRole.objects.create(
            company=self.company_b,
            name="ADMINISTRADOR",
            status=CompanyRole.Status.ACTIVE,
        )

        self.assertEqual(
            role_a.name_normalized,
            role_b.name_normalized,
        )
        self.assertNotEqual(role_a.company, role_b.company)

    def test_role_rejects_empty_normalized_name(self):
        role = CompanyRole(
            company=self.company_a,
            name="   ",
            status=CompanyRole.Status.ACTIVE,
        )

        with self.assertRaises(ValidationError) as context:
            role.full_clean()

        self.assertIn("name", context.exception.message_dict)

    def test_role_rejects_invalid_status(self):
        role = CompanyRole(
            company=self.company_a,
            name="Administrador",
            status="INVALID",
        )

        with self.assertRaises(ValidationError) as context:
            role.full_clean()

        self.assertIn("status", context.exception.message_dict)
