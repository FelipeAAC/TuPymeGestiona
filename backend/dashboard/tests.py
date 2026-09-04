from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from catalog.models import Category, Product, ProductVariant
from customers.models import Customer
from inventory.models import InventoryMovement, InventoryStock
from orders.models import Order
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
from sales.models import Sale, SaleEvent


User = get_user_model()


class DashboardApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_user(
            username="dashboard-admin",
            email="dashboard-admin@example.com",
            password="test-password",
        )
        self.branch_user = User.objects.create_user(
            username="dashboard-branch",
            email="dashboard-branch@example.com",
            password="test-password",
        )
        self.other_user = User.objects.create_user(
            username="dashboard-other",
            email="dashboard-other@example.com",
            password="test-password",
        )

        self.company = Company.objects.create(name="Empresa Dashboard")
        self.other_company = Company.objects.create(name="Otra Empresa Dashboard")
        self.branch = Branch.objects.create(
            company=self.company,
            code="DASH-01",
            name="Casa Matriz",
        )
        self.branch_two = Branch.objects.create(
            company=self.company,
            code="DASH-02",
            name="Sucursal Norte",
        )
        self.other_branch = Branch.objects.create(
            company=self.other_company,
            code="OTHER-01",
            name="Sucursal Externa",
        )
        self.warehouse = Warehouse.objects.create(
            company=self.company,
            branch=self.branch,
            code="DASH-B01",
            name="Bodega Matriz",
        )
        self.warehouse_two = Warehouse.objects.create(
            company=self.company,
            branch=self.branch_two,
            code="DASH-B02",
            name="Bodega Norte",
        )

        self.category = Category.objects.create(
            company=self.company,
            name="Dashboard",
        )
        self.product = Product.objects.create(
            company=self.company,
            category=self.category,
            name="Producto Dashboard",
            status=Product.Status.ACTIVE,
        )
        self.variant = ProductVariant.objects.create(
            product=self.product,
            sku="DASH-SKU-01",
            base_price=Decimal("1000.00"),
            status=ProductVariant.Status.ACTIVE,
        )
        self.variant_two = ProductVariant.objects.create(
            product=self.product,
            sku="DASH-SKU-02",
            base_price=Decimal("2000.00"),
            status=ProductVariant.Status.ACTIVE,
        )
        InventoryStock.objects.create(
            warehouse=self.warehouse,
            variant=self.variant,
            quantity=Decimal("4.000"),
        )
        InventoryStock.objects.create(
            warehouse=self.warehouse_two,
            variant=self.variant_two,
            quantity=Decimal("0.000"),
        )
        InventoryMovement.objects.create(
            warehouse=self.warehouse,
            variant=self.variant,
            movement_type=InventoryMovement.MovementType.ENTRY,
            quantity_delta=Decimal("4.000"),
            created_by=self.admin,
        )
        InventoryMovement.objects.create(
            warehouse=self.warehouse_two,
            variant=self.variant_two,
            movement_type=InventoryMovement.MovementType.ENTRY,
            quantity_delta=Decimal("2.000"),
            created_by=self.admin,
        )

        self.customer = Customer.objects.create(
            company=self.company,
            code="DASH-C01",
            name="Cliente Dashboard",
        )

        self.pending_order = self._order(
            number=1,
            branch=self.branch,
            warehouse=self.warehouse,
            status=Order.Status.CONFIRMED,
        )
        self.pending_order_two = self._order(
            number=2,
            branch=self.branch_two,
            warehouse=self.warehouse_two,
            status=Order.Status.PREPARED,
        )
        sale_order = self._order(
            number=3,
            branch=self.branch,
            warehouse=self.warehouse,
            status=Order.Status.DELIVERED,
        )
        sale_order_two = self._order(
            number=4,
            branch=self.branch_two,
            warehouse=self.warehouse_two,
            status=Order.Status.DELIVERED,
        )
        self.sale = self._sale(
            order=sale_order,
            number=1,
            amount=Decimal("1000.00"),
        )
        self.sale_two = self._sale(
            order=sale_order_two,
            number=2,
            amount=Decimal("2000.00"),
        )
        SaleEvent.objects.create(
            sale=self.sale,
            event_type=SaleEvent.EventType.CREATED,
            previous_status="",
            new_status=Sale.Status.PAID,
            performed_by=self.admin,
        )
        SaleEvent.objects.create(
            sale=self.sale_two,
            event_type=SaleEvent.EventType.CREATED,
            previous_status="",
            new_status=Sale.Status.PAID,
            performed_by=self.admin,
        )

        self.admin_membership = CompanyMembership.objects.create(
            user=self.admin,
            company=self.company,
            status=CompanyMembership.Status.ACTIVE,
        )
        self.branch_membership = CompanyMembership.objects.create(
            user=self.branch_user,
            company=self.company,
            status=CompanyMembership.Status.ACTIVE,
        )
        MembershipBranch.objects.create(
            membership=self.branch_membership,
            branch=self.branch,
        )
        CompanyMembership.objects.create(
            user=self.other_user,
            company=self.other_company,
            status=CompanyMembership.Status.ACTIVE,
        )
        self._grant_admin_permission()
        self._grant_branch_permissions()

    def _order(self, *, number, branch, warehouse, status):
        return Order.objects.create(
            company=self.company,
            branch=branch,
            warehouse=warehouse,
            customer=self.customer,
            number=number,
            status=status,
            created_by=self.admin,
        )

    def _sale(self, *, order, number, amount):
        return Sale.objects.create(
            company=self.company,
            branch=order.branch,
            order=order,
            number=number,
            status=Sale.Status.PAID,
            total_amount=amount,
            paid_amount=amount,
            idempotency_key=f"dashboard-sale-{number}",
            created_by=self.admin,
        )

    def _grant_admin_permission(self):
        role = CompanyRole.objects.create(
            company=self.company,
            name="Administrador Dashboard",
            status=CompanyRole.Status.ACTIVE,
        )
        CompanyRolePermission.objects.create(
            role=role,
            permission=Permission.objects.get(code="administration.manage"),
        )
        RoleAssignment.objects.create(
            membership=self.admin_membership,
            role=role,
            branch=None,
        )

    def _grant_branch_permissions(self):
        role = CompanyRole.objects.create(
            company=self.company,
            name="Operador Dashboard",
            status=CompanyRole.Status.ACTIVE,
        )
        for code in ("sales.manage", "orders.manage", "inventory.stocks.manage"):
            CompanyRolePermission.objects.create(
                role=role,
                permission=Permission.objects.get(code=code),
            )
        RoleAssignment.objects.create(
            membership=self.branch_membership,
            role=role,
            branch=self.branch,
        )

    def test_requires_valid_company_parameter(self):
        self.client.force_login(self.admin)
        response = self.client.get("/api/dashboard/overview/")
        self.assertEqual(response.status_code, 400)

    def test_rejects_company_outside_membership(self):
        self.client.force_login(self.other_user)
        response = self.client.get(
            f"/api/dashboard/overview/?company={self.company.id}"
        )
        self.assertEqual(response.status_code, 403)

    def test_admin_receives_real_company_metrics(self):
        self.client.force_login(self.admin)
        response = self.client.get(
            f"/api/dashboard/overview/?company={self.company.id}"
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["metrics"]["sales_today_amount"], "3000.00")
        self.assertEqual(body["metrics"]["sales_today_count"], 2)
        self.assertEqual(body["metrics"]["pending_orders"], 2)
        self.assertEqual(body["metrics"]["low_stock"], 2)
        self.assertEqual(body["metrics"]["active_customers"], 1)
        self.assertTrue(body["activity"])
        self.assertTrue(body["permissions"]["administration"])

    def test_branch_user_only_receives_authorized_branch_metrics(self):
        self.client.force_login(self.branch_user)
        response = self.client.get(
            f"/api/dashboard/overview/?company={self.company.id}"
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["metrics"]["sales_today_amount"], "1000.00")
        self.assertEqual(body["metrics"]["sales_today_count"], 1)
        self.assertEqual(body["metrics"]["pending_orders"], 1)
        self.assertEqual(body["metrics"]["low_stock"], 1)
        self.assertIsNone(body["metrics"]["active_customers"])
        self.assertFalse(body["permissions"]["customers"])
        serialized = str(body["activity"])
        self.assertIn("Casa Matriz", serialized)
        self.assertNotIn("Sucursal Norte", serialized)

    def test_modules_reflect_real_permissions(self):
        self.client.force_login(self.branch_user)
        response = self.client.get(
            f"/api/dashboard/overview/?company={self.company.id}"
        )
        modules = {item["code"]: item for item in response.json()["modules"]}
        self.assertTrue(modules["sales"]["available"])
        self.assertTrue(modules["reports"]["available"])
        self.assertFalse(modules["administration"]["available"])
