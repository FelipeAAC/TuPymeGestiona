from decimal import Decimal
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from accounts.models import User
from administration.models import PaymentMethod
from catalog.models import Category, Product, ProductVariant
from customers.models import Customer
from inventory.models import InventoryMovement, InventoryStock
from inventory.services import apply_inventory_movement
from orders.models import Order, OrderItem
from orders.services import deliver_order
from organizations.models import (
    Branch,
    Company,
    CompanyMembership,
    CompanyRole,
    CompanyRolePermission,
    Permission,
    RoleAssignment,
    Warehouse,
)
from portal.models import CustomerPortalAccount
from reports.services import (
    InventoryFilters,
    SalesFilters,
    build_inventory_pdf,
    build_inventory_xlsx,
    build_sales_pdf,
    build_sales_xlsx,
    inventory_report_data,
    resolve_report_context,
    sales_report_data,
)
from sales.models import Sale, SaleReversal
from sales.services import create_pos_sale, reverse_pos_sale

from .models import MercadoPagoCheckout, MercadoPagoEvent, MercadoPagoRemotePayment
from .services import MercadoPagoConflictError, apply_payment_payload


class OperationalRegressionTests(TestCase):
    """Permanent lifecycle checks for payment, stock, sales and reports."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="ops-user",
            email="ops@example.test",
            password="Strong-password-123!",
            first_name="Ops",
            last_name="User",
        )
        self.company = Company.objects.create(name="Operational Company")
        self.branch = Branch.objects.create(company=self.company, code="MAIN", name="Main")
        self.branch_two = Branch.objects.create(company=self.company, code="SECOND", name="Second")
        self.warehouse = Warehouse.objects.create(company=self.company, branch=self.branch, code="WH-MAIN", name="Main warehouse")
        self.warehouse_two = Warehouse.objects.create(company=self.company, branch=self.branch_two, code="WH-SECOND", name="Second warehouse")
        self.category = Category.objects.create(company=self.company, name="General")
        self.product = Product.objects.create(
            company=self.company,
            category=self.category,
            name="Operational product",
            status=Product.Status.ACTIVE,
        )
        self.variant = ProductVariant.objects.create(
            product=self.product,
            sku="OPS-001",
            base_price=Decimal("1200.00"),
            status=ProductVariant.Status.ACTIVE,
        )
        self.variant_two = ProductVariant.objects.create(
            product=self.product,
            sku="OPS-002",
            base_price=Decimal("800.00"),
            status=ProductVariant.Status.ACTIVE,
        )
        self.customer = Customer.objects.create(
            company=self.company,
            code="CUS-001",
            name="Operational customer",
            email="customer@example.test",
        )
        self.portal_account = CustomerPortalAccount.objects.create(
            user=self.user,
            company=self.company,
            customer=self.customer,
        )
        self.cash = PaymentMethod.objects.create(
            company=self.company,
            code="CASH",
            name="Efectivo",
            kind=PaymentMethod.Kind.CASH,
        )
        self.online = PaymentMethod.objects.create(
            company=self.company,
            code="ONLINE",
            name="Pago en línea",
            kind=PaymentMethod.Kind.ONLINE,
        )
        InventoryStock.objects.create(warehouse=self.warehouse, variant=self.variant, quantity=Decimal("10"))
        InventoryStock.objects.create(warehouse=self.warehouse, variant=self.variant_two, quantity=Decimal("10"))

        admin_permission, _ = Permission.objects.get_or_create(
            code="administration.manage",
            defaults={"scope_behavior": Permission.ScopeBehavior.COMPANY_ONLY},
        )
        inventory_permission, _ = Permission.objects.get_or_create(
            code="inventory.stocks.manage",
            defaults={"scope_behavior": Permission.ScopeBehavior.BRANCH_SCOPED},
        )
        membership = CompanyMembership.objects.create(
            user=self.user,
            company=self.company,
            status=CompanyMembership.Status.ACTIVE,
        )
        role = CompanyRole.objects.create(
            company=self.company,
            name="Operations administrator",
            status=CompanyRole.Status.ACTIVE,
        )
        CompanyRolePermission.objects.bulk_create([
            CompanyRolePermission(role=role, permission=admin_permission),
            CompanyRolePermission(role=role, permission=inventory_permission),
        ])
        RoleAssignment.objects.create(membership=membership, role=role)

    def _delivered_order(self, *, total=Decimal("1200.00"), status=Order.Status.DELIVERED):
        order = Order.objects.create(
            company=self.company,
            branch=self.branch,
            warehouse=self.warehouse,
            customer=self.customer,
            number=Order.objects.filter(company=self.company).count() + 1,
            status=status,
            created_by=self.user,
        )
        OrderItem.objects.create(order=order, variant=self.variant, quantity=1, unit_price=total)
        return order

    def _checkout(self, order, *, status=MercadoPagoCheckout.Status.READY):
        return MercadoPagoCheckout.objects.create(
            order=order,
            portal_account=self.portal_account,
            status=status,
            external_reference=f"TPG-MP-{order.id}",
            amount=order.total,
            currency="CLP",
            idempotency_key=f"checkout-{order.id}",
            request_hash=f"hash-{order.id}",
            preference_id="pref-1",
            init_point="https://example.test/pay",
        )

    def test_approved_payment_creates_one_paid_sale_and_is_idempotent(self):
        order = self._delivered_order()
        checkout = self._checkout(order)
        payload = {
            "id": "payment-001",
            "external_reference": checkout.external_reference,
            "status": "approved",
            "status_detail": "accredited",
            "transaction_amount": "1200.00",
            "currency_id": "CLP",
            "live_mode": False,
            "date_created": timezone.now().isoformat(),
        }
        with patch("transactional_notifications.services.enqueue_payment_status_notification") as enqueue_notification:
            result, payment, created = apply_payment_payload(payload=payload, correlation_id="test")
            result_again, _, created_again = apply_payment_payload(payload=payload, correlation_id="retry")

        self.assertTrue(created)
        self.assertFalse(created_again)
        self.assertEqual(payment.provider_payment_id, "payment-001")
        self.assertEqual(MercadoPagoRemotePayment.objects.filter(checkout=checkout).count(), 1)
        self.assertEqual(
            MercadoPagoEvent.objects.filter(
                checkout=checkout,
                event_type=MercadoPagoEvent.EventType.PAYMENT_APPROVED,
            ).count(),
            1,
        )
        enqueue_notification.assert_called_once()
        sale = Sale.objects.get(order=order)
        self.assertEqual(sale.status, Sale.Status.PAID)
        self.assertEqual(sale.paid_amount, Decimal("1200.00"))
        self.assertEqual(sale.payments.count(), 1)
        self.assertEqual(result_again.sale_id, sale.id)

    def test_delivery_reconciles_approved_payment_into_sale(self):
        order = self._delivered_order(status=Order.Status.PREPARED)
        checkout = self._checkout(order, status=MercadoPagoCheckout.Status.APPROVED)
        MercadoPagoRemotePayment.objects.create(
            checkout=checkout,
            provider_payment_id="payment-delivery",
            status="approved",
            transaction_amount=checkout.amount,
            currency_id="CLP",
            payload_hash="delivery-hash",
        )
        with patch("transactional_notifications.services.enqueue_order_status_notification"):
            delivered = deliver_order(order=order, performed_by=self.user)
        self.assertEqual(delivered.status, Order.Status.DELIVERED)
        sale = Sale.objects.get(order=order)
        self.assertEqual(sale.status, Sale.Status.PAID)
        self.assertEqual(sale.payments.count(), 1)
        checkout.refresh_from_db()
        self.assertEqual(checkout.sale_id, sale.id)

    def test_duplicate_remote_payment_id_cannot_be_reassigned_between_checkouts(self):
        order = self._delivered_order()
        first = self._checkout(order)
        second_order = self._delivered_order()
        second = self._checkout(second_order)
        payload = {
            "id": "shared-payment",
            "external_reference": first.external_reference,
            "status": "approved",
            "transaction_amount": "1200.00",
            "currency_id": "CLP",
            "live_mode": False,
        }
        with patch("transactional_notifications.services.enqueue_payment_status_notification"):
            apply_payment_payload(payload=payload)
        payload["external_reference"] = second.external_reference
        with self.assertRaises(MercadoPagoConflictError):
            apply_payment_payload(payload=payload)
        self.assertEqual(MercadoPagoRemotePayment.objects.get(provider_payment_id="shared-payment").checkout_id, first.id)

    def test_inventory_entry_exit_updates_stock_and_rejects_cross_company_variant(self):
        movement, stock = apply_inventory_movement(
            warehouse=self.warehouse,
            variant=self.variant,
            movement_type=InventoryMovement.MovementType.ENTRY,
            quantity_delta=Decimal("2"),
            created_by=self.user,
        )
        self.assertEqual(movement.quantity_delta, Decimal("2"))
        self.assertEqual(stock.quantity, Decimal("12"))
        _, stock = apply_inventory_movement(
            warehouse=self.warehouse,
            variant=self.variant,
            movement_type=InventoryMovement.MovementType.EXIT,
            quantity_delta=Decimal("-3"),
            created_by=self.user,
        )
        self.assertEqual(stock.quantity, Decimal("9"))
        other = Company.objects.create(name="Other company")
        other_branch = Branch.objects.create(company=other, code="OTHER", name="Other")
        other_warehouse = Warehouse.objects.create(company=other, branch=other_branch, code="OTHER", name="Other")
        with self.assertRaises(ValidationError):
            apply_inventory_movement(
                warehouse=other_warehouse,
                variant=self.variant,
                movement_type=InventoryMovement.MovementType.ENTRY,
                quantity_delta=Decimal("1"),
                created_by=self.user,
            )

    def test_sale_reversal_restores_stock_once_and_preserves_idempotency(self):
        sale, _, created = create_pos_sale(
            company=self.company,
            branch=self.branch,
            warehouse=self.warehouse,
            customer=self.customer,
            items=[{"variant": self.variant, "quantity": "2"}],
            payment_method=self.cash,
            reference="POS-001",
            idempotency_key="pos-001",
            created_by=self.user,
        )
        self.assertTrue(created)
        self.assertEqual(InventoryStock.objects.get(warehouse=self.warehouse, variant=self.variant).quantity, Decimal("8"))
        reversed_sale, reversal, created_reversal = reverse_pos_sale(sale=sale, reference="REV-001", performed_by=self.user)
        _, repeated_reversal, repeated = reverse_pos_sale(sale=sale, reference="REV-001", performed_by=self.user)
        self.assertTrue(created_reversal)
        self.assertFalse(repeated)
        self.assertEqual(reversal.id, repeated_reversal.id)
        self.assertEqual(reversed_sale.status, Sale.Status.CANCELLED)
        self.assertEqual(InventoryStock.objects.get(warehouse=self.warehouse, variant=self.variant).quantity, Decimal("10"))
        self.assertEqual(SaleReversal.objects.filter(sale=sale).count(), 1)

    def test_reports_filter_exports_and_company_isolation(self):
        create_pos_sale(
            company=self.company,
            branch=self.branch,
            warehouse=self.warehouse,
            customer=self.customer,
            items=[{"variant": self.variant, "quantity": "1"}],
            payment_method=self.cash,
            reference="REPORT-001",
            idempotency_key="report-001",
            created_by=self.user,
        )
        context = resolve_report_context(user=self.user, company_id=self.company.id)
        sales = sales_report_data(context=context, filters=SalesFilters(branch_id=self.branch.id))
        self.assertEqual(sales["summary"]["records"], 1)
        self.assertEqual(sales["rows"][0]["branch_code"], "MAIN")
        self.assertTrue(build_sales_pdf(context=context, filters=SalesFilters(branch_id=self.branch.id)).startswith(b"%PDF"))
        self.assertTrue(build_sales_xlsx(context=context, filters=SalesFilters(branch_id=self.branch.id)).startswith(b"PK"))
        inventory = inventory_report_data(context=context, filters=InventoryFilters(warehouse_id=self.warehouse.id, stock_level="AVAILABLE"))
        self.assertTrue(all(row["warehouse_code"] == "WH-MAIN" for row in inventory["rows"]))
        self.assertTrue(build_inventory_pdf(context=context, filters=InventoryFilters(warehouse_id=self.warehouse.id)).startswith(b"%PDF"))
        self.assertTrue(build_inventory_xlsx(context=context, filters=InventoryFilters(warehouse_id=self.warehouse.id)).startswith(b"PK"))
        other = Company.objects.create(name="Isolated company")
        other_branch = Branch.objects.create(company=other, code="OTHER", name="Other")
        other_warehouse = Warehouse.objects.create(company=other, branch=other_branch, code="OTHER", name="Other")
        other_customer = Customer.objects.create(company=other, code="OTHER-001", name="Other customer")
        Sale.objects.create(
            company=other,
            branch=other_branch,
            warehouse=other_warehouse,
            customer=other_customer,
            origin=Sale.Origin.POS,
            number=1,
            status=Sale.Status.PAID,
            total_amount=Decimal("99.00"),
            paid_amount=Decimal("99.00"),
            idempotency_key="other-report-001",
            created_by=self.user,
        )
        self.assertEqual(sales_report_data(context=context, filters=SalesFilters())["summary"]["records"], 1)

    def test_branch_scoped_inventory_report_excludes_other_branch(self):
        InventoryStock.objects.create(warehouse=self.warehouse_two, variant=self.variant, quantity=Decimal("7"))
        permission = Permission.objects.get(code="inventory.stocks.manage")
        scoped_user = User.objects.create_user(
            username="branch-ops",
            email="branch-ops@example.test",
            password="Strong-password-123!",
        )
        membership = CompanyMembership.objects.create(
            user=scoped_user,
            company=self.company,
            status=CompanyMembership.Status.ACTIVE,
        )
        role = CompanyRole.objects.create(
            company=self.company,
            name="Branch inventory operator",
            status=CompanyRole.Status.ACTIVE,
        )
        CompanyRolePermission.objects.create(role=role, permission=permission)
        from organizations.models import MembershipBranch

        MembershipBranch.objects.create(membership=membership, branch=self.branch)
        RoleAssignment.objects.create(membership=membership, role=role, branch=self.branch)
        context = resolve_report_context(user=scoped_user, company_id=self.company.id)
        self.assertEqual(context.inventory_warehouse_ids, frozenset({self.warehouse.id}))
        data = inventory_report_data(context=context, filters=InventoryFilters())
        self.assertTrue(data["rows"])
        self.assertTrue(all(row["warehouse_code"] == self.warehouse.code for row in data["rows"]))
