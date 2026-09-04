from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from rest_framework.test import APIClient

from catalog.models import Category, Product, ProductVariant
from customers.models import Customer
from inventory.models import InventoryStock
from orders.models import Order, OrderItem
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
from sales.services import create_sale, record_payment


User = get_user_model()


class ReportsApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_user(
            username="report-admin",
            email="report-admin@example.com",
            password="test-password",
        )
        self.inventory_user = User.objects.create_user(
            username="report-inventory",
            email="report-inventory@example.com",
            password="test-password",
        )
        self.other_user = User.objects.create_user(
            username="report-other",
            email="report-other@example.com",
            password="test-password",
        )

        self.company = Company.objects.create(name="Empresa Reportes")
        self.other_company = Company.objects.create(name="Otra Empresa Reportes")
        self.branch = Branch.objects.create(
            company=self.company,
            code="REP-01",
            name="Casa Matriz",
        )
        self.branch_two = Branch.objects.create(
            company=self.company,
            code="REP-02",
            name="Sucursal Norte",
        )
        self.other_branch = Branch.objects.create(
            company=self.other_company,
            code="EXT-01",
            name="Sucursal Externa",
        )
        self.warehouse = Warehouse.objects.create(
            company=self.company,
            branch=self.branch,
            code="BOD-REP-01",
            name="Bodega Central",
        )
        self.warehouse_two = Warehouse.objects.create(
            company=self.company,
            branch=self.branch_two,
            code="BOD-REP-02",
            name="Bodega Norte",
        )
        self.other_warehouse = Warehouse.objects.create(
            company=self.other_company,
            branch=self.other_branch,
            code="BOD-EXT-01",
            name="Bodega Externa",
        )

        self.category = Category.objects.create(company=self.company, name="Bebidas")
        self.product = Product.objects.create(
            company=self.company,
            category=self.category,
            name="Producto Reporte",
            status=Product.Status.ACTIVE,
        )
        self.variant = ProductVariant.objects.create(
            product=self.product,
            sku="REP-SKU-01",
            base_price=Decimal("1500.00"),
            status=ProductVariant.Status.ACTIVE,
        )
        self.variant_two = ProductVariant.objects.create(
            product=self.product,
            sku="REP-SKU-02",
            base_price=Decimal("2000.00"),
            status=ProductVariant.Status.ACTIVE,
        )
        self.stock = InventoryStock.objects.create(
            warehouse=self.warehouse,
            variant=self.variant,
            quantity=Decimal("4.000"),
        )
        self.stock_two = InventoryStock.objects.create(
            warehouse=self.warehouse_two,
            variant=self.variant_two,
            quantity=Decimal("20.000"),
        )

        self.customer = Customer.objects.create(
            company=self.company,
            code="REP-CLI-01",
            name="Cliente Reporte",
        )
        self.admin_membership = CompanyMembership.objects.create(
            user=self.admin,
            company=self.company,
            status=CompanyMembership.Status.ACTIVE,
        )
        MembershipBranch.objects.create(membership=self.admin_membership, branch=self.branch)
        self.inventory_membership = CompanyMembership.objects.create(
            user=self.inventory_user,
            company=self.company,
            status=CompanyMembership.Status.ACTIVE,
        )
        MembershipBranch.objects.create(membership=self.inventory_membership, branch=self.branch)
        self.other_membership = CompanyMembership.objects.create(
            user=self.other_user,
            company=self.other_company,
            status=CompanyMembership.Status.ACTIVE,
        )

        admin_permission = Permission.objects.get(code="administration.manage")
        admin_role = CompanyRole.objects.create(
            company=self.company,
            name="Administrador",
            status=CompanyRole.Status.ACTIVE,
        )
        CompanyRolePermission.objects.create(role=admin_role, permission=admin_permission)
        RoleAssignment.objects.create(
            membership=self.admin_membership,
            role=admin_role,
            branch=None,
        )

        inventory_permission = Permission.objects.get(code="inventory.stocks.manage")
        inventory_role = CompanyRole.objects.create(
            company=self.company,
            name="Encargado Inventario",
            status=CompanyRole.Status.ACTIVE,
        )
        CompanyRolePermission.objects.create(role=inventory_role, permission=inventory_permission)
        RoleAssignment.objects.create(
            membership=self.inventory_membership,
            role=inventory_role,
            branch=self.branch,
        )

        self.sale = self._create_sale(number=1, branch=self.branch, warehouse=self.warehouse)
        record_payment(
            sale=self.sale,
            amount=Decimal("1000.00"),
            reference="REP-PAY-01",
            idempotency_key="rep-payment-01",
            performed_by=self.admin,
        )
        self.sale.refresh_from_db()
        self.sale_two = self._create_sale(number=2, branch=self.branch_two, warehouse=self.warehouse_two)

    def _create_sale(self, *, number, branch, warehouse):
        order = Order.objects.create(
            company=self.company,
            branch=branch,
            warehouse=warehouse,
            customer=self.customer,
            number=number,
            status=Order.Status.DELIVERED,
            created_by=self.admin,
        )
        OrderItem.objects.create(
            order=order,
            variant=self.variant,
            quantity=Decimal("2.000"),
            unit_price=Decimal("1500.00"),
        )
        sale, _ = create_sale(
            company=self.company,
            order=order,
            idempotency_key=f"rep-sale-{number}",
            created_by=self.admin,
        )
        return sale

    def test_options_admin_can_access_both_reports(self):
        self.client.force_login(self.admin)
        response = self.client.get(f"/api/reports/options/?company={self.company.id}")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["permissions"]["sales"])
        self.assertTrue(response.json()["permissions"]["inventory"])
        self.assertEqual(len(response.json()["branches"]), 2)
        self.assertEqual(len(response.json()["warehouses"]), 2)

    def test_sales_report_filters_branch_and_keeps_company_isolation(self):
        self.client.force_login(self.admin)
        response = self.client.get(
            f"/api/reports/sales/?company={self.company.id}&branch={self.branch.id}"
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["summary"]["records"], 1)
        self.assertEqual(body["rows"][0]["number"], self.sale.number)
        self.assertEqual(body["rows"][0]["branch"], self.branch.name)
        self.assertEqual(body["summary"]["gross_total"], "3000.00")
        self.assertEqual(body["summary"]["paid_total"], "1000.00")

    def test_inventory_only_user_cannot_generate_sales_report(self):
        self.client.force_login(self.inventory_user)
        response = self.client.get(f"/api/reports/sales/?company={self.company.id}")
        self.assertEqual(response.status_code, 403)

    def test_inventory_user_only_sees_authorized_branch_warehouse(self):
        self.client.force_login(self.inventory_user)
        response = self.client.get(f"/api/reports/inventory/?company={self.company.id}")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["summary"]["records"], 1)
        self.assertEqual(body["rows"][0]["warehouse"], self.warehouse.name)
        self.assertEqual(body["summary"]["reference_value"], "6000.00")

    def test_inventory_critical_filter_uses_explicit_threshold(self):
        self.client.force_login(self.admin)
        response = self.client.get(
            f"/api/reports/inventory/?company={self.company.id}&stock_level=CRITICAL&critical_threshold=5"
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["summary"]["records"], 1)
        self.assertEqual(body["rows"][0]["stock_level"], "CRITICAL")
        self.assertIn("precio base vigente", body["valuation_note"])

    def test_sales_pdf_and_xls_are_downloadable(self):
        self.client.force_login(self.admin)
        pdf_response = self.client.get(f"/api/reports/sales/export/pdf/?company={self.company.id}")
        self.assertEqual(pdf_response.status_code, 200)
        self.assertEqual(pdf_response["Content-Type"], "application/pdf")
        self.assertTrue(pdf_response.content.startswith(b"%PDF"))

        xls_response = self.client.get(f"/api/reports/sales/export/xls/?company={self.company.id}")
        self.assertEqual(xls_response.status_code, 200)
        self.assertIn("spreadsheetml", xls_response["Content-Type"])
        self.assertTrue(xls_response.content.startswith(b"PK"))

    def test_inventory_pdf_and_xls_are_downloadable(self):
        self.client.force_login(self.inventory_user)
        pdf_response = self.client.get(f"/api/reports/inventory/export/pdf/?company={self.company.id}")
        self.assertEqual(pdf_response.status_code, 200)
        self.assertTrue(pdf_response.content.startswith(b"%PDF"))
        xls_response = self.client.get(f"/api/reports/inventory/export/xls/?company={self.company.id}")
        self.assertEqual(xls_response.status_code, 200)
        self.assertTrue(xls_response.content.startswith(b"PK"))

    def test_inventory_rejects_warehouse_outside_authorized_scope(self):
        self.client.force_login(self.inventory_user)
        response = self.client.get(
            f"/api/reports/inventory/?company={self.company.id}&warehouse={self.warehouse_two.id}"
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("alcance autorizado", response.json()["detail"])

    def test_cross_company_membership_is_not_leaked(self):
        self.client.force_login(self.other_user)
        response = self.client.get(f"/api/reports/options/?company={self.company.id}")
        self.assertEqual(response.status_code, 403)
