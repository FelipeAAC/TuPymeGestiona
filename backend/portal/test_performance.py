from decimal import Decimal

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from catalog.models import Category, Product, ProductVariant
from inventory.models import InventoryStock
from organizations.models import Branch, Company, Warehouse
from portal.services import select_warehouse_with_stock


class PortalQueryEfficiencyTests(TestCase):
    def test_store_list_prefetches_branches_without_n_plus_one(self):
        for company_index in range(6):
            company = Company.objects.create(name=f"Tienda {company_index}", is_active=True)
            for branch_index in range(3):
                Branch.objects.create(
                    company=company,
                    code=f"B{branch_index}",
                    name=f"Sucursal {branch_index}",
                    is_active=True,
                )

        with CaptureQueriesContext(connection) as queries:
            response = self.client.get("/api/portal/stores/")

        self.assertEqual(response.status_code, 200)
        self.assertLessEqual(len(queries), 4)
        self.assertEqual(len(response.json()["stores"]), 6)

    def test_catalog_prefetches_stock_availability_without_per_variant_queries(self):
        company = Company.objects.create(name="Tienda Catálogo", is_active=True)
        branch = Branch.objects.create(company=company, code="CASA", name="Casa", is_active=True)
        warehouse = Warehouse.objects.create(company=company, branch=branch, code="WEB", name="Web")
        category = Category.objects.create(company=company, name="General")

        for product_index in range(8):
            product = Product.objects.create(
                company=company,
                category=category,
                name=f"Producto {product_index}",
                status=Product.Status.ACTIVE,
            )
            for variant_index in range(2):
                variant = ProductVariant.objects.create(
                    product=product,
                    sku=f"SKU-{product_index}-{variant_index}",
                    base_price=Decimal("1000.00"),
                    status=ProductVariant.Status.ACTIVE,
                )
                InventoryStock.objects.create(
                    warehouse=warehouse,
                    variant=variant,
                    quantity=Decimal("10.000"),
                )

        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(f"/api/portal/stores/{company.id}/catalog/")

        self.assertEqual(response.status_code, 200)
        self.assertLessEqual(len(queries), 8)
        self.assertEqual(len(response.json()["products"]), 8)

    def test_warehouse_stock_selection_uses_fixed_query_count(self):
        company = Company.objects.create(name="Tienda Stock", is_active=True)
        branch = Branch.objects.create(company=company, code="CASA", name="Casa", is_active=True)
        category = Category.objects.create(company=company, name="General")
        product = Product.objects.create(
            company=company,
            category=category,
            name="Producto",
            status=Product.Status.ACTIVE,
        )
        variant = ProductVariant.objects.create(
            product=product,
            sku="STOCK-1",
            base_price=Decimal("5000.00"),
            status=ProductVariant.Status.ACTIVE,
        )
        warehouses = [
            Warehouse.objects.create(
                company=company,
                branch=branch,
                code=f"B-{index}",
                name=f"Bodega {index}",
            )
            for index in range(5)
        ]
        for index, warehouse in enumerate(warehouses):
            InventoryStock.objects.create(
                warehouse=warehouse,
                variant=variant,
                quantity=Decimal("1.000") if index < 4 else Decimal("10.000"),
            )

        with self.assertNumQueries(2):
            selected = select_warehouse_with_stock(
                company=company,
                branch=branch,
                items=[{"variant": variant, "quantity": Decimal("5.000")}],
            )

        self.assertEqual(selected, warehouses[-1])
