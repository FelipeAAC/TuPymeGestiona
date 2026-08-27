from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from catalog.models import (
    Category,
    Product,
    ProductVariant,
)

from organizations.models import (
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

from .models import (
    InventoryMovement,
    InventoryStock,
    InventoryTransfer,
    InventoryTransferItem,
)

from .services import (
    apply_inventory_movement,
    create_inventory_transfer,
)

User = get_user_model()


class InventoryModelsTests(TestCase):

    def setUp(self):
        self.company_a = Company.objects.create(
            name="Empresa Inventario A",
        )

        self.company_b = Company.objects.create(
            name="Empresa Inventario B",
        )

        self.branch_a = Branch.objects.create(
            company=self.company_a,
            code="SUC-001",
            name="Sucursal Principal",
        )

        self.branch_b = Branch.objects.create(
            company=self.company_a,
            code="SUC-002",
            name="Sucursal Secundaria",
        )

        self.warehouse_a = Warehouse.objects.create(
            company=self.company_a,
            branch=self.branch_a,
            code="BOD-001",
            name="Bodega Principal",
        )

        self.warehouse_b = Warehouse.objects.create(
            company=self.company_a,
            branch=self.branch_b,
            code="BOD-002",
            name="Bodega Secundaria",
        )

        self.warehouse_company_b = Warehouse.objects.create(
            company=self.company_b,
            code="BOD-003",
            name="Bodega Empresa B",
        )

        self.category_a = Category.objects.create(
            company=self.company_a,
            name="Categoria A",
        )

        self.category_b = Category.objects.create(
            company=self.company_b,
            name="Categoria B",
        )

        self.product_a = Product.objects.create(
            company=self.company_a,
            category=self.category_a,
            name="Producto A",
            status=Product.Status.ACTIVE,
        )

        self.product_b = Product.objects.create(
            company=self.company_b,
            category=self.category_b,
            name="Producto B",
            status=Product.Status.ACTIVE,
        )

        self.variant_a = ProductVariant.objects.create(
            product=self.product_a,
            sku="SKU-A",
            base_price=100,
            status=ProductVariant.Status.ACTIVE,
        )

        self.variant_b = ProductVariant.objects.create(
            product=self.product_b,
            sku="SKU-B",
            base_price=200,
            status=ProductVariant.Status.ACTIVE,
        )


    def test_inventory_stock_can_be_created(self):
        stock = InventoryStock(
            warehouse=self.warehouse_a,
            variant=self.variant_a,
            quantity=10,
        )

        stock.full_clean()
        stock.save()

        self.assertEqual(
            stock.quantity,
            10,
        )


    def test_inventory_stock_cannot_use_variant_from_another_company(self):
        stock = InventoryStock(
            warehouse=self.warehouse_a,
            variant=self.variant_b,
            quantity=10,
        )

        with self.assertRaises(ValidationError) as context:
            stock.full_clean()

        self.assertIn(
            "variant",
            context.exception.message_dict,
        )


    def test_inventory_stock_cannot_have_negative_quantity(self):
        stock = InventoryStock(
            warehouse=self.warehouse_a,
            variant=self.variant_a,
            quantity=-1,
        )

        with self.assertRaises(ValidationError) as context:
            stock.full_clean()

        self.assertIn(
            "quantity",
            context.exception.message_dict,
        )


    def test_same_variant_cannot_repeat_inside_same_warehouse(self):
        InventoryStock.objects.create(
            warehouse=self.warehouse_a,
            variant=self.variant_a,
            quantity=10,
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                InventoryStock.objects.create(
                    warehouse=self.warehouse_a,
                    variant=self.variant_a,
                    quantity=20,
                )


    def test_same_variant_can_exist_in_different_warehouses(self):
        stock_a = InventoryStock.objects.create(
            warehouse=self.warehouse_a,
            variant=self.variant_a,
            quantity=10,
        )

        stock_b = InventoryStock.objects.create(
            warehouse=self.warehouse_b,
            variant=self.variant_a,
            quantity=20,
        )

        self.assertNotEqual(
            stock_a.warehouse,
            stock_b.warehouse,
        )



class InventoryStockApiTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username="inventory-api-user",
            email="inventory-api@example.com",
            password="test-password",
        )

        self.company_a = Company.objects.create(
            name="Empresa Inventory A",
        )

        self.branch_a = Branch.objects.create(
            company=self.company_a,
            code="SUC-INV-A",
            name="Sucursal Inventory A",
        )

        self.branch_b = Branch.objects.create(
            company=self.company_a,
            code="SUC-INV-B",
            name="Sucursal Inventory B",
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
            code="inventory.stocks.manage",
        )

        self.role = CompanyRole.objects.create(
            company=self.company_a,
            name="Administrador Inventario",
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

        category = Category.objects.create(
            company=self.company_a,
            name="Categoria Inventario",
        )

        product = Product.objects.create(
            company=self.company_a,
            category=category,
            name="Producto Inventario",
            status=Product.Status.ACTIVE,
        )

        self.variant = ProductVariant.objects.create(
            product=product,
            sku="SKU-INV-001",
            base_price=100,
            status=ProductVariant.Status.ACTIVE,
        )

        self.warehouse = Warehouse.objects.create(
            company=self.company_a,
            branch=self.branch_a,
            code="BOD-INV-001",
            name="Bodega Inventario",
        )

        self.stock = InventoryStock.objects.create(
            warehouse=self.warehouse,
            variant=self.variant,
            quantity=50,
        )


    def test_list_returns_authorized_stock(self):
        self.client.force_login(self.user)

        response = self.client.get(
            f"/api/inventory/stocks/?company={self.company_a.id}",
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        stocks = response.json()["stocks"]

        self.assertEqual(
            len(stocks),
            1,
        )

        self.assertEqual(
            stocks[0]["id"],
            self.stock.id,
        )


    def test_create_stock_with_permission(self):

        warehouse = Warehouse.objects.create(
            company=self.company_a,
            branch=self.branch_a,
            code="BOD-INV-NEW",
            name="Bodega Nueva",
        )

        self.client.force_login(self.user)

        response = self.client.post(
            "/api/inventory/stocks/",
            {
                "company": self.company_a.id,
                "warehouse": warehouse.id,
                "variant": self.variant.id,
                "quantity": "25",
            },
            content_type="application/json",
        )

        self.assertEqual(
            response.status_code,
            201,
        )

        self.assertEqual(
            InventoryStock.objects.count(),
            2,
        )


    def test_create_stock_denies_other_branch(self):

        warehouse_other_branch = Warehouse.objects.create(
            company=self.company_a,
            branch=self.branch_b,
            code="BOD-INV-002",
            name="Bodega Otra Sucursal",
        )

        self.client.force_login(self.user)

        response = self.client.post(
            "/api/inventory/stocks/",
            {
                "company": self.company_a.id,
                "warehouse": warehouse_other_branch.id,
                "variant": self.variant.id,
                "quantity": "10",
            },
            content_type="application/json",
        )

        self.assertEqual(
            response.status_code,
            403,
        )


class InventoryMovementModelsTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username="inventory-movement-user",
            email="inventory-movement@example.com",
            password="test-password",
        )

        self.company_a = Company.objects.create(
            name="Empresa Movimiento A",
        )
        self.company_b = Company.objects.create(
            name="Empresa Movimiento B",
        )

        self.branch_a = Branch.objects.create(
            company=self.company_a,
            code="SUC-MOV-A",
            name="Sucursal Movimiento A",
        )

        self.warehouse_a = Warehouse.objects.create(
            company=self.company_a,
            branch=self.branch_a,
            code="BOD-MOV-A",
            name="Bodega Movimiento A",
        )

        self.warehouse_b = Warehouse.objects.create(
            company=self.company_b,
            code="BOD-MOV-B",
            name="Bodega Movimiento B",
        )

        self.category_a = Category.objects.create(
            company=self.company_a,
            name="Categoria Movimiento A",
        )
        self.category_b = Category.objects.create(
            company=self.company_b,
            name="Categoria Movimiento B",
        )

        self.product_a = Product.objects.create(
            company=self.company_a,
            category=self.category_a,
            name="Producto Movimiento A",
            status=Product.Status.ACTIVE,
        )
        self.product_b = Product.objects.create(
            company=self.company_b,
            category=self.category_b,
            name="Producto Movimiento B",
            status=Product.Status.ACTIVE,
        )

        self.variant_a = ProductVariant.objects.create(
            product=self.product_a,
            sku="SKU-MOV-A",
            base_price=100,
            status=ProductVariant.Status.ACTIVE,
        )
        self.variant_b = ProductVariant.objects.create(
            product=self.product_b,
            sku="SKU-MOV-B",
            base_price=200,
            status=ProductVariant.Status.ACTIVE,
        )

    def test_entry_movement_can_be_created(self):
        movement = InventoryMovement.objects.create(
            warehouse=self.warehouse_a,
            variant=self.variant_a,
            movement_type=InventoryMovement.MovementType.ENTRY,
            quantity_delta=10,
            created_by=self.user,
        )

        self.assertIsNotNone(
            movement.pk,
        )
        self.assertEqual(
            movement.movement_type,
            InventoryMovement.MovementType.ENTRY,
        )
        self.assertEqual(
            movement.quantity_delta,
            10,
        )
        self.assertEqual(
            movement.created_by,
            self.user,
        )

    def test_exit_movement_can_be_created(self):
        movement = InventoryMovement.objects.create(
            warehouse=self.warehouse_a,
            variant=self.variant_a,
            movement_type=InventoryMovement.MovementType.EXIT,
            quantity_delta=-5,
            created_by=self.user,
        )

        self.assertIsNotNone(
            movement.pk,
        )
        self.assertEqual(
            movement.quantity_delta,
            -5,
        )

    def test_adjustment_can_be_positive(self):
        movement = InventoryMovement.objects.create(
            warehouse=self.warehouse_a,
            variant=self.variant_a,
            movement_type=InventoryMovement.MovementType.ADJUSTMENT,
            quantity_delta=3,
            created_by=self.user,
        )

        self.assertEqual(
            movement.quantity_delta,
            3,
        )

    def test_adjustment_can_be_negative(self):
        movement = InventoryMovement.objects.create(
            warehouse=self.warehouse_a,
            variant=self.variant_a,
            movement_type=InventoryMovement.MovementType.ADJUSTMENT,
            quantity_delta=-2,
            created_by=self.user,
        )

        self.assertEqual(
            movement.quantity_delta,
            -2,
        )

    def test_movement_cannot_have_zero_quantity(self):
        movement = InventoryMovement(
            warehouse=self.warehouse_a,
            variant=self.variant_a,
            movement_type=InventoryMovement.MovementType.ADJUSTMENT,
            quantity_delta=0,
            created_by=self.user,
        )

        with self.assertRaises(ValidationError) as context:
            movement.full_clean()

        self.assertIn(
            "quantity_delta",
            context.exception.message_dict,
        )

    def test_entry_cannot_have_negative_quantity(self):
        movement = InventoryMovement(
            warehouse=self.warehouse_a,
            variant=self.variant_a,
            movement_type=InventoryMovement.MovementType.ENTRY,
            quantity_delta=-10,
            created_by=self.user,
        )

        with self.assertRaises(ValidationError) as context:
            movement.full_clean()

        self.assertIn(
            "quantity_delta",
            context.exception.message_dict,
        )

    def test_exit_cannot_have_positive_quantity(self):
        movement = InventoryMovement(
            warehouse=self.warehouse_a,
            variant=self.variant_a,
            movement_type=InventoryMovement.MovementType.EXIT,
            quantity_delta=10,
            created_by=self.user,
        )

        with self.assertRaises(ValidationError) as context:
            movement.full_clean()

        self.assertIn(
            "quantity_delta",
            context.exception.message_dict,
        )

    def test_movement_cannot_use_variant_from_another_company(self):
        movement = InventoryMovement(
            warehouse=self.warehouse_a,
            variant=self.variant_b,
            movement_type=InventoryMovement.MovementType.ENTRY,
            quantity_delta=10,
            created_by=self.user,
        )

        with self.assertRaises(ValidationError) as context:
            movement.full_clean()

        self.assertIn(
            "variant",
            context.exception.message_dict,
        )


class InventoryMovementPermissionSeedTests(TestCase):

    def test_inventory_movements_permission_is_branch_scoped(self):
        permission = Permission.objects.get(
            code="inventory.movements.manage",
        )

        self.assertEqual(
            permission.scope_behavior,
            "BRANCH_SCOPED",
        )


class InventoryMovementServiceTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username="inventory-service-user",
            email="inventory-service@example.com",
            password="test-password",
        )

        self.company = Company.objects.create(
            name="Empresa Inventory Service",
        )

        self.branch = Branch.objects.create(
            company=self.company,
            code="SUC-SERVICE",
            name="Sucursal Service",
        )

        self.warehouse = Warehouse.objects.create(
            company=self.company,
            branch=self.branch,
            code="BOD-SERVICE",
            name="Bodega Service",
        )

        self.category = Category.objects.create(
            company=self.company,
            name="Categoria Service",
        )

        self.product = Product.objects.create(
            company=self.company,
            category=self.category,
            name="Producto Service",
            status=Product.Status.ACTIVE,
        )

        self.variant = ProductVariant.objects.create(
            product=self.product,
            sku="SKU-SERVICE",
            base_price=100,
            status=ProductVariant.Status.ACTIVE,
        )

    def create_stock(self, quantity):
        return InventoryStock.objects.create(
            warehouse=self.warehouse,
            variant=self.variant,
            quantity=Decimal(quantity),
        )

    def test_entry_increases_existing_stock(self):
        stock = self.create_stock("10.000")

        movement, returned_stock = apply_inventory_movement(
            warehouse=self.warehouse,
            variant=self.variant,
            movement_type=InventoryMovement.MovementType.ENTRY,
            quantity_delta=Decimal("5.000"),
            created_by=self.user,
        )

        stock.refresh_from_db()

        self.assertEqual(
            stock.quantity,
            Decimal("15.000"),
        )
        self.assertEqual(
            returned_stock.pk,
            stock.pk,
        )
        self.assertEqual(
            movement.quantity_delta,
            Decimal("5.000"),
        )
        self.assertEqual(
            InventoryMovement.objects.count(),
            1,
        )

    def test_entry_creates_stock_when_it_does_not_exist(self):
        movement, stock = apply_inventory_movement(
            warehouse=self.warehouse,
            variant=self.variant,
            movement_type=InventoryMovement.MovementType.ENTRY,
            quantity_delta=Decimal("5.000"),
            created_by=self.user,
        )

        self.assertEqual(
            stock.quantity,
            Decimal("5.000"),
        )
        self.assertEqual(
            InventoryStock.objects.count(),
            1,
        )
        self.assertEqual(
            InventoryMovement.objects.count(),
            1,
        )
        self.assertEqual(
            movement.warehouse,
            self.warehouse,
        )

    def test_exit_decreases_existing_stock(self):
        stock = self.create_stock("10.000")

        apply_inventory_movement(
            warehouse=self.warehouse,
            variant=self.variant,
            movement_type=InventoryMovement.MovementType.EXIT,
            quantity_delta=Decimal("-4.000"),
            created_by=self.user,
        )

        stock.refresh_from_db()

        self.assertEqual(
            stock.quantity,
            Decimal("6.000"),
        )

    def test_positive_adjustment_increases_stock(self):
        stock = self.create_stock("10.000")

        apply_inventory_movement(
            warehouse=self.warehouse,
            variant=self.variant,
            movement_type=InventoryMovement.MovementType.ADJUSTMENT,
            quantity_delta=Decimal("2.000"),
            created_by=self.user,
        )

        stock.refresh_from_db()

        self.assertEqual(
            stock.quantity,
            Decimal("12.000"),
        )

    def test_negative_adjustment_decreases_stock(self):
        stock = self.create_stock("10.000")

        apply_inventory_movement(
            warehouse=self.warehouse,
            variant=self.variant,
            movement_type=InventoryMovement.MovementType.ADJUSTMENT,
            quantity_delta=Decimal("-3.000"),
            created_by=self.user,
        )

        stock.refresh_from_db()

        self.assertEqual(
            stock.quantity,
            Decimal("7.000"),
        )

    def test_movement_cannot_leave_negative_stock(self):
        stock = self.create_stock("3.000")

        with self.assertRaises(ValidationError):
            apply_inventory_movement(
                warehouse=self.warehouse,
                variant=self.variant,
                movement_type=InventoryMovement.MovementType.EXIT,
                quantity_delta=Decimal("-5.000"),
                created_by=self.user,
            )

        stock.refresh_from_db()

        self.assertEqual(
            stock.quantity,
            Decimal("3.000"),
        )
        self.assertEqual(
            InventoryMovement.objects.count(),
            0,
        )

    def test_negative_movement_without_stock_is_rejected(self):
        with self.assertRaises(ValidationError):
            apply_inventory_movement(
                warehouse=self.warehouse,
                variant=self.variant,
                movement_type=InventoryMovement.MovementType.EXIT,
                quantity_delta=Decimal("-1.000"),
                created_by=self.user,
            )

        self.assertFalse(
            InventoryStock.objects.filter(
                warehouse=self.warehouse,
                variant=self.variant,
            ).exists()
        )
        self.assertEqual(
            InventoryMovement.objects.count(),
            0,
        )

    def test_invalid_entry_does_not_modify_stock(self):
        stock = self.create_stock("10.000")

        with self.assertRaises(ValidationError):
            apply_inventory_movement(
                warehouse=self.warehouse,
                variant=self.variant,
                movement_type=InventoryMovement.MovementType.ENTRY,
                quantity_delta=Decimal("-2.000"),
                created_by=self.user,
            )

        stock.refresh_from_db()

        self.assertEqual(
            stock.quantity,
            Decimal("10.000"),
        )
        self.assertEqual(
            InventoryMovement.objects.count(),
            0,
        )

    def test_transaction_rolls_back_stock_if_movement_save_fails(self):
        stock = self.create_stock("10.000")

        with patch(
            "inventory.services.InventoryMovement.save",
            side_effect=RuntimeError(
                "Error simulado al guardar movimiento."
            ),
        ):
            with self.assertRaises(RuntimeError):
                apply_inventory_movement(
                    warehouse=self.warehouse,
                    variant=self.variant,
                    movement_type=(
                        InventoryMovement.MovementType.ENTRY
                    ),
                    quantity_delta=Decimal("5.000"),
                    created_by=self.user,
                )

        stock.refresh_from_db()

        self.assertEqual(
            stock.quantity,
            Decimal("10.000"),
        )
        self.assertEqual(
            InventoryMovement.objects.count(),
            0,
        )


class InventoryMovementApiTests(TestCase):

    def setUp(self):

        self.user = User.objects.create_user(
            username="inventory-movement-api-user",
            email="inventory-movement-api@example.com",
            password="test-password",
        )

        self.company = Company.objects.create(
            name="Empresa Movement API",
        )

        self.branch = Branch.objects.create(
            company=self.company,
            code="SUC-MOV-API",
            name="Sucursal Movement API",
        )

        self.membership = CompanyMembership.objects.create(
            user=self.user,
            company=self.company,
            status=CompanyMembership.Status.ACTIVE,
        )

        MembershipBranch.objects.create(
            membership=self.membership,
            branch=self.branch,
        )

        self.permission = Permission.objects.get(
            code="inventory.movements.manage",
        )

        self.role = CompanyRole.objects.create(
            company=self.company,
            name="Administrador Movimientos",
            status=CompanyRole.Status.ACTIVE,
        )

        CompanyRolePermission.objects.create(
            role=self.role,
            permission=self.permission,
        )

        RoleAssignment.objects.create(
            membership=self.membership,
            role=self.role,
            branch=self.branch,
        )

        category = Category.objects.create(
            company=self.company,
            name="Categoria Movement API",
        )

        product = Product.objects.create(
            company=self.company,
            category=category,
            name="Producto Movement API",
            status=Product.Status.ACTIVE,
        )

        self.variant = ProductVariant.objects.create(
            product=product,
            sku="SKU-MOV-API",
            base_price=100,
            status=ProductVariant.Status.ACTIVE,
        )

        self.warehouse = Warehouse.objects.create(
            company=self.company,
            branch=self.branch,
            code="BOD-MOV-API",
            name="Bodega Movement API",
        )


    def test_create_entry_movement_updates_stock(self):

        self.client.force_login(self.user)

        response = self.client.post(
            "/api/inventory/movements/",
            {
                "company": self.company.id,
                "warehouse": self.warehouse.id,
                "variant": self.variant.id,
                "movement_type": (
                    InventoryMovement.MovementType.ENTRY
                ),
                "quantity_delta": "25.000",
            },
            content_type="application/json",
        )

        self.assertEqual(
            response.status_code,
            201,
        )

        self.assertEqual(
            InventoryMovement.objects.count(),
            1,
        )

        stock = InventoryStock.objects.get(
            warehouse=self.warehouse,
            variant=self.variant,
        )

        self.assertEqual(
            stock.quantity,
            Decimal("25.000"),
        )


    def test_list_returns_authorized_movements(self):

        apply_inventory_movement(
            warehouse=self.warehouse,
            variant=self.variant,
            movement_type=(
                InventoryMovement.MovementType.ENTRY
            ),
            quantity_delta=Decimal("10.000"),
            created_by=self.user,
        )

        self.client.force_login(self.user)

        response = self.client.get(
            f"/api/inventory/movements/?company={self.company.id}",
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        movements = response.json()["movements"]

        self.assertEqual(
            len(movements),
            1,
        )

    def test_create_movement_denies_other_branch(self):

        other_branch = Branch.objects.create(
            company=self.company,
            code="SUC-MOV-OTHER",
            name="Sucursal Otra",
        )

        other_warehouse = Warehouse.objects.create(
            company=self.company,
            branch=other_branch,
            code="BOD-MOV-OTHER",
            name="Bodega Otra",
        )

        self.client.force_login(self.user)

        response = self.client.post(
            "/api/inventory/movements/",
            {
                "company": self.company.id,
                "warehouse": other_warehouse.id,
                "variant": self.variant.id,
                "movement_type": (
                    InventoryMovement.MovementType.ENTRY
                ),
                "quantity_delta": "10.000",
            },
            content_type="application/json",
        )

        self.assertEqual(
            response.status_code,
            403,
        )

    def test_create_movement_denies_variant_from_other_company(self):

        company_b = Company.objects.create(
            name="Empresa B Movement API",
        )

        category_b = Category.objects.create(
            company=company_b,
            name="Categoria B",
        )

        product_b = Product.objects.create(
            company=company_b,
            category=category_b,
            name="Producto B",
            status=Product.Status.ACTIVE,
        )

        variant_b = ProductVariant.objects.create(
            product=product_b,
            sku="SKU-MOV-B",
            base_price=100,
            status=ProductVariant.Status.ACTIVE,
        )

        self.client.force_login(self.user)

        response = self.client.post(
            "/api/inventory/movements/",
            {
                "company": self.company.id,
                "warehouse": self.warehouse.id,
                "variant": variant_b.id,
                "movement_type": (
                    InventoryMovement.MovementType.ENTRY
                ),
                "quantity_delta": "10.000",
            },
            content_type="application/json",
        )

        self.assertEqual(
            response.status_code,
            400,
        )

    def test_create_movement_without_permission_is_denied(self):

        RoleAssignment.objects.all().delete()

        self.client.force_login(self.user)

        response = self.client.post(
            "/api/inventory/movements/",
            {
                "company": self.company.id,
                "warehouse": self.warehouse.id,
                "variant": self.variant.id,
                "movement_type": (
                    InventoryMovement.MovementType.ENTRY
                ),
                "quantity_delta": "10.000",
            },
            content_type="application/json",
        )

        self.assertEqual(
            response.status_code,
            403,
        )


    def test_exit_without_stock_is_rejected(self):

        self.client.force_login(self.user)

        response = self.client.post(
            "/api/inventory/movements/",
            {
                "company": self.company.id,
                "warehouse": self.warehouse.id,
                "variant": self.variant.id,
                "movement_type": (
                    InventoryMovement.MovementType.EXIT
                ),
                "quantity_delta": "-5.000",
            },
            content_type="application/json",
        )

        self.assertEqual(
            response.status_code,
            400,
        )

        self.assertEqual(
            InventoryMovement.objects.count(),
            0,
        )

        self.assertFalse(
            InventoryStock.objects.filter(
                warehouse=self.warehouse,
                variant=self.variant,
            ).exists()
        )

    def test_list_movements_filters_by_type(self):

        InventoryMovement.objects.create(
            warehouse=self.warehouse,
            variant=self.variant,
            movement_type=InventoryMovement.MovementType.ENTRY,
            quantity_delta=10,
            created_by=self.user,
        )

        InventoryMovement.objects.create(
            warehouse=self.warehouse,
            variant=self.variant,
            movement_type=InventoryMovement.MovementType.EXIT,
            quantity_delta=-3,
            created_by=self.user,
        )

        self.client.force_login(self.user)

        response = self.client.get(
            (
                "/api/inventory/movements/"
                f"?company={self.company.id}"
                "&movement_type=ENTRY"
            ),
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        movements = response.json()["movements"]

        self.assertEqual(
            len(movements),
            1,
        )

        self.assertEqual(
            movements[0]["movement_type"],
            InventoryMovement.MovementType.ENTRY,
        )


class InventoryTransferModelsTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username="inventory-transfer-user",
            email="inventory-transfer@example.com",
            password="test-password",
        )

        self.company = Company.objects.create(
            name="Empresa Transfer",
        )

        self.branch_a = Branch.objects.create(
            company=self.company,
            code="SUC-TRANSFER-A",
            name="Sucursal Transfer A",
        )

        self.branch_b = Branch.objects.create(
            company=self.company,
            code="SUC-TRANSFER-B",
            name="Sucursal Transfer B",
        )

        self.warehouse_a = Warehouse.objects.create(
            company=self.company,
            branch=self.branch_a,
            code="BOD-TRANSFER-A",
            name="Bodega Origen",
        )

        self.warehouse_b = Warehouse.objects.create(
            company=self.company,
            branch=self.branch_b,
            code="BOD-TRANSFER-B",
            name="Bodega Destino",
        )

        category = Category.objects.create(
            company=self.company,
            name="Categoria Transfer",
        )

        product = Product.objects.create(
            company=self.company,
            category=category,
            name="Producto Transfer",
            status=Product.Status.ACTIVE,
        )

        self.variant = ProductVariant.objects.create(
            product=product,
            sku="SKU-TRANSFER",
            base_price=100,
            status=ProductVariant.Status.ACTIVE,
        )


    def test_inventory_transfer_can_be_created(self):

        transfer = InventoryTransfer.objects.create(
            company=self.company,
            source_warehouse=self.warehouse_a,
            destination_warehouse=self.warehouse_b,
            created_by=self.user,
        )

        self.assertIsNotNone(
            transfer.pk,
        )

        self.assertEqual(
            transfer.status,
            InventoryTransfer.Status.COMPLETED,
        )


    def test_transfer_cannot_use_same_warehouse(self):

        transfer = InventoryTransfer(
            company=self.company,
            source_warehouse=self.warehouse_a,
            destination_warehouse=self.warehouse_a,
            created_by=self.user,
        )

        with self.assertRaises(ValidationError):
            transfer.full_clean()


    def test_transfer_item_requires_positive_quantity(self):

        transfer = InventoryTransfer.objects.create(
            company=self.company,
            source_warehouse=self.warehouse_a,
            destination_warehouse=self.warehouse_b,
            created_by=self.user,
        )

        item = InventoryTransferItem(
            transfer=transfer,
            variant=self.variant,
            quantity=0,
        )

        with self.assertRaises(ValidationError):
            item.full_clean()


class InventoryTransferServiceTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username="transfer-service-user",
            email="transfer-service@example.com",
            password="test-password",
        )

        self.company = Company.objects.create(
            name="Empresa Transfer Service",
        )

        self.branch_a = Branch.objects.create(
            company=self.company,
            code="SUC-TRANS-A",
            name="Sucursal Origen",
        )

        self.branch_b = Branch.objects.create(
            company=self.company,
            code="SUC-TRANS-B",
            name="Sucursal Destino",
        )

        self.source = Warehouse.objects.create(
            company=self.company,
            branch=self.branch_a,
            code="BOD-TRANS-A",
            name="Bodega Origen",
        )

        self.destination = Warehouse.objects.create(
            company=self.company,
            branch=self.branch_b,
            code="BOD-TRANS-B",
            name="Bodega Destino",
        )

        category = Category.objects.create(
            company=self.company,
            name="Categoria Transfer Service",
        )

        product = Product.objects.create(
            company=self.company,
            category=category,
            name="Producto Transfer Service",
            status=Product.Status.ACTIVE,
        )

        self.variant = ProductVariant.objects.create(
            product=product,
            sku="SKU-TRANS-SERVICE",
            base_price=100,
            status=ProductVariant.Status.ACTIVE,
        )


    def test_transfer_moves_stock_between_warehouses(self):

        InventoryStock.objects.create(
            warehouse=self.source,
            variant=self.variant,
            quantity=Decimal("100.000"),
        )

        transfer = create_inventory_transfer(
            company=self.company,
            source_warehouse=self.source,
            destination_warehouse=self.destination,
            items=[
                {
                    "variant": self.variant,
                    "quantity": Decimal("20.000"),
                }
            ],
            created_by=self.user,
        )

        self.assertIsNotNone(
            transfer.pk,
        )

        source_stock = InventoryStock.objects.get(
            warehouse=self.source,
            variant=self.variant,
        )

        destination_stock = InventoryStock.objects.get(
            warehouse=self.destination,
            variant=self.variant,
        )

        self.assertEqual(
            source_stock.quantity,
            Decimal("80.000"),
        )

        self.assertEqual(
            destination_stock.quantity,
            Decimal("20.000"),
        )

        self.assertEqual(
            InventoryMovement.objects.count(),
            2,
        )


    def test_transfer_without_stock_rolls_back(self):

        with self.assertRaises(ValidationError):

            create_inventory_transfer(
                company=self.company,
                source_warehouse=self.source,
                destination_warehouse=self.destination,
                items=[
                    {
                        "variant": self.variant,
                        "quantity": Decimal("20.000"),
                    }
                ],
                created_by=self.user,
            )

        self.assertFalse(
            InventoryTransfer.objects.exists()
        )

        self.assertEqual(
            InventoryMovement.objects.count(),
            0,
        )

    def test_transfer_rolls_back_if_destination_entry_fails(self):

        InventoryStock.objects.create(
            warehouse=self.source,
            variant=self.variant,
            quantity=Decimal("100.000"),
        )

        with patch(
            "inventory.services.apply_inventory_movement",
            side_effect=RuntimeError(
                "Fallo simulado en entrada destino"
            ),
        ):

            with self.assertRaises(RuntimeError):

                create_inventory_transfer(
                    company=self.company,
                    source_warehouse=self.source,
                    destination_warehouse=self.destination,
                    items=[
                        {
                            "variant": self.variant,
                            "quantity": Decimal("20.000"),
                        }
                    ],
                    created_by=self.user,
                )

        self.assertFalse(
            InventoryTransfer.objects.exists()
        )

        self.assertEqual(
            InventoryMovement.objects.count(),
            0,
        )

        stock = InventoryStock.objects.get(
            warehouse=self.source,
            variant=self.variant,
        )

        self.assertEqual(
            stock.quantity,
            Decimal("100.000"),
        )


class InventoryTransferApiTests(TestCase):

    def setUp(self):

        self.user = User.objects.create_user(
            username="inventory-transfer-api-user",
            email="inventory-transfer-api@example.com",
            password="test-password",
        )

        self.company = Company.objects.create(
            name="Empresa Transfer API",
        )

        self.branch_a = Branch.objects.create(
            company=self.company,
            code="SUC-TRANS-API-A",
            name="Sucursal Transfer Origen",
        )

        self.branch_b = Branch.objects.create(
            company=self.company,
            code="SUC-TRANS-API-B",
            name="Sucursal Transfer Destino",
        )


        self.membership = CompanyMembership.objects.create(
            user=self.user,
            company=self.company,
            status=CompanyMembership.Status.ACTIVE,
        )


        MembershipBranch.objects.create(
            membership=self.membership,
            branch=self.branch_a,
        )


        MembershipBranch.objects.create(
            membership=self.membership,
            branch=self.branch_b,
        )


        self.permission = Permission.objects.get(
            code="inventory.transfers.manage",
        )


        self.role = CompanyRole.objects.create(
            company=self.company,
            name="Administrador Transferencias",
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


        RoleAssignment.objects.create(
            membership=self.membership,
            role=self.role,
            branch=self.branch_b,
        )


        category = Category.objects.create(
            company=self.company,
            name="Categoria Transfer API",
        )


        product = Product.objects.create(
            company=self.company,
            category=category,
            name="Producto Transfer API",
            status=Product.Status.ACTIVE,
        )


        self.variant = ProductVariant.objects.create(
            product=product,
            sku="SKU-TRANSFER-API",
            base_price=100,
            status=ProductVariant.Status.ACTIVE,
        )


        self.source = Warehouse.objects.create(
            company=self.company,
            branch=self.branch_a,
            code="BOD-TRANS-API-A",
            name="Bodega Origen API",
        )


        self.destination = Warehouse.objects.create(
            company=self.company,
            branch=self.branch_b,
            code="BOD-TRANS-API-B",
            name="Bodega Destino API",
        )



    def test_create_transfer_updates_stock(self):

        self.client.force_login(
            self.user,
        )


        InventoryStock.objects.create(
            warehouse=self.source,
            variant=self.variant,
            quantity=Decimal("100.000"),
        )


        response = self.client.post(
            "/api/inventory/transfers/",
            {
                "company": self.company.id,
                "source_warehouse": self.source.id,
                "destination_warehouse": self.destination.id,
                "items": [
                    {
                        "variant": self.variant.id,
                        "quantity": "25.000",
                    }
                ],
            },
            content_type="application/json",
        )


        self.assertEqual(
            response.status_code,
            201,
        )


        source_stock = InventoryStock.objects.get(
            warehouse=self.source,
            variant=self.variant,
        )


        destination_stock = InventoryStock.objects.get(
            warehouse=self.destination,
            variant=self.variant,
        )


        self.assertEqual(
            source_stock.quantity,
            Decimal("75.000"),
        )


        self.assertEqual(
            destination_stock.quantity,
            Decimal("25.000"),
        )


        self.assertEqual(
            InventoryMovement.objects.count(),
            2,
        )



    def test_create_transfer_without_permission_returns_403(self):

        RoleAssignment.objects.all().delete()


        self.client.force_login(
            self.user,
        )


        response = self.client.post(
            "/api/inventory/transfers/",
            {
                "company": self.company.id,
                "source_warehouse": self.source.id,
                "destination_warehouse": self.destination.id,
                "items": [
                    {
                        "variant": self.variant.id,
                        "quantity": "10.000",
                    }
                ],
            },
            content_type="application/json",
        )


        self.assertEqual(
            response.status_code,
            403,
        )


    def test_list_transfers_returns_authorized_transfers(self):

        self.client.force_login(
            self.user,
        )

        transfer = InventoryTransfer.objects.create(
            company=self.company,
            source_warehouse=self.source,
            destination_warehouse=self.destination,
            created_by=self.user,
        )

        InventoryTransferItem.objects.create(
            transfer=transfer,
            variant=self.variant,
            quantity=Decimal("20.000"),
        )

        response = self.client.get(
            "/api/inventory/transfers/",
            {
                "company": self.company.id,
            },
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.assertEqual(
            len(response.data["transfers"]),
            1,
        )

        self.assertEqual(
            response.data["transfers"][0]["id"],
            transfer.id,
        )

        self.assertEqual(
            len(
                response.data["transfers"][0]["items"]
            ),
            1,
        )


    def test_list_transfers_without_permission_returns_empty_list(self):

        RoleAssignment.objects.all().delete()

        self.client.force_login(
            self.user,
        )

        InventoryTransfer.objects.create(
            company=self.company,
            source_warehouse=self.source,
            destination_warehouse=self.destination,
            created_by=self.user,
        )

        response = self.client.get(
            "/api/inventory/transfers/",
            {
                "company": self.company.id,
            },
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.assertEqual(
            response.data["transfers"],
            [],
        )


    def test_list_transfers_by_destination_branch_permission(self):

        RoleAssignment.objects.filter(
            branch=self.branch_a,
        ).delete()

        self.client.force_login(
            self.user,
        )

        transfer = InventoryTransfer.objects.create(
            company=self.company,
            source_warehouse=self.source,
            destination_warehouse=self.destination,
            created_by=self.user,
        )

        response = self.client.get(
            "/api/inventory/transfers/",
            {
                "company": self.company.id,
            },
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.assertEqual(
            len(response.data["transfers"]),
            1,
        )

        self.assertEqual(
            response.data["transfers"][0]["id"],
            transfer.id,
        )
