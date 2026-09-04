from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone

from customers.models import Customer
from external_payments.models import MercadoPagoCheckout
from external_payments.services import apply_payment_payload
from orders.models import Order
from orders.services import _set_order_status
from organizations.models import Branch, Company, Warehouse
from portal.models import CustomerPortalAccount

from .models import TransactionalNotification, TransactionalNotificationAttempt
from .services import (
    enqueue_order_status_notification,
    mark_stale_sending_uncertain,
    process_one_notification,
)


User = get_user_model()


@override_settings(TRANSACTIONAL_EMAIL_FROM="no-reply@example.test")
class TransactionalNotificationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="cliente@example.test",
            email="cliente@example.test",
            password="test-pass-123",
        )
        self.company = Company.objects.create(name="Comercial Demo")
        self.branch = Branch.objects.create(
            company=self.company,
            code="CASA",
            name="Casa Matriz",
        )
        self.warehouse = Warehouse.objects.create(
            company=self.company,
            branch=self.branch,
            code="B1",
            name="Bodega 1",
        )
        self.customer = Customer.objects.create(
            company=self.company,
            code="C1",
            name="Cliente Demo",
            email="cliente@example.test",
        )
        self.order = Order.objects.create(
            company=self.company,
            branch=self.branch,
            warehouse=self.warehouse,
            customer=self.customer,
            number=1,
            status=Order.Status.DRAFT,
            created_by=self.user,
        )

    def test_order_status_hook_creates_outbox_and_is_idempotent(self):
        _set_order_status(order=self.order, new_status=Order.Status.CONFIRMED)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.CONFIRMED)
        message = TransactionalNotification.objects.get()
        self.assertEqual(message.kind, TransactionalNotification.Kind.ORDER_CONFIRMED)
        self.assertEqual(message.recipient_email, "cliente@example.test")
        self.assertEqual(message.status, TransactionalNotification.Status.PENDING)

        duplicate, created = enqueue_order_status_notification(order=self.order)
        self.assertFalse(created)
        self.assertEqual(duplicate.pk, message.pk)
        self.assertEqual(TransactionalNotification.objects.count(), 1)

    def test_customer_without_email_does_not_create_outbox(self):
        self.customer.email = ""
        self.customer.save(update_fields=("email", "updated_at"))
        _set_order_status(order=self.order, new_status=Order.Status.CONFIRMED)
        self.assertEqual(TransactionalNotification.objects.count(), 0)

    def test_successful_processing_marks_sent_and_logs_attempt(self):
        _set_order_status(order=self.order, new_status=Order.Status.CONFIRMED)
        message = TransactionalNotification.objects.get()

        result, sent = process_one_notification(
            message.id,
            sender=lambda notification: "fake-message-id",
        )

        self.assertTrue(sent)
        self.assertEqual(result.status, TransactionalNotification.Status.SENT)
        self.assertEqual(result.provider_message_id, "fake-message-id")
        attempt = TransactionalNotificationAttempt.objects.get(notification=result)
        self.assertEqual(attempt.outcome, TransactionalNotificationAttempt.Outcome.SENT)

    @override_settings(TRANSACTIONAL_EMAIL_MAX_ATTEMPTS=2, TRANSACTIONAL_EMAIL_RETRY_MINUTES=1)
    def test_transient_failure_retries_then_fails_at_limit(self):
        _set_order_status(order=self.order, new_status=Order.Status.CONFIRMED)
        message = TransactionalNotification.objects.get()
        now = timezone.now()

        first, sent = process_one_notification(
            message.id,
            sender=lambda notification: (_ for _ in ()).throw(OSError("smtp unavailable")),
            now=now,
        )
        self.assertFalse(sent)
        self.assertEqual(first.status, TransactionalNotification.Status.RETRY)
        self.assertEqual(first.attempts, 1)
        self.assertIsNotNone(first.next_attempt_at)

        second, sent = process_one_notification(
            message.id,
            sender=lambda notification: (_ for _ in ()).throw(OSError("smtp unavailable")),
            now=now + timedelta(days=1),
        )
        self.assertFalse(sent)
        self.assertEqual(second.status, TransactionalNotification.Status.FAILED)
        self.assertEqual(second.attempts, 2)
        self.assertEqual(
            list(second.attempt_log.values_list("outcome", flat=True)),
            [
                TransactionalNotificationAttempt.Outcome.RETRY,
                TransactionalNotificationAttempt.Outcome.FAILED,
            ],
        )

    @override_settings(TRANSACTIONAL_EMAIL_SENDING_STALE_MINUTES=5)
    def test_stale_sending_becomes_uncertain_without_automatic_resend(self):
        _set_order_status(order=self.order, new_status=Order.Status.CONFIRMED)
        message = TransactionalNotification.objects.get()
        message.status = TransactionalNotification.Status.SENDING
        message.attempts = 1
        message.sending_started_at = timezone.now() - timedelta(minutes=10)
        message.save(update_fields=("status", "attempts", "sending_started_at", "updated_at"))

        count = mark_stale_sending_uncertain()

        self.assertEqual(count, 1)
        message.refresh_from_db()
        self.assertEqual(message.status, TransactionalNotification.Status.UNCERTAIN)
        self.assertIsNone(message.next_attempt_at)
        self.assertEqual(message.last_error_code, "SEND_RESULT_UNCERTAIN")

    def test_payment_payload_enqueues_one_approved_notification(self):
        self.order.status = Order.Status.CONFIRMED
        self.order.save(update_fields=("status", "updated_at"))
        account = CustomerPortalAccount.objects.create(
            user=self.user,
            company=self.company,
            customer=self.customer,
        )
        checkout = MercadoPagoCheckout.objects.create(
            order=self.order,
            portal_account=account,
            status=MercadoPagoCheckout.Status.READY,
            external_reference=f"TPG-MP-{self.company.id}-{self.order.id}",
            amount=Decimal("1000.00"),
            currency="CLP",
            idempotency_key="checkout-1",
            request_hash="a" * 64,
            preference_id="pref-1",
            init_point="https://example.test/pay",
        )
        payload = {
            "id": "pay-1",
            "external_reference": checkout.external_reference,
            "status": "approved",
            "status_detail": "accredited",
            "transaction_amount": "1000.00",
            "currency_id": "CLP",
            "live_mode": False,
        }

        updated, payment, valid = apply_payment_payload(payload=payload, correlation_id="test")
        self.assertTrue(valid)
        self.assertEqual(updated.status, MercadoPagoCheckout.Status.APPROVED)
        message = TransactionalNotification.objects.get(kind=TransactionalNotification.Kind.PAYMENT_APPROVED)
        self.assertEqual(message.checkout_id, checkout.id)
        self.assertEqual(message.payload["provider_payment_id"], "pay-1")

        apply_payment_payload(payload=payload, correlation_id="duplicate")
        self.assertEqual(
            TransactionalNotification.objects.filter(kind=TransactionalNotification.Kind.PAYMENT_APPROVED).count(),
            1,
        )
