from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from .authorization import has_permission
from .models import (
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


class WarehousePermissionSeedTests(TestCase):
    def test_warehouses_manage_permission_is_seeded(self):
        permission = Permission.objects.get(
            code="organizations.warehouses.manage",
        )

        self.assertEqual(
            permission.scope_behavior,
            Permission.ScopeBehavior.BRANCH_SCOPED,
        )


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

    def test_role_can_exist_without_permissions(self):
        role = CompanyRole.objects.create(
            company=self.company_a,
            name="Operador",
            status=CompanyRole.Status.ACTIVE,
        )

        self.assertFalse(role.permission_links.exists())

    def test_role_permission_connects_role_and_permission(self):
        role = CompanyRole.objects.create(
            company=self.company_a,
            name="Operador",
            status=CompanyRole.Status.ACTIVE,
        )

        permission = Permission.objects.create(
            code="products.view",
            scope_behavior=Permission.ScopeBehavior.TENANT_GLOBAL,
        )

        role_permission = CompanyRolePermission.objects.create(
            role=role,
            permission=permission,
        )

        self.assertEqual(role_permission.role, role)
        self.assertEqual(role_permission.permission, permission)
        self.assertIn(role_permission, role.permission_links.all())
        self.assertIn(role_permission, permission.role_links.all())

    def test_role_can_have_multiple_permissions(self):
        role = CompanyRole.objects.create(
            company=self.company_a,
            name="Operador",
            status=CompanyRole.Status.ACTIVE,
        )

        permission_view = Permission.objects.create(
            code="products.view",
            scope_behavior=Permission.ScopeBehavior.TENANT_GLOBAL,
        )

        permission_edit = Permission.objects.create(
            code="products.edit",
            scope_behavior=Permission.ScopeBehavior.TENANT_GLOBAL,
        )

        CompanyRolePermission.objects.create(
            role=role,
            permission=permission_view,
        )
        CompanyRolePermission.objects.create(
            role=role,
            permission=permission_edit,
        )

        self.assertEqual(role.permission_links.count(), 2)

    def test_same_permission_can_be_used_by_roles_from_different_companies(self):
        permission = Permission.objects.create(
            code="products.view",
            scope_behavior=Permission.ScopeBehavior.TENANT_GLOBAL,
        )

        role_a = CompanyRole.objects.create(
            company=self.company_a,
            name="Operador",
            status=CompanyRole.Status.ACTIVE,
        )

        role_b = CompanyRole.objects.create(
            company=self.company_b,
            name="Operador",
            status=CompanyRole.Status.ACTIVE,
        )

        CompanyRolePermission.objects.create(
            role=role_a,
            permission=permission,
        )
        CompanyRolePermission.objects.create(
            role=role_b,
            permission=permission,
        )

        self.assertEqual(permission.role_links.count(), 2)

    def test_role_permission_cannot_be_duplicated(self):
        role = CompanyRole.objects.create(
            company=self.company_a,
            name="Operador",
            status=CompanyRole.Status.ACTIVE,
        )

        permission = Permission.objects.create(
            code="products.view",
            scope_behavior=Permission.ScopeBehavior.TENANT_GLOBAL,
        )

        CompanyRolePermission.objects.create(
            role=role,
            permission=permission,
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                CompanyRolePermission.objects.create(
                    role=role,
                    permission=permission,
                )

    def test_role_assignment_can_be_company_wide(self):
        user = User.objects.create_user(
            username="company-user",
            email="company-user@example.com",
            password="test-password",
        )

        membership = CompanyMembership.objects.create(
            user=user,
            company=self.company_a,
            status=CompanyMembership.Status.ACTIVE,
        )

        role = CompanyRole.objects.create(
            company=self.company_a,
            name="Administrador",
            status=CompanyRole.Status.ACTIVE,
        )

        assignment = RoleAssignment(
            membership=membership,
            role=role,
            branch=None,
        )

        assignment.full_clean()
        assignment.save()

        self.assertIsNone(assignment.branch)

    def test_role_assignment_can_be_branch_scoped(self):
        user = User.objects.create_user(
            username="branch-user",
            email="branch-user@example.com",
            password="test-password",
        )

        membership = CompanyMembership.objects.create(
            user=user,
            company=self.company_a,
            status=CompanyMembership.Status.ACTIVE,
        )

        branch = Branch.objects.create(
            company=self.company_a,
            code="SUC-RBAC",
            name="Sucursal RBAC",
        )

        MembershipBranch.objects.create(
            membership=membership,
            branch=branch,
        )

        role = CompanyRole.objects.create(
            company=self.company_a,
            name="Vendedor",
            status=CompanyRole.Status.ACTIVE,
        )

        assignment = RoleAssignment(
            membership=membership,
            role=role,
            branch=branch,
        )

        assignment.full_clean()
        assignment.save()

        self.assertEqual(assignment.branch, branch)

    def test_role_assignment_rejects_role_from_another_company(self):
        user = User.objects.create_user(
            username="wrong-role-user",
            email="wrong-role@example.com",
            password="test-password",
        )

        membership = CompanyMembership.objects.create(
            user=user,
            company=self.company_a,
        )

        role = CompanyRole.objects.create(
            company=self.company_b,
            name="Rol Empresa B",
            status=CompanyRole.Status.ACTIVE,
        )

        assignment = RoleAssignment(
            membership=membership,
            role=role,
        )

        with self.assertRaises(ValidationError) as context:
            assignment.full_clean()

        self.assertIn("role", context.exception.message_dict)

    def test_branch_assignment_requires_membership_branch(self):
        user = User.objects.create_user(
            username="no-branch-user",
            email="no-branch@example.com",
            password="test-password",
        )

        membership = CompanyMembership.objects.create(
            user=user,
            company=self.company_a,
        )

        branch = Branch.objects.create(
            company=self.company_a,
            code="SUC-NO-MB",
            name="Sucursal Sin Adscripcion",
        )

        role = CompanyRole.objects.create(
            company=self.company_a,
            name="Operador Sucursal",
            status=CompanyRole.Status.ACTIVE,
        )

        assignment = RoleAssignment(
            membership=membership,
            role=role,
            branch=branch,
        )

        with self.assertRaises(ValidationError) as context:
            assignment.full_clean()

        self.assertIn("branch", context.exception.message_dict)

    def test_cannot_mix_company_wide_and_branch_assignments(self):
        user = User.objects.create_user(
            username="mixed-scope-user",
            email="mixed-scope@example.com",
            password="test-password",
        )

        membership = CompanyMembership.objects.create(
            user=user,
            company=self.company_a,
        )

        branch = Branch.objects.create(
            company=self.company_a,
            code="SUC-MIX",
            name="Sucursal Mix",
        )

        MembershipBranch.objects.create(
            membership=membership,
            branch=branch,
        )

        role = CompanyRole.objects.create(
            company=self.company_a,
            name="Rol Mixto",
            status=CompanyRole.Status.ACTIVE,
        )

        RoleAssignment.objects.create(
            membership=membership,
            role=role,
            branch=None,
        )

        branch_assignment = RoleAssignment(
            membership=membership,
            role=role,
            branch=branch,
        )

        with self.assertRaises(ValidationError) as context:
            branch_assignment.full_clean()

        self.assertIn("branch", context.exception.message_dict)

    def test_company_only_permission_blocks_branch_assignment(self):
        user = User.objects.create_user(
            username="company-only-user",
            email="company-only@example.com",
            password="test-password",
        )

        membership = CompanyMembership.objects.create(
            user=user,
            company=self.company_a,
        )

        branch = Branch.objects.create(
            company=self.company_a,
            code="SUC-COMPANY-ONLY",
            name="Sucursal Company Only",
        )

        MembershipBranch.objects.create(
            membership=membership,
            branch=branch,
        )

        role = CompanyRole.objects.create(
            company=self.company_a,
            name="Administrador Empresa",
            status=CompanyRole.Status.ACTIVE,
        )

        permission = Permission.objects.create(
            code="company.manage",
            scope_behavior=Permission.ScopeBehavior.COMPANY_ONLY,
        )

        CompanyRolePermission.objects.create(
            role=role,
            permission=permission,
        )

        assignment = RoleAssignment(
            membership=membership,
            role=role,
            branch=branch,
        )

        with self.assertRaises(ValidationError) as context:
            assignment.full_clean()

        self.assertIn("branch", context.exception.message_dict)

    def test_company_only_permission_cannot_be_added_after_branch_assignment(self):
        user = User.objects.create_user(
            username="late-company-only-user",
            email="late-company-only@example.com",
            password="test-password",
        )

        membership = CompanyMembership.objects.create(
            user=user,
            company=self.company_a,
        )

        branch = Branch.objects.create(
            company=self.company_a,
            code="SUC-LATE",
            name="Sucursal Late",
        )

        MembershipBranch.objects.create(
            membership=membership,
            branch=branch,
        )

        role = CompanyRole.objects.create(
            company=self.company_a,
            name="Operador Branch",
            status=CompanyRole.Status.ACTIVE,
        )

        RoleAssignment.objects.create(
            membership=membership,
            role=role,
            branch=branch,
        )

        permission = Permission.objects.create(
            code="company.settings.manage",
            scope_behavior=Permission.ScopeBehavior.COMPANY_ONLY,
        )

        link = CompanyRolePermission(
            role=role,
            permission=permission,
        )

        with self.assertRaises(ValidationError) as context:
            link.full_clean()

        self.assertIn("permission", context.exception.message_dict)

    def test_duplicate_company_wide_assignment_is_rejected(self):
        user = User.objects.create_user(
            username="duplicate-company-user",
            email="duplicate-company@example.com",
            password="test-password",
        )

        membership = CompanyMembership.objects.create(
            user=user,
            company=self.company_a,
        )

        role = CompanyRole.objects.create(
            company=self.company_a,
            name="Rol Company Duplicate",
            status=CompanyRole.Status.ACTIVE,
        )

        RoleAssignment.objects.create(
            membership=membership,
            role=role,
            branch=None,
        )

        with self.assertRaises(ValidationError):
            RoleAssignment.objects.create(
                membership=membership,
                role=role,
                branch=None,
            )

    def test_cannot_create_company_wide_after_branch_assignment(self):
        user = User.objects.create_user(
            username="reverse-mixed-user",
            email="reverse-mixed@example.com",
            password="test-password",
        )

        membership = CompanyMembership.objects.create(
            user=user,
            company=self.company_a,
        )

        branch = Branch.objects.create(
            company=self.company_a,
            code="SUC-REVERSE-MIX",
            name="Sucursal Reverse Mix",
        )

        MembershipBranch.objects.create(
            membership=membership,
            branch=branch,
        )

        role = CompanyRole.objects.create(
            company=self.company_a,
            name="Rol Reverse Mix",
            status=CompanyRole.Status.ACTIVE,
        )

        RoleAssignment.objects.create(
            membership=membership,
            role=role,
            branch=branch,
        )

        with self.assertRaises(ValidationError):
            RoleAssignment.objects.create(
                membership=membership,
                role=role,
                branch=None,
            )


class EffectivePermissionTests(TestCase):
    def setUp(self):
        self.company_a = Company.objects.create(
            name="Empresa Permission A",
        )
        self.company_b = Company.objects.create(
            name="Empresa Permission B",
        )

        self.branch_a = Branch.objects.create(
            company=self.company_a,
            code="SUC-PERM-A",
            name="Sucursal Permission A",
        )
        self.branch_a_2 = Branch.objects.create(
            company=self.company_a,
            code="SUC-PERM-A2",
            name="Sucursal Permission A 2",
        )
        self.branch_b = Branch.objects.create(
            company=self.company_b,
            code="SUC-PERM-B",
            name="Sucursal Permission B",
        )

        self.user = User.objects.create_user(
            username="permission-user",
            email="permission-user@example.com",
            password="test-password",
        )

        self.membership = CompanyMembership.objects.create(
            user=self.user,
            company=self.company_a,
            status=CompanyMembership.Status.ACTIVE,
        )

        MembershipBranch.objects.create(
            membership=self.membership,
            branch=self.branch_a,
        )

    def create_role_with_permission(
        self,
        *,
        permission_code,
        scope_behavior,
        branch=None,
        role_status=CompanyRole.Status.ACTIVE,
    ):
        permission = Permission.objects.create(
            code=permission_code,
            scope_behavior=scope_behavior,
        )

        role = CompanyRole.objects.create(
            company=self.company_a,
            name=f"Rol {permission_code}",
            status=role_status,
        )

        CompanyRolePermission.objects.create(
            role=role,
            permission=permission,
        )

        RoleAssignment.objects.create(
            membership=self.membership,
            role=role,
            branch=branch,
        )

        return permission, role

    def test_company_only_permission_requires_company_wide_assignment(self):
        self.create_role_with_permission(
            permission_code="company.settings.manage",
            scope_behavior=Permission.ScopeBehavior.COMPANY_ONLY,
            branch=None,
        )

        self.assertTrue(
            has_permission(
                user=self.user,
                company=self.company_a,
                permission_code="company.settings.manage",
            )
        )

    def test_tenant_global_permission_allows_company_wide_assignment(self):
        self.create_role_with_permission(
            permission_code="products.view",
            scope_behavior=Permission.ScopeBehavior.TENANT_GLOBAL,
            branch=None,
        )

        self.assertTrue(
            has_permission(
                user=self.user,
                company=self.company_a,
                permission_code="products.view",
            )
        )

    def test_tenant_global_permission_allows_branch_assignment(self):
        self.create_role_with_permission(
            permission_code="customers.view",
            scope_behavior=Permission.ScopeBehavior.TENANT_GLOBAL,
            branch=self.branch_a,
        )

        self.assertTrue(
            has_permission(
                user=self.user,
                company=self.company_a,
                permission_code="customers.view",
            )
        )

    def test_branch_scoped_company_wide_assignment_allows_any_company_branch(self):
        self.create_role_with_permission(
            permission_code="inventory.view",
            scope_behavior=Permission.ScopeBehavior.BRANCH_SCOPED,
            branch=None,
        )

        self.assertTrue(
            has_permission(
                user=self.user,
                company=self.company_a,
                permission_code="inventory.view",
                branch=self.branch_a,
            )
        )

        self.assertTrue(
            has_permission(
                user=self.user,
                company=self.company_a,
                permission_code="inventory.view",
                branch=self.branch_a_2,
            )
        )

    def test_branch_scoped_branch_assignment_allows_matching_branch(self):
        self.create_role_with_permission(
            permission_code="sales.create",
            scope_behavior=Permission.ScopeBehavior.BRANCH_SCOPED,
            branch=self.branch_a,
        )

        self.assertTrue(
            has_permission(
                user=self.user,
                company=self.company_a,
                permission_code="sales.create",
                branch=self.branch_a,
            )
        )

    def test_branch_scoped_branch_assignment_denies_other_branch(self):
        self.create_role_with_permission(
            permission_code="orders.manage",
            scope_behavior=Permission.ScopeBehavior.BRANCH_SCOPED,
            branch=self.branch_a,
        )

        self.assertFalse(
            has_permission(
                user=self.user,
                company=self.company_a,
                permission_code="orders.manage",
                branch=self.branch_a_2,
            )
        )

    def test_branch_scoped_branch_assignment_requires_branch_context(self):
        self.create_role_with_permission(
            permission_code="inventory.adjust",
            scope_behavior=Permission.ScopeBehavior.BRANCH_SCOPED,
            branch=self.branch_a,
        )

        self.assertFalse(
            has_permission(
                user=self.user,
                company=self.company_a,
                permission_code="inventory.adjust",
            )
        )

    def test_non_active_membership_does_not_authorize(self):
        self.create_role_with_permission(
            permission_code="products.edit",
            scope_behavior=Permission.ScopeBehavior.TENANT_GLOBAL,
            branch=None,
        )

        for status in (
            CompanyMembership.Status.INVITED,
            CompanyMembership.Status.SUSPENDED,
            CompanyMembership.Status.LEFT,
        ):
            with self.subTest(status=status):
                self.membership.status = status
                self.membership.save(update_fields=["status"])

                self.assertFalse(
                    has_permission(
                        user=self.user,
                        company=self.company_a,
                        permission_code="products.edit",
                    )
                )

        self.membership.status = CompanyMembership.Status.ACTIVE
        self.membership.save(update_fields=["status"])

    def test_inactive_role_does_not_authorize(self):
        self.create_role_with_permission(
            permission_code="customers.edit",
            scope_behavior=Permission.ScopeBehavior.TENANT_GLOBAL,
            branch=None,
            role_status=CompanyRole.Status.INACTIVE,
        )

        self.assertFalse(
            has_permission(
                user=self.user,
                company=self.company_a,
                permission_code="customers.edit",
            )
        )

    def test_assignment_from_other_company_does_not_authorize(self):
        other_membership = CompanyMembership.objects.create(
            user=self.user,
            company=self.company_b,
            status=CompanyMembership.Status.ACTIVE,
        )

        permission = Permission.objects.create(
            code="reports.view",
            scope_behavior=Permission.ScopeBehavior.TENANT_GLOBAL,
        )

        role = CompanyRole.objects.create(
            company=self.company_b,
            name="Rol Reports B",
            status=CompanyRole.Status.ACTIVE,
        )

        CompanyRolePermission.objects.create(
            role=role,
            permission=permission,
        )

        RoleAssignment.objects.create(
            membership=other_membership,
            role=role,
            branch=None,
        )

        self.assertFalse(
            has_permission(
                user=self.user,
                company=self.company_a,
                permission_code="reports.view",
            )
        )

    def test_branch_from_other_company_does_not_authorize(self):
        self.create_role_with_permission(
            permission_code="stock.view",
            scope_behavior=Permission.ScopeBehavior.BRANCH_SCOPED,
            branch=None,
        )

        self.assertFalse(
            has_permission(
                user=self.user,
                company=self.company_a,
                permission_code="stock.view",
                branch=self.branch_b,
            )
        )

    def test_unknown_permission_code_does_not_authorize(self):
        self.assertFalse(
            has_permission(
                user=self.user,
                company=self.company_a,
                permission_code="permission.does.not.exist",
            )
        )

    def test_permission_is_resolved_by_code_not_role_name(self):
        role = CompanyRole.objects.create(
            company=self.company_a,
            name="products.delete",
            status=CompanyRole.Status.ACTIVE,
        )

        RoleAssignment.objects.create(
            membership=self.membership,
            role=role,
            branch=None,
        )

        self.assertFalse(
            has_permission(
                user=self.user,
                company=self.company_a,
                permission_code="products.delete",
            )
        )


class OrganizationContextApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="context-user",
            email="context-user@example.com",
            password="test-password",
        )

        self.other_user = User.objects.create_user(
            username="other-context-user",
            email="other-context-user@example.com",
            password="test-password",
        )

        self.company_a = Company.objects.create(name="Empresa A")
        self.company_b = Company.objects.create(name="Empresa B")
        self.company_c = Company.objects.create(name="Empresa C")

        self.active_membership = CompanyMembership.objects.create(
            user=self.user,
            company=self.company_a,
            status=CompanyMembership.Status.ACTIVE,
        )

        self.suspended_membership = CompanyMembership.objects.create(
            user=self.user,
            company=self.company_b,
            status=CompanyMembership.Status.SUSPENDED,
        )

        self.other_membership = CompanyMembership.objects.create(
            user=self.other_user,
            company=self.company_c,
            status=CompanyMembership.Status.ACTIVE,
        )

        self.branch_a = Branch.objects.create(
            company=self.company_a,
            code="SUC-CONTEXT-1",
            name="Sucursal Contexto 1",
        )

        self.branch_a_2 = Branch.objects.create(
            company=self.company_a,
            code="SUC-CONTEXT-2",
            name="Sucursal Contexto 2",
        )

        MembershipBranch.objects.create(
            membership=self.active_membership,
            branch=self.branch_a,
        )

        MembershipBranch.objects.create(
            membership=self.active_membership,
            branch=self.branch_a_2,
        )

    def test_context_requires_authentication(self):
        response = self.client.get(
            "/api/organizations/context/",
        )

        self.assertEqual(response.status_code, 403)

    def test_context_returns_active_memberships_for_current_user(self):
        self.client.force_login(self.user)

        response = self.client.get(
            "/api/organizations/context/",
        )

        self.assertEqual(response.status_code, 200)

        memberships = response.json()["memberships"]

        self.assertEqual(len(memberships), 1)
        self.assertEqual(
            memberships[0]["id"],
            self.active_membership.id,
        )
        self.assertEqual(
            memberships[0]["status"],
            CompanyMembership.Status.ACTIVE,
        )

    def test_context_does_not_return_other_users_memberships(self):
        self.client.force_login(self.user)

        response = self.client.get(
            "/api/organizations/context/",
        )

        membership_ids = {
            membership["id"]
            for membership in response.json()["memberships"]
        }

        self.assertNotIn(
            self.other_membership.id,
            membership_ids,
        )

    def test_context_does_not_return_suspended_memberships(self):
        self.client.force_login(self.user)

        response = self.client.get(
            "/api/organizations/context/",
        )

        membership_ids = {
            membership["id"]
            for membership in response.json()["memberships"]
        }

        self.assertNotIn(
            self.suspended_membership.id,
            membership_ids,
        )

    def test_context_returns_company_and_membership_branches(self):
        self.client.force_login(self.user)

        response = self.client.get(
            "/api/organizations/context/",
        )

        membership = response.json()["memberships"][0]

        self.assertEqual(
            membership["company"],
            {
                "id": self.company_a.id,
                "name": "Empresa A",
            },
        )

        branch_ids = {
            branch["id"]
            for branch in membership["branches"]
        }

        self.assertEqual(
            branch_ids,
            {
                self.branch_a.id,
                self.branch_a_2.id,
            },
        )


class WarehouseDetailUpdateApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="warehouse-api-user",
            email="warehouse-api@example.com",
            password="test-password",
        )

        self.company_a = Company.objects.create(
            name="Empresa Warehouse A",
        )

        self.company_b = Company.objects.create(
            name="Empresa Warehouse B",
        )

        self.branch_a = Branch.objects.create(
            company=self.company_a,
            code="SUC-WH-A",
            name="Sucursal Warehouse A",
        )

        self.branch_b = Branch.objects.create(
            company=self.company_a,
            code="SUC-WH-B",
            name="Sucursal Warehouse B",
        )

        self.other_company_branch = Branch.objects.create(
            company=self.company_b,
            code="SUC-WH-C",
            name="Sucursal Warehouse C",
        )

        self.membership = CompanyMembership.objects.create(
            user=self.user,
            company=self.company_a,
            status=CompanyMembership.Status.ACTIVE,
        )

        MembershipBranch.objects.create(
            membership=self.membership,
            branch=self.branch_a,
        )

        self.permission = Permission.objects.get(
            code="organizations.warehouses.manage",
        )

        self.role = CompanyRole.objects.create(
            company=self.company_a,
            name="Administrador Bodegas",
            status=CompanyRole.Status.ACTIVE,
        )

        CompanyRolePermission.objects.create(
            role=self.role,
            permission=self.permission,
        )

        RoleAssignment.objects.create(
            membership=self.membership,
            role=self.role,
            branch=self.branch_a,
        )

        self.warehouse = Warehouse.objects.create(
            company=self.company_a,
            branch=self.branch_a,
            code="BOD-001",
            name="Bodega Principal",
        )


    def test_detail_returns_authorized_warehouse(self):
        self.client.force_login(self.user)

        response = self.client.get(
            f"/api/organizations/warehouses/{self.warehouse.id}/?company={self.company_a.id}",
        )

        self.assertEqual(response.status_code, 200)

        self.assertEqual(
            response.json()["warehouse"]["id"],
            self.warehouse.id,
        )


    def test_update_changes_warehouse_name(self):
        self.client.force_login(self.user)

        response = self.client.patch(
            f"/api/organizations/warehouses/{self.warehouse.id}/",
            {
                "company": self.company_a.id,
                "name": "Bodega Actualizada",
            },
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)

        self.warehouse.refresh_from_db()

        self.assertEqual(
            self.warehouse.name,
            "Bodega Actualizada",
        )
