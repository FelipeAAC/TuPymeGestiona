from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from rest_framework.test import APIClient

from catalog.models import Category, Product, ProductVariant
from customers.models import Customer
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

from .models import Order, OrderItem, OrderNumberSequence
from .services import (
    OrderNotEditableError,
    create_draft_order,
    update_draft_order,
)
from .views import ORDERS_MANAGE_PERMISSION_CODE


User = get_user_model()


class OrderFixtureMixin:
    def setUp(self):
        super().setUp()

        self.client = APIClient()
        self.user = User.objects.create_user(
            username="orders-user",
            email="orders@example.com",
            password="test-password",
        )

        self.company = Company.objects.create(
            name="Empresa Pedidos",
        )
        self.other_company = Company.objects.create(
            name="Otra Empresa Pedidos",
        )

        self.branch = Branch.objects.create(
            company=self.company,
            code="SUC-PED-01",
            name="Sucursal Pedidos",
        )
        self.other_branch = Branch.objects.create(
            company=self.company,
            code="SUC-PED-02",
            name="Otra Sucursal Pedidos",
        )
        self.foreign_branch = Branch.objects.create(
            company=self.other_company,
            code="SUC-PED-EXT",
            name="Sucursal Externa",
        )

        self.warehouse = Warehouse.objects.create(
            company=self.company,
            branch=self.branch,
            code="BOD-PED-01",
            name="Bodega Pedidos",
        )
        self.other_warehouse = Warehouse.objects.create(
            company=self.company,
            branch=self.other_branch,
            code="BOD-PED-02",
            name="Otra Bodega Pedidos",
        )
        self.company_warehouse = Warehouse.objects.create(
            company=self.company,
            code="BOD-PED-GLOBAL",
            name="Bodega de Empresa",
        )
        self.foreign_warehouse = Warehouse.objects.create(
            company=self.other_company,
            branch=self.foreign_branch,
            code="BOD-PED-EXT",
            name="Bodega Externa",
        )

        self.customer = Customer.objects.create(
            company=self.company,
            code="CLI-PED-01",
            name="Cliente Pedidos",
        )
        self.foreign_customer = Customer.objects.create(
            company=self.other_company,
            code="CLI-PED-EXT",
            name="Cliente Externo",
        )

        category = Category.objects.create(
            company=self.company,
            name="Categoria Pedidos",
        )
        product = Product.objects.create(
            company=self.company,
            category=category,
            name="Producto Pedidos",
            status=Product.Status.ACTIVE,
        )
        self.variant = ProductVariant.objects.create(
            product=product,
            sku="SKU-PED-01",
            base_price=Decimal("1250.00"),
            status=ProductVariant.Status.ACTIVE,
        )
        self.second_variant = ProductVariant.objects.create(
            product=product,
            sku="SKU-PED-02",
            base_price=Decimal("500.00"),
            status=ProductVariant.Status.ACTIVE,
        )

        foreign_category = Category.objects.create(
            company=self.other_company,
            name="Categoria Externa",
        )
        foreign_product = Product.objects.create(
            company=self.other_company,
            category=foreign_category,
            name="Producto Externo",
            status=Product.Status.ACTIVE,
        )
        self.foreign_variant = ProductVariant.objects.create(
            product=foreign_product,
            sku="SKU-PED-EXT",
            base_price=Decimal("800.00"),
            status=ProductVariant.Status.ACTIVE,
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
            code=ORDERS_MANAGE_PERMISSION_CODE,
        )
        self.role = CompanyRole.objects.create(
            company=self.company,
            name="Administrador Pedidos",
            status=CompanyRole.Status.ACTIVE,
        )
        CompanyRolePermission.objects.create(
            role=self.role,
            permission=self.permission,
        )
        self.assignment = RoleAssignment.objects.create(
            membership=self.membership,
            role=self.role,
            branch=self.branch,
        )

    def create_order(
        self,
        *,
        number=1,
        branch=None,
        warehouse=None,
        status=Order.Status.DRAFT,
        company=None,
        customer=None,
        variant=None,
    ):
        company = company or self.company
        branch = branch or self.branch
        warehouse = warehouse or self.warehouse
        customer = customer or self.customer
        variant = variant or self.variant

        order = Order.objects.create(
            company=company,
            branch=branch,
            warehouse=warehouse,
            customer=customer,
            number=number,
            status=status,
            created_by=self.user,
        )
        OrderItem.objects.create(
            order=order,
            variant=variant,
            quantity=Decimal("2.000"),
            unit_price=Decimal("1250.00"),
        )
        return order

    def valid_payload(self):
        return {
            "company": self.company.id,
            "branch": self.branch.id,
            "warehouse": self.warehouse.id,
            "customer": self.customer.id,
            "notes": "Pedido de prueba",
            "items": [
                {
                    "variant": self.variant.id,
                    "quantity": "2.000",
                    "unit_price": "1250.00",
                },
            ],
        }


class OrderModelTests(OrderFixtureMixin, TestCase):
    def test_orders_permission_is_branch_scoped(self):
        self.assertEqual(
            self.permission.scope_behavior,
            Permission.ScopeBehavior.BRANCH_SCOPED,
        )

    def test_order_number_is_unique_inside_company(self):
        self.create_order(number=10)

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self.create_order(number=10)

    def test_order_rejects_customer_from_another_company(self):
        order = Order(
            company=self.company,
            branch=self.branch,
            warehouse=self.warehouse,
            customer=self.foreign_customer,
            number=1,
            created_by=self.user,
        )

        with self.assertRaises(ValidationError):
            order.save()

    def test_order_rejects_warehouse_from_another_branch(self):
        order = Order(
            company=self.company,
            branch=self.branch,
            warehouse=self.other_warehouse,
            customer=self.customer,
            number=1,
            created_by=self.user,
        )

        with self.assertRaises(ValidationError):
            order.save()

    def test_order_item_rejects_variant_from_another_company(self):
        order = self.create_order()
        item = OrderItem(
            order=order,
            variant=self.foreign_variant,
            quantity=Decimal("1.000"),
            unit_price=Decimal("800.00"),
        )

        with self.assertRaises(ValidationError):
            item.save()

    def test_order_item_requires_positive_quantity(self):
        order = self.create_order()
        item = OrderItem(
            order=order,
            variant=self.second_variant,
            quantity=Decimal("0.000"),
            unit_price=Decimal("500.00"),
        )

        with self.assertRaises(ValidationError):
            item.save()


class OrderServiceTests(OrderFixtureMixin, TestCase):
    def test_create_draft_assigns_consecutive_numbers_per_company(self):
        first = create_draft_order(
            company=self.company,
            branch=self.branch,
            warehouse=self.warehouse,
            customer=self.customer,
            notes="Primero",
            items=[],
            created_by=self.user,
        )
        second = create_draft_order(
            company=self.company,
            branch=self.branch,
            warehouse=self.warehouse,
            customer=self.customer,
            notes="Segundo",
            items=[],
            created_by=self.user,
        )
        foreign = create_draft_order(
            company=self.other_company,
            branch=self.foreign_branch,
            warehouse=self.foreign_warehouse,
            customer=self.foreign_customer,
            notes="Otra empresa",
            items=[],
            created_by=self.user,
        )

        self.assertEqual((first.number, second.number), (1, 2))
        self.assertEqual(foreign.number, 1)
        self.assertEqual(first.status, Order.Status.DRAFT)
        self.assertEqual(
            OrderNumberSequence.objects.get(
                company=self.company,
            ).next_number,
            3,
        )

    def test_create_draft_rolls_back_number_when_item_is_invalid(self):
        with self.assertRaises(ValidationError):
            create_draft_order(
                company=self.company,
                branch=self.branch,
                warehouse=self.warehouse,
                customer=self.customer,
                notes="Invalido",
                items=[
                    {
                        "variant": self.foreign_variant,
                        "quantity": Decimal("1.000"),
                        "unit_price": Decimal("800.00"),
                    },
                ],
                created_by=self.user,
            )

        self.assertFalse(Order.objects.exists())
        self.assertFalse(OrderNumberSequence.objects.exists())

    def test_update_draft_replaces_items_atomically(self):
        order = self.create_order()

        updated = update_draft_order(
            order=order,
            validated_data={
                "notes": "Actualizado",
                "items": [
                    {
                        "variant": self.second_variant,
                        "quantity": Decimal("3.000"),
                        "unit_price": Decimal("500.00"),
                    },
                ],
            },
            replace_items=True,
        )

        self.assertEqual(updated.notes, "Actualizado")
        self.assertEqual(updated.items.count(), 1)
        self.assertEqual(
            updated.items.get().variant,
            self.second_variant,
        )
        self.assertEqual(updated.total, Decimal("1500.00000"))

    def test_update_rejects_non_draft_order(self):
        order = self.create_order(status=Order.Status.CONFIRMED)

        with self.assertRaises(OrderNotEditableError):
            update_draft_order(
                order=order,
                validated_data={"notes": "No permitido"},
                replace_items=False,
            )


class OrderApiTests(OrderFixtureMixin, TestCase):
    def test_orders_require_authentication(self):
        response = self.client.get(
            "/api/orders/",
            {"company": self.company.id},
        )

        self.assertEqual(response.status_code, 403)
    def test_options_only_return_authorized_tenant_data(self):
        self.client.force_login(self.user)

        response = self.client.get(
            "/api/orders/options/",
            {"company": self.company.id},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["permissions"], {"manage": True})
        self.assertEqual(
            {branch["id"] for branch in response.data["branches"]},
            {self.branch.id},
        )
        self.assertEqual(
            {warehouse["id"] for warehouse in response.data["warehouses"]},
            {self.warehouse.id, self.company_warehouse.id},
        )
        self.assertEqual(
            [customer["id"] for customer in response.data["customers"]],
            [self.customer.id],
        )
        self.assertNotIn(
            self.foreign_variant.id,
            [variant["id"] for variant in response.data["variants"]],
        )

    def test_options_without_permission_are_empty(self):
        self.assignment.delete()
        self.client.force_login(self.user)

        response = self.client.get(
            "/api/orders/options/",
            {"company": self.company.id},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["permissions"], {"manage": False})
        self.assertEqual(response.data["branches"], [])
        self.assertEqual(response.data["warehouses"], [])
        self.assertEqual(response.data["customers"], [])
        self.assertEqual(response.data["variants"], [])

    def test_create_draft_order_with_items(self):
        payload = self.valid_payload()
        payload["number"] = 999
        payload["status"] = Order.Status.DELIVERED
        self.client.force_login(self.user)

        response = self.client.post(
            "/api/orders/",
            payload,
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["order"]["number"], 1)
        self.assertEqual(
            response.data["order"]["status"],
            Order.Status.DRAFT,
        )
        self.assertEqual(response.data["order"]["total"], "2500.00")
        self.assertEqual(response.data["order"]["created_by"], self.user.id)
        self.assertEqual(OrderItem.objects.count(), 1)

    def test_create_denies_branch_outside_role_scope(self):
        payload = self.valid_payload()
        payload["branch"] = self.other_branch.id
        payload["warehouse"] = self.other_warehouse.id
        self.client.force_login(self.user)

        response = self.client.post(
            "/api/orders/",
            payload,
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 403)
        self.assertFalse(Order.objects.exists())

    def test_create_rejects_cross_tenant_relations(self):
        self.client.force_login(self.user)

        invalid_fields = {
            "customer": self.foreign_customer.id,
            "warehouse": self.foreign_warehouse.id,
        }

        for field, value in invalid_fields.items():
            with self.subTest(field=field):
                payload = self.valid_payload()
                payload[field] = value
                response = self.client.post(
                    "/api/orders/",
                    payload,
                    content_type="application/json",
                )
                self.assertEqual(response.status_code, 400)

        payload = self.valid_payload()
        payload["items"][0]["variant"] = self.foreign_variant.id
        response = self.client.post(
            "/api/orders/",
            payload,
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(Order.objects.exists())

    def test_create_rejects_duplicate_variants(self):
        payload = self.valid_payload()
        payload["items"].append(dict(payload["items"][0]))
        self.client.force_login(self.user)

        response = self.client.post(
            "/api/orders/",
            payload,
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(Order.objects.exists())

    def test_list_only_returns_orders_from_authorized_branch(self):
        allowed = self.create_order(number=1)
        self.create_order(
            number=2,
            branch=self.other_branch,
            warehouse=self.other_warehouse,
        )
        self.client.force_login(self.user)

        response = self.client.get(
            "/api/orders/",
            {
                "company": self.company.id,
                "status": Order.Status.DRAFT,
                "page_size": 10,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["pagination"]["count"], 1)
        self.assertEqual(
            [order["id"] for order in response.data["orders"]],
            [allowed.id],
        )

    def test_detail_does_not_expose_order_from_other_branch(self):
        hidden = self.create_order(
            number=2,
            branch=self.other_branch,
            warehouse=self.other_warehouse,
        )
        self.client.force_login(self.user)

        response = self.client.get(
            f"/api/orders/{hidden.id}/",
            {"company": self.company.id},
        )

        self.assertEqual(response.status_code, 404)

    def test_update_draft_replaces_items_and_preserves_identity(self):
        order = self.create_order(number=7)
        self.client.force_login(self.user)

        response = self.client.patch(
            f"/api/orders/{order.id}/",
            {
                "company": self.company.id,
                "number": 500,
                "status": Order.Status.CANCELLED,
                "notes": "Actualizado por API",
                "items": [
                    {
                        "variant": self.second_variant.id,
                        "quantity": "3.000",
                        "unit_price": "500.00",
                    },
                ],
            },
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["order"]["number"], 7)
        self.assertEqual(
            response.data["order"]["status"],
            Order.Status.DRAFT,
        )
        self.assertEqual(response.data["order"]["total"], "1500.00")
        order.refresh_from_db()
        self.assertEqual(order.notes, "Actualizado por API")
        self.assertEqual(order.items.get().variant, self.second_variant)

    def test_update_non_draft_returns_conflict(self):
        order = self.create_order(
            status=Order.Status.CONFIRMED,
        )
        self.client.force_login(self.user)

        response = self.client.patch(
            f"/api/orders/{order.id}/",
            {
                "company": self.company.id,
                "notes": "No permitido",
            },
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 409)
        order.refresh_from_db()
        self.assertEqual(order.notes, "")

    def test_update_cannot_move_order_outside_role_scope(self):
        order = self.create_order()
        self.client.force_login(self.user)

        response = self.client.patch(
            f"/api/orders/{order.id}/",
            {
                "company": self.company.id,
                "branch": self.other_branch.id,
                "warehouse": self.other_warehouse.id,
            },
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 403)
        order.refresh_from_db()
        self.assertEqual(order.branch, self.branch)

    def test_update_duplicate_items_preserves_existing_draft(self):
        order = self.create_order()
        self.client.force_login(self.user)
        item_payload = {
            "variant": self.second_variant.id,
            "quantity": "1.000",
            "unit_price": "500.00",
        }

        response = self.client.patch(
            f"/api/orders/{order.id}/",
            {
                "company": self.company.id,
                "notes": "No debe persistir",
                "items": [item_payload, dict(item_payload)],
            },
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        order.refresh_from_db()
        self.assertEqual(order.notes, "")
        self.assertEqual(order.items.get().variant, self.variant)

    def test_suspended_membership_does_not_authorize_orders(self):
        self.membership.status = CompanyMembership.Status.SUSPENDED
        self.membership.save(update_fields=("status",))
        self.client.force_login(self.user)

        response = self.client.post(
            "/api/orders/",
            self.valid_payload(),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 403)
