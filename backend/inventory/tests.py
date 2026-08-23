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

from .models import InventoryStock


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
