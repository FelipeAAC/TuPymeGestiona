from datetime import timedelta

from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APITestCase

from .models import (
    ElectronicTaxDocument,
    ElectronicTaxExchange,
    ElectronicTaxOperationalAlert,
    ElectronicTaxStatusCheckTask,
    FolioAuthorization,
)
from .operations import (
    integrity_snapshot,
    operational_summary,
    process_status_check_tasks,
    scan_company_operations,
)
from .services import FakeElectronicTaxProvider
from .tests import ElectronicTaxFixtureMixin


class ElectronicTaxOperationsTests(ElectronicTaxFixtureMixin, TestCase):
    @override_settings(ELECTRONIC_TAX_FOLIO_LOW_THRESHOLD=5, SII_ADAPTER_ENABLED=False)
    def test_scan_creates_and_resolves_low_folio_alert(self):
        authorization = FolioAuthorization.objects.create(
            company=self.company,
            type_code=33,
            start_folio=100,
            end_folio=109,
            next_folio=106,
            status=FolioAuthorization.Status.ACTIVE,
        )
        result = scan_company_operations(company=self.company)
        self.assertEqual(result["warning"], 1)
        alert = ElectronicTaxOperationalAlert.objects.get(company=self.company, code="FOLIO_LOW")
        self.assertEqual(alert.status, ElectronicTaxOperationalAlert.Status.OPEN)
        self.assertEqual(alert.details["remaining"], 4)

        authorization.next_folio = 102
        authorization.save(update_fields=("next_folio", "updated_at"))
        scan_company_operations(company=self.company)
        alert.refresh_from_db()
        self.assertEqual(alert.status, ElectronicTaxOperationalAlert.Status.RESOLVED)
        self.assertIsNotNone(alert.resolved_at)

    @override_settings(
        ELECTRONIC_TAX_STALE_MINUTES=10,
        ELECTRONIC_TAX_STATUS_RETRY_MINUTES=1,
        SII_ADAPTER_ENABLED=False,
    )
    def test_stale_send_uncertain_creates_alert_and_status_query_task(self):
        document = self.create_document()
        old = timezone.now() - timedelta(minutes=30)
        ElectronicTaxDocument.objects.filter(pk=document.pk).update(
            state=ElectronicTaxDocument.State.SEND_UNCERTAIN,
            folio=123,
            updated_at=old,
        )
        scan_company_operations(company=self.company, now=timezone.now())
        self.assertTrue(
            ElectronicTaxOperationalAlert.objects.filter(
                company=self.company,
                code="REMOTE_STATUS_STALE",
                severity=ElectronicTaxOperationalAlert.Severity.CRITICAL,
                status=ElectronicTaxOperationalAlert.Status.OPEN,
            ).exists()
        )
        task = ElectronicTaxStatusCheckTask.objects.get(document=document)
        self.assertEqual(task.state, ElectronicTaxStatusCheckTask.State.PENDING)
        self.assertEqual(task.actor, self.user)

    @override_settings(ELECTRONIC_TAX_STATUS_RETRY_MINUTES=1)
    def test_status_query_worker_resolves_with_fake_without_resending(self):
        document = self.create_document()
        ElectronicTaxDocument.objects.filter(pk=document.pk).update(
            state=ElectronicTaxDocument.State.SEND_UNCERTAIN,
            folio=124,
        )
        document.refresh_from_db()
        task = ElectronicTaxStatusCheckTask.objects.create(
            company=self.company,
            branch=self.branch,
            document=document,
            actor=self.user,
            reason="TEST",
            due_at=timezone.now() - timedelta(minutes=1),
        )
        provider = FakeElectronicTaxProvider(refresh_state=ElectronicTaxDocument.State.ACCEPTED)
        result = process_status_check_tasks(execute=True, provider=provider)
        task.refresh_from_db()
        document.refresh_from_db()
        self.assertEqual(result["succeeded"], 1)
        self.assertEqual(provider.refresh_calls, 1)
        self.assertEqual(provider.submit_calls, 0)
        self.assertEqual(task.state, ElectronicTaxStatusCheckTask.State.SUCCEEDED)
        self.assertEqual(document.state, ElectronicTaxDocument.State.ACCEPTED)

    def test_receiver_uncertain_is_alerted_without_automatic_mail_retry(self):
        document = self.accept_document(self.create_document(), folio=125)
        ElectronicTaxExchange.objects.create(
            document=document,
            delivery_state=ElectronicTaxExchange.DeliveryState.SEND_UNCERTAIN,
            recipient_email=document.receiver_tax_email,
            send_attempts=1,
        )
        old = timezone.now() - timedelta(hours=1)
        ElectronicTaxExchange.objects.filter(document=document).update(updated_at=old)
        with override_settings(ELECTRONIC_TAX_STALE_MINUTES=10, SII_ADAPTER_ENABLED=False):
            scan_company_operations(company=self.company)
        self.assertTrue(
            ElectronicTaxOperationalAlert.objects.filter(
                company=self.company,
                code="RECEIVER_EXCHANGE_UNCERTAIN",
                status=ElectronicTaxOperationalAlert.Status.OPEN,
            ).exists()
        )
        self.assertFalse(ElectronicTaxStatusCheckTask.objects.filter(document=document).exists())

    def test_integrity_snapshot_and_summary_do_not_expose_payloads(self):
        document = self.create_document()
        summary = operational_summary(company=self.company)
        snapshot = integrity_snapshot(company=self.company)
        self.assertEqual(summary["company_id"], self.company.id)
        self.assertIn(summary["database"]["vendor"], {"sqlite", "mysql"})
        self.assertEqual(snapshot["documents"], 1)
        self.assertEqual(snapshot["problems"], [])
        serialized = str({"summary": summary, "snapshot": snapshot})
        self.assertNotIn("encrypted_caf", serialized)
        self.assertNotIn("encrypted_payload", serialized)
        self.assertNotIn("password", serialized.lower())


class ElectronicTaxOperationsApiTests(ElectronicTaxFixtureMixin, APITestCase):
    def setUp(self):
        super().setUp()
        self.client.force_authenticate(self.user)

    def test_operations_summary_is_company_scoped(self):
        self.create_document()
        response = self.client.get(
            "/api/v1/electronic-tax-operations/summary/",
            {"company": self.company.id},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["operations"]["company_id"], self.company.id)
        self.assertEqual(response.data["operations"]["documents_by_state"]["DRAFT"], 1)

    def test_operations_alerts_requires_company_access(self):
        response = self.client.get(
            "/api/v1/electronic-tax-operations/alerts/",
            {"company": 999999},
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data["code"], "DTE_PERMISSION_DENIED")
