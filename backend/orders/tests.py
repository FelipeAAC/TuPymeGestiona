from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from rest_framework.test import APIClient

from catalog.models import Category, Product, ProductVariant
from customers.models import Customer
from inventory.models import InventoryMovement, InventoryStock
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
    Order,
    OrderInventoryMovement,
    OrderItem,
    OrderNumberSequence,
)
from .services import (
    OrderNotEditableError,
    OrderTransitionError,
    cancel_order,
    confirm_order,
    create_draft_order,
    deliver_order,
    prepare_order,
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

    def create_stock(
        self,
        *,
        quantity=Decimal("10.000"),
        variant=None,
        warehouse=None,
    ):
        return InventoryStock.objects.create(
            warehouse=warehouse or self.warehouse,
            variant=variant or self.variant,
            quantity=quantity,
        )


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


class OrderInventoryServiceTests(OrderFixtureMixin, TestCase):
    def test_confirm_order_deducts_stock_and_records_trace(self):
        stock = self.create_stock()
        order = self.create_order()

        confirmed = confirm_order(
            order=order,
            performed_by=self.user,
        )

        stock.refresh_from_db()
        self.assertEqual(confirmed.status, Order.Status.CONFIRMED)
        self.assertEqual(stock.quantity, Decimal("8.000"))

        link = OrderInventoryMovement.objects.get()
        self.assertEqual(
            link.kind,
            OrderInventoryMovement.Kind.CONFIRMATION,
        )
        self.assertEqual(
            link.inventory_movement.movement_type,
            InventoryMovement.MovementType.EXIT,
        )
        self.assertEqual(
            link.inventory_movement.quantity_delta,
            Decimal("-2.000"),
        )

    def test_confirm_order_rolls_back_every_item_if_stock_is_insufficient(self):
        first_stock = self.create_stock(
            quantity=Decimal("10.000"),
        )
        second_stock = self.create_stock(
            quantity=Decimal("1.000"),
            variant=self.second_variant,
        )
        order = self.create_order()
        OrderItem.objects.create(
            order=order,
            variant=self.second_variant,
            quantity=Decimal("3.000"),
            unit_price=Decimal("500.00"),
        )

        with self.assertRaises(ValidationError):
            confirm_order(
                order=order,
                performed_by=self.user,
            )

        first_stock.refresh_from_db()
        second_stock.refresh_from_db()
        order.refresh_from_db()
        self.assertEqual(first_stock.quantity, Decimal("10.000"))
        self.assertEqual(second_stock.quantity, Decimal("1.000"))
        self.assertEqual(order.status, Order.Status.DRAFT)
        self.assertFalse(InventoryMovement.objects.exists())
        self.assertFalse(OrderInventoryMovement.objects.exists())

    def test_confirm_order_requires_at_least_one_item(self):
        order = Order.objects.create(
            company=self.company,
            branch=self.branch,
            warehouse=self.warehouse,
            customer=self.customer,
            number=1,
            created_by=self.user,
        )

        with self.assertRaises(ValidationError):
            confirm_order(
                order=order,
                performed_by=self.user,
            )

        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.DRAFT)

    def test_confirm_order_cannot_run_twice(self):
        self.create_stock()
        order = self.create_order()
        confirm_order(
            order=order,
            performed_by=self.user,
        )

        with self.assertRaises(OrderTransitionError):
            confirm_order(
                order=order,
                performed_by=self.user,
            )

        self.assertEqual(InventoryMovement.objects.count(), 1)

    def test_prepare_and_deliver_follow_the_operational_sequence(self):
        self.create_stock()
        order = self.create_order()
        order = confirm_order(
            order=order,
            performed_by=self.user,
        )

        prepared = prepare_order(
            order=order,
            performed_by=self.user,
        )
        delivered = deliver_order(
            order=prepared,
            performed_by=self.user,
        )

        self.assertEqual(prepared.status, Order.Status.PREPARED)
        self.assertEqual(delivered.status, Order.Status.DELIVERED)
        self.assertEqual(InventoryMovement.objects.count(), 1)

    def test_prepare_rejects_every_status_except_confirmed(self):
        for order_status in (
            Order.Status.DRAFT,
            Order.Status.PREPARED,
            Order.Status.DELIVERED,
            Order.Status.CANCELLED,
        ):
            with self.subTest(order_status=order_status):
                order = self.create_order(
                    number=10 + Order.objects.count(),
                    status=order_status,
                )

                with self.assertRaises(OrderTransitionError):
                    prepare_order(
                        order=order,
                        performed_by=self.user,
                    )

                order.refresh_from_db()
                self.assertEqual(order.status, order_status)

    def test_deliver_rejects_every_status_except_prepared(self):
        for order_status in (
            Order.Status.DRAFT,
            Order.Status.CONFIRMED,
            Order.Status.DELIVERED,
            Order.Status.CANCELLED,
        ):
            with self.subTest(order_status=order_status):
                order = self.create_order(
                    number=20 + Order.objects.count(),
                    status=order_status,
                )

                with self.assertRaises(OrderTransitionError):
                    deliver_order(
                        order=order,
                        performed_by=self.user,
                    )

                order.refresh_from_db()
                self.assertEqual(order.status, order_status)

    def test_cancel_confirmed_order_restores_exact_stock(self):
        stock = self.create_stock()
        order = self.create_order()
        order = confirm_order(
            order=order,
            performed_by=self.user,
        )

        cancelled = cancel_order(
            order=order,
            performed_by=self.user,
        )

        stock.refresh_from_db()
        self.assertEqual(cancelled.status, Order.Status.CANCELLED)
        self.assertEqual(stock.quantity, Decimal("10.000"))
        self.assertEqual(InventoryMovement.objects.count(), 2)
        self.assertEqual(OrderInventoryMovement.objects.count(), 2)
        cancellation = OrderInventoryMovement.objects.get(
            kind=OrderInventoryMovement.Kind.CANCELLATION,
        )
        self.assertEqual(
            cancellation.inventory_movement.quantity_delta,
            Decimal("2.000"),
        )

    def test_cancel_draft_does_not_move_stock(self):
        stock = self.create_stock()
        order = self.create_order()

        cancelled = cancel_order(
            order=order,
            performed_by=self.user,
        )

        stock.refresh_from_db()
        self.assertEqual(cancelled.status, Order.Status.CANCELLED)
        self.assertEqual(stock.quantity, Decimal("10.000"))
        self.assertFalse(InventoryMovement.objects.exists())

    def test_cancel_prepared_order_restores_exact_stock(self):
        stock = self.create_stock()
        order = self.create_order()
        order = confirm_order(
            order=order,
            performed_by=self.user,
        )
        order = prepare_order(
            order=order,
            performed_by=self.user,
        )

        cancelled = cancel_order(
            order=order,
            performed_by=self.user,
        )

        stock.refresh_from_db()
        self.assertEqual(cancelled.status, Order.Status.CANCELLED)
        self.assertEqual(stock.quantity, Decimal("10.000"))
        self.assertEqual(InventoryMovement.objects.count(), 2)
        self.assertEqual(OrderInventoryMovement.objects.count(), 2)

    def test_cancel_rejects_statuses_outside_supported_flow(self):
        for order_status in (
            Order.Status.DELIVERED,
            Order.Status.CANCELLED,
        ):
            with self.subTest(order_status=order_status):
                order = self.create_order(
                    number=10 + len(Order.objects.all()),
                    status=order_status,
                )

                with self.assertRaises(OrderTransitionError):
                    cancel_order(
                        order=order,
                        performed_by=self.user,
                    )

    def test_cancel_rejects_confirmed_order_without_complete_trace(self):
        order = self.create_order(
            status=Order.Status.CONFIRMED,
        )

        with self.assertRaises(ValidationError):
            cancel_order(
                order=order,
                performed_by=self.user,
            )

        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.CONFIRMED)


class OrderTransitionApiTests(OrderFixtureMixin, TestCase):
    def test_confirm_endpoint_requires_authentication(self):
        order = self.create_order()

        response = self.client.post(
            f"/api/orders/{order.id}/confirm/",
            {"company": self.company.id},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 403)

    def test_confirm_endpoint_deducts_stock(self):
        stock = self.create_stock()
        order = self.create_order()
        self.client.force_login(self.user)

        response = self.client.post(
            f"/api/orders/{order.id}/confirm/",
            {"company": self.company.id},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data["order"]["status"],
            Order.Status.CONFIRMED,
        )
        self.assertEqual(
            response.data["order"]["items"][0]["stock_movements"][0][
                "quantity_delta"
            ],
            "-2.000",
        )
        stock.refresh_from_db()
        self.assertEqual(stock.quantity, Decimal("8.000"))

    def test_confirm_endpoint_reports_insufficient_stock_without_changes(self):
        stock = self.create_stock(
            quantity=Decimal("1.000"),
        )
        order = self.create_order()
        self.client.force_login(self.user)

        response = self.client.post(
            f"/api/orders/{order.id}/confirm/",
            {"company": self.company.id},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        order.refresh_from_db()
        stock.refresh_from_db()
        self.assertEqual(order.status, Order.Status.DRAFT)
        self.assertEqual(stock.quantity, Decimal("1.000"))
        self.assertFalse(InventoryMovement.objects.exists())

    def test_confirm_endpoint_hides_order_outside_branch_scope(self):
        order = self.create_order(
            branch=self.other_branch,
            warehouse=self.other_warehouse,
        )
        self.client.force_login(self.user)

        response = self.client.post(
            f"/api/orders/{order.id}/confirm/",
            {"company": self.company.id},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 404)

    def test_confirm_endpoint_cannot_run_twice(self):
        self.create_stock()
        order = self.create_order()
        self.client.force_login(self.user)

        first = self.client.post(
            f"/api/orders/{order.id}/confirm/",
            {"company": self.company.id},
            content_type="application/json",
        )
        second = self.client.post(
            f"/api/orders/{order.id}/confirm/",
            {"company": self.company.id},
            content_type="application/json",
        )

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 409)
        self.assertEqual(InventoryMovement.objects.count(), 1)

    def test_prepare_and_deliver_endpoints_advance_confirmed_order(self):
        self.create_stock()
        order = self.create_order()
        order = confirm_order(
            order=order,
            performed_by=self.user,
        )
        self.client.force_login(self.user)

        prepared = self.client.post(
            f"/api/orders/{order.id}/prepare/",
            {"company": self.company.id},
            content_type="application/json",
        )
        delivered = self.client.post(
            f"/api/orders/{order.id}/deliver/",
            {"company": self.company.id},
            content_type="application/json",
        )

        self.assertEqual(prepared.status_code, 200)
        self.assertEqual(
            prepared.data["order"]["status"],
            Order.Status.PREPARED,
        )
        self.assertEqual(delivered.status_code, 200)
        self.assertEqual(
            delivered.data["order"]["status"],
            Order.Status.DELIVERED,
        )

    def test_prepare_endpoint_rejects_invalid_transition_without_changes(self):
        order = self.create_order()
        self.client.force_login(self.user)

        response = self.client.post(
            f"/api/orders/{order.id}/prepare/",
            {"company": self.company.id},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 409)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.DRAFT)

    def test_deliver_endpoint_retry_is_safe(self):
        self.create_stock()
        order = self.create_order()
        order = confirm_order(
            order=order,
            performed_by=self.user,
        )
        order = prepare_order(
            order=order,
            performed_by=self.user,
        )
        self.client.force_login(self.user)

        first = self.client.post(
            f"/api/orders/{order.id}/deliver/",
            {"company": self.company.id},
            content_type="application/json",
        )
        delivered_at = first.data["order"]["updated_at"]
        second = self.client.post(
            f"/api/orders/{order.id}/deliver/",
            {"company": self.company.id},
            content_type="application/json",
        )

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 409)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.DELIVERED)
        self.assertEqual(
            order.updated_at.isoformat().replace("+00:00", "Z"),
            delivered_at,
        )

    def test_prepare_endpoint_hides_cross_tenant_order(self):
        order = self.create_order(
            company=self.other_company,
            branch=self.foreign_branch,
            warehouse=self.foreign_warehouse,
            customer=self.foreign_customer,
            variant=self.foreign_variant,
            status=Order.Status.CONFIRMED,
        )
        self.client.force_login(self.user)

        response = self.client.post(
            f"/api/orders/{order.id}/prepare/",
            {"company": self.company.id},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 404)

    def test_operational_endpoints_hide_orders_outside_branch_scope(self):
        scenarios = (
            ("prepare", Order.Status.CONFIRMED),
            ("deliver", Order.Status.PREPARED),
        )
        self.client.force_login(self.user)

        for endpoint, order_status in scenarios:
            with self.subTest(endpoint=endpoint):
                order = self.create_order(
                    number=30 + Order.objects.count(),
                    branch=self.other_branch,
                    warehouse=self.other_warehouse,
                    status=order_status,
                )

                response = self.client.post(
                    f"/api/orders/{order.id}/{endpoint}/",
                    {"company": self.company.id},
                    content_type="application/json",
                )

                self.assertEqual(response.status_code, 404)

    def test_deliver_endpoint_rejects_company_without_membership(self):
        order = self.create_order(status=Order.Status.PREPARED)
        self.client.force_login(self.user)

        response = self.client.post(
            f"/api/orders/{order.id}/deliver/",
            {"company": self.other_company.id},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 403)

    def test_cancel_endpoint_restores_confirmed_stock(self):
        stock = self.create_stock()
        order = self.create_order()
        order = confirm_order(
            order=order,
            performed_by=self.user,
        )
        self.client.force_login(self.user)

        response = self.client.post(
            f"/api/orders/{order.id}/cancel/",
            {"company": self.company.id},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data["order"]["status"],
            Order.Status.CANCELLED,
        )
        movements = response.data["order"]["items"][0][
            "stock_movements"
        ]
        self.assertEqual(len(movements), 2)
        stock.refresh_from_db()
        self.assertEqual(stock.quantity, Decimal("10.000"))

    def test_cancel_endpoint_restores_prepared_stock(self):
        stock = self.create_stock()
        order = self.create_order()
        order = confirm_order(
            order=order,
            performed_by=self.user,
        )
        order = prepare_order(
            order=order,
            performed_by=self.user,
        )
        self.client.force_login(self.user)

        response = self.client.post(
            f"/api/orders/{order.id}/cancel/",
            {"company": self.company.id},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data["order"]["status"],
            Order.Status.CANCELLED,
        )
        stock.refresh_from_db()
        self.assertEqual(stock.quantity, Decimal("10.000"))

    def test_cancel_endpoint_rejects_delivered_without_restocking(self):
        stock = self.create_stock()
        order = self.create_order()
        order = confirm_order(
            order=order,
            performed_by=self.user,
        )
        order = prepare_order(
            order=order,
            performed_by=self.user,
        )
        order = deliver_order(
            order=order,
            performed_by=self.user,
        )
        self.client.force_login(self.user)

        response = self.client.post(
            f"/api/orders/{order.id}/cancel/",
            {"company": self.company.id},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 409)
        order.refresh_from_db()
        stock.refresh_from_db()
        self.assertEqual(order.status, Order.Status.DELIVERED)
        self.assertEqual(stock.quantity, Decimal("8.000"))
        self.assertEqual(InventoryMovement.objects.count(), 1)

    def test_cancel_endpoint_cancels_draft_without_inventory_effect(self):
        order = self.create_order()
        self.client.force_login(self.user)

        response = self.client.post(
            f"/api/orders/{order.id}/cancel/",
            {"company": self.company.id},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data["order"]["status"],
            Order.Status.CANCELLED,
        )
        self.assertFalse(InventoryMovement.objects.exists())

    def test_transition_endpoint_requires_company(self):
        order = self.create_order()
        self.client.force_login(self.user)

        response = self.client.post(
            f"/api/orders/{order.id}/confirm/",
            {},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)

    def test_transition_endpoint_without_permission_does_not_expose_order(self):
        order = self.create_order()
        self.assignment.delete()
        self.client.force_login(self.user)

        response = self.client.post(
            f"/api/orders/{order.id}/confirm/",
            {"company": self.company.id},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 404)


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
