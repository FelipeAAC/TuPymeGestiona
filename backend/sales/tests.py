from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from rest_framework.test import APIClient

from catalog.models import Category, Product, ProductVariant
from customers.models import Customer
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

from .models import Payment, Sale, SaleEvent, SaleNumberSequence
from .services import (
    SaleIdempotencyConflictError,
    SaleTransitionError,
    cancel_sale,
    create_sale,
    record_payment,
)
from .views import SALES_MANAGE_PERMISSION_CODE


User = get_user_model()


class SaleFixtureMixin:
    def setUp(self):
        super().setUp()
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="sales-user",
            email="sales@example.com",
            password="test-password",
        )
        self.company = Company.objects.create(name="Empresa Ventas")
        self.other_company = Company.objects.create(
            name="Otra Empresa Ventas",
        )
        self.branch = Branch.objects.create(
            company=self.company,
            code="SUC-VTA-01",
            name="Sucursal Ventas",
        )
        self.other_branch = Branch.objects.create(
            company=self.company,
            code="SUC-VTA-02",
            name="Otra Sucursal Ventas",
        )
        self.foreign_branch = Branch.objects.create(
            company=self.other_company,
            code="SUC-VTA-EXT",
            name="Sucursal Externa",
        )
        self.warehouse = Warehouse.objects.create(
            company=self.company,
            branch=self.branch,
            code="BOD-VTA-01",
            name="Bodega Ventas",
        )
        self.other_warehouse = Warehouse.objects.create(
            company=self.company,
            branch=self.other_branch,
            code="BOD-VTA-02",
            name="Otra Bodega Ventas",
        )
        self.foreign_warehouse = Warehouse.objects.create(
            company=self.other_company,
            branch=self.foreign_branch,
            code="BOD-VTA-EXT",
            name="Bodega Externa",
        )
        self.customer = Customer.objects.create(
            company=self.company,
            code="CLI-VTA-01",
            name="Cliente Ventas",
        )
        self.foreign_customer = Customer.objects.create(
            company=self.other_company,
            code="CLI-VTA-EXT",
            name="Cliente Externo",
        )

        category = Category.objects.create(
            company=self.company,
            name="Categoria Ventas",
        )
        product = Product.objects.create(
            company=self.company,
            category=category,
            name="Producto Ventas",
            status=Product.Status.ACTIVE,
        )
        self.variant = ProductVariant.objects.create(
            product=product,
            sku="SKU-VTA-01",
            base_price=Decimal("1250.00"),
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
            sku="SKU-VTA-EXT",
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
            code=SALES_MANAGE_PERMISSION_CODE,
        )
        self.role = CompanyRole.objects.create(
            company=self.company,
            name="Administrador Ventas",
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
        company=None,
        branch=None,
        warehouse=None,
        customer=None,
        variant=None,
        status=Order.Status.DELIVERED,
        quantity=Decimal("2.000"),
        unit_price=Decimal("1250.00"),
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
            quantity=quantity,
            unit_price=unit_price,
        )
        return order

    def create_foreign_order(self, *, number=1):
        return self.create_order(
            number=number,
            company=self.other_company,
            branch=self.foreign_branch,
            warehouse=self.foreign_warehouse,
            customer=self.foreign_customer,
            variant=self.foreign_variant,
        )

    def create_sale_for_order(
        self,
        order,
        *,
        key="sale-key-1",
    ):
        sale, _ = create_sale(
            company=order.company,
            order=order,
            idempotency_key=key,
            created_by=self.user,
        )
        return sale

    def sale_payload(self, order, *, key="sale-key-1"):
        return {
            "company": self.company.id,
            "order": order.id,
            "idempotency_key": key,
        }

    def payment_payload(
        self,
        *,
        amount="500.00",
        reference="TRANSFER-001",
        key="payment-key-1",
    ):
        return {
            "company": self.company.id,
            "amount": amount,
            "reference": reference,
            "idempotency_key": key,
        }


class SaleModelTests(SaleFixtureMixin, TestCase):
    def test_sales_permission_is_branch_scoped(self):
        self.assertEqual(
            self.permission.scope_behavior,
            Permission.ScopeBehavior.BRANCH_SCOPED,
        )

    def test_sale_number_is_unique_inside_company(self):
        first = self.create_order(number=1)
        second = self.create_order(number=2)
        self.create_sale_for_order(first, key="first-key")

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Sale.objects.bulk_create(
                    [
                        Sale(
                            company=self.company,
                            branch=self.branch,
                            order=second,
                            number=1,
                            status=Sale.Status.PENDING,
                            total_amount=second.total,
                            paid_amount=0,
                            idempotency_key="second-key",
                            created_by=self.user,
                        )
                    ]
                )

    def test_sale_idempotency_key_is_unique_inside_company(self):
        first = self.create_order(number=1)
        second = self.create_order(number=2)
        self.create_sale_for_order(first, key="shared-key")

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Sale.objects.bulk_create(
                    [
                        Sale(
                            company=self.company,
                            branch=self.branch,
                            order=second,
                            number=2,
                            status=Sale.Status.PENDING,
                            total_amount=second.total,
                            paid_amount=0,
                            idempotency_key="shared-key",
                            created_by=self.user,
                        )
                    ]
                )

    def test_sale_rejects_cross_tenant_order(self):
        foreign_order = self.create_foreign_order()

        with self.assertRaises(ValidationError):
            Sale.objects.create(
                company=self.company,
                branch=self.branch,
                order=foreign_order,
                number=1,
                status=Sale.Status.PENDING,
                total_amount=foreign_order.total,
                paid_amount=0,
                idempotency_key="cross-tenant",
                created_by=self.user,
            )

    def test_sale_rejects_inconsistent_payment_status(self):
        order = self.create_order()

        with self.assertRaises(ValidationError):
            Sale.objects.create(
                company=self.company,
                branch=self.branch,
                order=order,
                number=1,
                status=Sale.Status.PAID,
                total_amount=order.total,
                paid_amount=Decimal("100.00"),
                idempotency_key="invalid-status",
                created_by=self.user,
            )

    def test_payment_requires_positive_amount_and_reference(self):
        sale = self.create_sale_for_order(self.create_order())

        with self.assertRaises(ValidationError):
            Payment.objects.create(
                sale=sale,
                amount=Decimal("0.00"),
                reference=" ",
                idempotency_key="payment-invalid",
                recorded_by=self.user,
            )


class SaleServiceTests(SaleFixtureMixin, TestCase):
    def test_create_sale_snapshots_total_number_and_audit_event(self):
        order = self.create_order()

        sale, created = create_sale(
            company=self.company,
            order=order,
            idempotency_key=" create-001 ",
            created_by=self.user,
        )

        self.assertTrue(created)
        self.assertEqual(sale.number, 1)
        self.assertEqual(sale.status, Sale.Status.PENDING)
        self.assertEqual(sale.total_amount, Decimal("2500.00"))
        self.assertEqual(sale.paid_amount, Decimal("0.00"))
        self.assertEqual(sale.idempotency_key, "create-001")
        self.assertEqual(sale.events.count(), 1)
        event = sale.events.get()
        self.assertEqual(event.event_type, SaleEvent.EventType.CREATED)
        self.assertEqual(event.new_status, Sale.Status.PENDING)
        self.assertEqual(
            SaleNumberSequence.objects.get(company=self.company).next_number,
            2,
        )

    def test_create_sale_requires_delivered_order(self):
        order = self.create_order(status=Order.Status.PREPARED)

        with self.assertRaises(SaleTransitionError):
            create_sale(
                company=self.company,
                order=order,
                idempotency_key="prepared-order",
                created_by=self.user,
            )

        self.assertFalse(Sale.objects.exists())

    def test_create_sale_replays_same_idempotent_request(self):
        order = self.create_order()
        first, first_created = create_sale(
            company=self.company,
            order=order,
            idempotency_key="same-sale-key",
            created_by=self.user,
        )
        second, second_created = create_sale(
            company=self.company,
            order=order,
            idempotency_key="same-sale-key",
            created_by=self.user,
        )

        self.assertTrue(first_created)
        self.assertFalse(second_created)
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(Sale.objects.count(), 1)
        self.assertEqual(SaleEvent.objects.count(), 1)

    def test_create_sale_rejects_key_reuse_for_another_order(self):
        first = self.create_order(number=1)
        second = self.create_order(number=2)
        self.create_sale_for_order(first, key="reused-sale-key")

        with self.assertRaises(SaleIdempotencyConflictError):
            create_sale(
                company=self.company,
                order=second,
                idempotency_key="reused-sale-key",
                created_by=self.user,
            )

    def test_create_sale_rejects_second_sale_for_order(self):
        order = self.create_order()
        self.create_sale_for_order(order, key="first-key")

        with self.assertRaises(SaleTransitionError):
            create_sale(
                company=self.company,
                order=order,
                idempotency_key="second-key",
                created_by=self.user,
            )

    def test_create_sale_rolls_back_when_audit_fails(self):
        order = self.create_order()

        with patch(
            "sales.services.SaleEvent.objects.create",
            side_effect=RuntimeError("audit failure"),
        ):
            with self.assertRaises(RuntimeError):
                create_sale(
                    company=self.company,
                    order=order,
                    idempotency_key="rollback-sale",
                    created_by=self.user,
                )

        self.assertFalse(Sale.objects.exists())
        self.assertFalse(SaleNumberSequence.objects.exists())

    def test_record_payment_moves_pending_to_partial(self):
        sale = self.create_sale_for_order(self.create_order())

        sale, payment, created = record_payment(
            sale=sale,
            amount=Decimal("500.00"),
            reference=" TRANSFER-001 ",
            idempotency_key=" payment-001 ",
            performed_by=self.user,
        )

        self.assertTrue(created)
        self.assertEqual(payment.reference, "TRANSFER-001")
        self.assertEqual(payment.idempotency_key, "payment-001")
        self.assertEqual(sale.status, Sale.Status.PARTIAL)
        self.assertEqual(sale.paid_amount, Decimal("500.00"))
        self.assertEqual(sale.balance, Decimal("2000.00"))
        event = sale.events.get(
            event_type=SaleEvent.EventType.PAYMENT_RECORDED,
        )
        self.assertEqual(event.previous_status, Sale.Status.PENDING)
        self.assertEqual(event.new_status, Sale.Status.PARTIAL)
        self.assertEqual(event.payment, payment)

    def test_record_payment_moves_partial_to_paid(self):
        sale = self.create_sale_for_order(self.create_order())
        sale, _, _ = record_payment(
            sale=sale,
            amount=Decimal("500.00"),
            reference="FIRST",
            idempotency_key="first-payment",
            performed_by=self.user,
        )
        sale, _, _ = record_payment(
            sale=sale,
            amount=Decimal("2000.00"),
            reference="FINAL",
            idempotency_key="final-payment",
            performed_by=self.user,
        )

        self.assertEqual(sale.status, Sale.Status.PAID)
        self.assertEqual(sale.paid_amount, sale.total_amount)
        self.assertEqual(sale.balance, Decimal("0.00"))
        self.assertEqual(sale.payments.count(), 2)
        self.assertEqual(sale.events.count(), 3)

    def test_record_payment_rejects_overpayment_without_changes(self):
        sale = self.create_sale_for_order(self.create_order())

        with self.assertRaises(SaleTransitionError):
            record_payment(
                sale=sale,
                amount=Decimal("2500.01"),
                reference="TOO-MUCH",
                idempotency_key="overpayment",
                performed_by=self.user,
            )

        sale.refresh_from_db()
        self.assertEqual(sale.status, Sale.Status.PENDING)
        self.assertEqual(sale.paid_amount, Decimal("0.00"))
        self.assertFalse(Payment.objects.exists())

    def test_record_payment_replays_same_idempotent_request(self):
        sale = self.create_sale_for_order(self.create_order())
        first_sale, first_payment, first_created = record_payment(
            sale=sale,
            amount=Decimal("500.00"),
            reference="REPLAY",
            idempotency_key="replay-payment",
            performed_by=self.user,
        )
        second_sale, second_payment, second_created = record_payment(
            sale=first_sale,
            amount=Decimal("500.00"),
            reference="REPLAY",
            idempotency_key="replay-payment",
            performed_by=self.user,
        )

        self.assertTrue(first_created)
        self.assertFalse(second_created)
        self.assertEqual(first_payment.pk, second_payment.pk)
        self.assertEqual(second_sale.paid_amount, Decimal("500.00"))
        self.assertEqual(Payment.objects.count(), 1)
        self.assertEqual(SaleEvent.objects.count(), 2)

    def test_record_payment_rejects_key_reuse_with_other_payload(self):
        sale = self.create_sale_for_order(self.create_order())
        sale, _, _ = record_payment(
            sale=sale,
            amount=Decimal("500.00"),
            reference="ORIGINAL",
            idempotency_key="conflict-payment",
            performed_by=self.user,
        )

        with self.assertRaises(SaleIdempotencyConflictError):
            record_payment(
                sale=sale,
                amount=Decimal("600.00"),
                reference="CHANGED",
                idempotency_key="conflict-payment",
                performed_by=self.user,
            )

        sale.refresh_from_db()
        self.assertEqual(sale.paid_amount, Decimal("500.00"))
        self.assertEqual(Payment.objects.count(), 1)

    def test_record_payment_rolls_back_when_audit_fails(self):
        sale = self.create_sale_for_order(self.create_order())

        with patch(
            "sales.services.SaleEvent.objects.create",
            side_effect=RuntimeError("audit failure"),
        ):
            with self.assertRaises(RuntimeError):
                record_payment(
                    sale=sale,
                    amount=Decimal("500.00"),
                    reference="ROLLBACK",
                    idempotency_key="rollback-payment",
                    performed_by=self.user,
                )

        sale.refresh_from_db()
        self.assertEqual(sale.status, Sale.Status.PENDING)
        self.assertEqual(sale.paid_amount, Decimal("0.00"))
        self.assertFalse(Payment.objects.exists())

    def test_cancel_pending_sale_and_replay_without_duplicate_event(self):
        sale = self.create_sale_for_order(self.create_order())
        sale, changed = cancel_sale(sale=sale, performed_by=self.user)
        replayed, replay_changed = cancel_sale(
            sale=sale,
            performed_by=self.user,
        )

        self.assertTrue(changed)
        self.assertFalse(replay_changed)
        self.assertEqual(replayed.status, Sale.Status.CANCELLED)
        self.assertEqual(replayed.cancelled_by, self.user)
        self.assertIsNotNone(replayed.cancelled_at)
        self.assertEqual(
            replayed.events.filter(
                event_type=SaleEvent.EventType.CANCELLED,
            ).count(),
            1,
        )

    def test_cancel_rejects_sale_with_payments(self):
        sale = self.create_sale_for_order(self.create_order())
        sale, _, _ = record_payment(
            sale=sale,
            amount=Decimal("500.00"),
            reference="PARTIAL",
            idempotency_key="partial-before-cancel",
            performed_by=self.user,
        )

        with self.assertRaises(SaleTransitionError):
            cancel_sale(sale=sale, performed_by=self.user)

        sale.refresh_from_db()
        self.assertEqual(sale.status, Sale.Status.PARTIAL)

    def test_zero_total_sale_starts_paid(self):
        order = self.create_order(unit_price=Decimal("0.00"))
        sale = self.create_sale_for_order(order)

        self.assertEqual(sale.status, Sale.Status.PAID)
        self.assertEqual(sale.total_amount, Decimal("0.00"))
        self.assertEqual(sale.balance, Decimal("0.00"))


class SaleApiTests(SaleFixtureMixin, TestCase):
    def test_sales_api_requires_authentication(self):
        response = self.client.get(
            "/api/sales/",
            {"company": self.company.id},
        )

        self.assertEqual(response.status_code, 403)

    def test_create_sale_returns_commercial_snapshot(self):
        order = self.create_order()
        self.client.force_login(self.user)

        response = self.client.post(
            "/api/sales/",
            self.sale_payload(order),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertFalse(response.data["idempotent_replay"])
        self.assertEqual(response.data["sale"]["number"], 1)
        self.assertEqual(response.data["sale"]["order"], order.id)
        self.assertEqual(response.data["sale"]["order_number"], 1)
        self.assertEqual(response.data["sale"]["total_amount"], "2500.00")
        self.assertEqual(response.data["sale"]["balance"], "2500.00")
        self.assertEqual(len(response.data["sale"]["events"]), 1)

    def test_create_sale_requires_valid_company(self):
        order = self.create_order()
        self.client.force_login(self.user)

        missing = self.sale_payload(order)
        missing.pop("company")
        missing_response = self.client.post(
            "/api/sales/",
            missing,
            content_type="application/json",
        )
        invalid = self.sale_payload(order)
        invalid["company"] = "invalid"
        invalid_response = self.client.post(
            "/api/sales/",
            invalid,
            content_type="application/json",
        )

        self.assertEqual(missing_response.status_code, 400)
        self.assertEqual(invalid_response.status_code, 400)
        self.assertFalse(Sale.objects.exists())

    def test_create_sale_denies_branch_outside_role_scope(self):
        order = self.create_order(
            branch=self.other_branch,
            warehouse=self.other_warehouse,
        )
        self.client.force_login(self.user)

        response = self.client.post(
            "/api/sales/",
            self.sale_payload(order),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 403)
        self.assertFalse(Sale.objects.exists())

    def test_create_sale_rejects_cross_tenant_order(self):
        order = self.create_foreign_order()
        self.client.force_login(self.user)

        response = self.client.post(
            "/api/sales/",
            self.sale_payload(order),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(Sale.objects.exists())

    def test_create_sale_rejects_non_delivered_order(self):
        order = self.create_order(status=Order.Status.PREPARED)
        self.client.force_login(self.user)

        response = self.client.post(
            "/api/sales/",
            self.sale_payload(order),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 409)
        self.assertFalse(Sale.objects.exists())

    def test_create_sale_idempotent_replay_returns_existing_sale(self):
        order = self.create_order()
        self.client.force_login(self.user)
        payload = self.sale_payload(order)
        first = self.client.post(
            "/api/sales/",
            payload,
            content_type="application/json",
        )
        second = self.client.post(
            "/api/sales/",
            payload,
            content_type="application/json",
        )

        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 200)
        self.assertTrue(second.data["idempotent_replay"])
        self.assertEqual(first.data["sale"]["id"], second.data["sale"]["id"])
        self.assertEqual(Sale.objects.count(), 1)

    def test_list_only_returns_sales_from_authorized_branch(self):
        allowed_order = self.create_order(number=1)
        hidden_order = self.create_order(
            number=2,
            branch=self.other_branch,
            warehouse=self.other_warehouse,
        )
        allowed = self.create_sale_for_order(
            allowed_order,
            key="allowed-sale",
        )
        self.create_sale_for_order(hidden_order, key="hidden-sale")
        self.client.force_login(self.user)

        response = self.client.get(
            "/api/sales/",
            {"company": self.company.id},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["pagination"]["count"], 1)
        self.assertEqual(
            [sale["id"] for sale in response.data["sales"]],
            [allowed.id],
        )

    def test_detail_does_not_expose_other_branch(self):
        order = self.create_order(
            branch=self.other_branch,
            warehouse=self.other_warehouse,
        )
        hidden = self.create_sale_for_order(order)
        self.client.force_login(self.user)

        response = self.client.get(
            f"/api/sales/{hidden.id}/",
            {"company": self.company.id},
        )

        self.assertEqual(response.status_code, 404)

    def test_list_filters_status_and_searches_payment_reference(self):
        partial = self.create_sale_for_order(
            self.create_order(number=1),
            key="partial-sale",
        )
        record_payment(
            sale=partial,
            amount=Decimal("500.00"),
            reference="BANK-ABC-123",
            idempotency_key="search-payment",
            performed_by=self.user,
        )
        self.create_sale_for_order(
            self.create_order(number=2),
            key="pending-sale",
        )
        self.client.force_login(self.user)

        response = self.client.get(
            "/api/sales/",
            {
                "company": self.company.id,
                "status": Sale.Status.PARTIAL,
                "search": "ABC-123",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["pagination"]["count"], 1)
        self.assertEqual(response.data["sales"][0]["id"], partial.id)

    def test_record_payment_returns_partial_sale_and_audit(self):
        sale = self.create_sale_for_order(self.create_order())
        self.client.force_login(self.user)

        response = self.client.post(
            f"/api/sales/{sale.id}/payments/",
            self.payment_payload(),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertFalse(response.data["idempotent_replay"])
        self.assertEqual(response.data["sale"]["status"], Sale.Status.PARTIAL)
        self.assertEqual(response.data["sale"]["paid_amount"], "500.00")
        self.assertEqual(response.data["sale"]["balance"], "2000.00")
        self.assertEqual(response.data["payment"]["reference"], "TRANSFER-001")
        self.assertEqual(len(response.data["sale"]["events"]), 2)

    def test_record_payment_replay_returns_same_payment(self):
        sale = self.create_sale_for_order(self.create_order())
        self.client.force_login(self.user)
        payload = self.payment_payload()
        first = self.client.post(
            f"/api/sales/{sale.id}/payments/",
            payload,
            content_type="application/json",
        )
        second = self.client.post(
            f"/api/sales/{sale.id}/payments/",
            payload,
            content_type="application/json",
        )

        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 200)
        self.assertTrue(second.data["idempotent_replay"])
        self.assertEqual(
            first.data["payment"]["id"],
            second.data["payment"]["id"],
        )
        self.assertEqual(Payment.objects.count(), 1)

    def test_record_payment_key_conflict_returns_conflict(self):
        sale = self.create_sale_for_order(self.create_order())
        self.client.force_login(self.user)
        first = self.payment_payload()
        second = self.payment_payload(
            amount="600.00",
            reference="CHANGED",
        )
        self.client.post(
            f"/api/sales/{sale.id}/payments/",
            first,
            content_type="application/json",
        )
        response = self.client.post(
            f"/api/sales/{sale.id}/payments/",
            second,
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 409)
        sale.refresh_from_db()
        self.assertEqual(sale.paid_amount, Decimal("500.00"))

    def test_record_payment_rejects_overpayment(self):
        sale = self.create_sale_for_order(self.create_order())
        self.client.force_login(self.user)

        response = self.client.post(
            f"/api/sales/{sale.id}/payments/",
            self.payment_payload(amount="2500.01"),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 409)
        self.assertFalse(Payment.objects.exists())

    def test_cancel_sale_is_replay_safe_and_blocks_new_payment(self):
        sale = self.create_sale_for_order(self.create_order())
        self.client.force_login(self.user)
        first = self.client.post(
            f"/api/sales/{sale.id}/cancel/",
            {"company": self.company.id},
            content_type="application/json",
        )
        second = self.client.post(
            f"/api/sales/{sale.id}/cancel/",
            {"company": self.company.id},
            content_type="application/json",
        )
        payment = self.client.post(
            f"/api/sales/{sale.id}/payments/",
            self.payment_payload(),
            content_type="application/json",
        )

        self.assertEqual(first.status_code, 200)
        self.assertFalse(first.data["already_cancelled"])
        self.assertEqual(second.status_code, 200)
        self.assertTrue(second.data["already_cancelled"])
        self.assertEqual(payment.status_code, 409)
        self.assertEqual(
            SaleEvent.objects.filter(
                sale=sale,
                event_type=SaleEvent.EventType.CANCELLED,
            ).count(),
            1,
        )

    def test_options_only_return_unsold_delivered_authorized_orders(self):
        available = self.create_order(number=1)
        sold = self.create_order(number=2)
        self.create_sale_for_order(sold, key="sold-order")
        self.create_order(
            number=3,
            status=Order.Status.PREPARED,
        )
        self.create_order(
            number=4,
            branch=self.other_branch,
            warehouse=self.other_warehouse,
        )
        self.client.force_login(self.user)

        response = self.client.get(
            "/api/sales/options/",
            {"company": self.company.id},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["permissions"], {"manage": True})
        self.assertEqual(
            [order["id"] for order in response.data["delivered_orders"]],
            [available.id],
        )
        self.assertEqual(
            [branch["id"] for branch in response.data["branches"]],
            [self.branch.id],
        )

    def test_options_without_permission_are_empty(self):
        self.assignment.delete()
        self.create_order()
        self.client.force_login(self.user)

        response = self.client.get(
            "/api/sales/options/",
            {"company": self.company.id},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["permissions"], {"manage": False})
        self.assertEqual(response.data["branches"], [])
        self.assertEqual(response.data["delivered_orders"], [])

    def test_suspended_membership_does_not_authorize_sales(self):
        order = self.create_order()
        self.membership.status = CompanyMembership.Status.SUSPENDED
        self.membership.save(update_fields=("status",))
        self.client.force_login(self.user)

        response = self.client.post(
            "/api/sales/",
            self.sale_payload(order),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 403)
        self.assertFalse(Sale.objects.exists())
