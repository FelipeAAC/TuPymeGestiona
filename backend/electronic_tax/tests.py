from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APITestCase

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
from sales.models import Sale

from .models import (
    ElectronicTaxDocument,
    ElectronicTaxEvent,
    ElectronicTaxReference,
    FolioAuthorization,
    FolioReservation,
    TaxCompanyProfile,
    TaxCustomerProfile,
    TaxProductProfile,
)
from .services import (
    DTEAlreadyExistsError,
    DTECommercialAdjustmentRequiredError,
    DTEIdempotencyConflictError,
    DTEProviderNotConfiguredError,
    DTERefundRequiredError,
    DTEValidationError,
    FakeElectronicTaxProvider,
    create_base_document,
    create_credit_note,
    create_debit_note,
    discard_document,
    issue_document,
    normalize_rut,
    record_event,
    refresh_document_status,
    reserve_folio,
    validate_document,
)


DOCUMENT_PERMISSIONS = (
    "electronic_tax_document.view",
    "electronic_tax_document.create",
    "electronic_tax_document.validate",
    "electronic_tax_document.issue",
    "electronic_tax_document.adjust",
)


class ElectronicTaxFixtureMixin:
    def setUp(self):
        super().setUp()
        User = get_user_model()
        self.user = User.objects.create_user(
            username="tax-user",
            email="tax@example.com",
            password="secret123",
        )
        self.company = Company.objects.create(name="Empresa Uno")
        self.branch = Branch.objects.create(company=self.company, code="SCL", name="Santiago")
        self.warehouse = Warehouse.objects.create(
            company=self.company,
            branch=self.branch,
            code="B1",
            name="Bodega Uno",
        )
        self.membership = CompanyMembership.objects.create(
            user=self.user,
            company=self.company,
            status=CompanyMembership.Status.ACTIVE,
        )
        MembershipBranch.objects.create(membership=self.membership, branch=self.branch)
        self.role = CompanyRole.objects.create(
            company=self.company,
            name="Facturacion",
            status=CompanyRole.Status.ACTIVE,
        )
        RoleAssignment.objects.create(
            membership=self.membership,
            role=self.role,
            branch=self.branch,
        )
        for code in DOCUMENT_PERMISSIONS:
            permission = Permission.objects.get(code=code)
            CompanyRolePermission.objects.create(role=self.role, permission=permission)

        self.folio_role = CompanyRole.objects.create(
            company=self.company,
            name="Tributario",
            status=CompanyRole.Status.ACTIVE,
        )
        folio_permission = Permission.objects.get(code="electronic_tax_folio.manage")
        CompanyRolePermission.objects.create(role=self.folio_role, permission=folio_permission)
        RoleAssignment.objects.create(
            membership=self.membership,
            role=self.folio_role,
            branch=None,
        )

        self.customer = Customer.objects.create(
            company=self.company,
            code="C1",
            name="Cliente Uno",
            tax_id="12345678-5",
            email="cliente@example.com",
        )
        self.category = Category.objects.create(company=self.company, name="General")
        self.product = Product.objects.create(
            company=self.company,
            category=self.category,
            name="Producto A",
            status=Product.Status.ACTIVE,
        )
        self.variant = ProductVariant.objects.create(
            product=self.product,
            sku="SKU-A",
            base_price=Decimal("1190.00"),
            status=ProductVariant.Status.ACTIVE,
        )
        self.order = Order.objects.create(
            company=self.company,
            branch=self.branch,
            warehouse=self.warehouse,
            customer=self.customer,
            number=1,
            status=Order.Status.DELIVERED,
            created_by=self.user,
        )
        OrderItem.objects.create(
            order=self.order,
            variant=self.variant,
            quantity=Decimal("1.000"),
            unit_price=Decimal("1190.00"),
        )
        self.sale = Sale.objects.create(
            company=self.company,
            branch=self.branch,
            order=self.order,
            number=1,
            status=Sale.Status.PENDING,
            total_amount=Decimal("1190.00"),
            paid_amount=Decimal("0.00"),
            idempotency_key="sale-1",
            created_by=self.user,
        )
        TaxCompanyProfile.objects.create(
            company=self.company,
            rut="76123456-0",
            legal_name="Empresa Uno SpA",
            business_activity="Servicios informaticos",
            address="Av. Uno 123",
            commune="Santiago",
            city="Santiago",
            tax_email="tributario@empresa.cl",
        )
        TaxCustomerProfile.objects.create(
            customer=self.customer,
            rut="12345678-5",
            legal_name="Cliente Uno Ltda",
            business_activity="Comercio",
            address="Calle Dos 456",
            commune="Providencia",
            city="Santiago",
            tax_email="tributario@cliente.cl",
        )
        TaxProductProfile.objects.create(
            variant=self.variant,
            tax_category=TaxProductProfile.TaxCategory.AFFECTED,
        )

    def create_document(self, *, type_code=33, key="create-dte-1"):
        return create_base_document(
            company=self.company,
            sale=self.sale,
            type_code=type_code,
            idempotency_key=key,
            created_by=self.user,
        )[0]

    def accept_document(self, document, *, folio=100):
        ElectronicTaxDocument.objects.filter(pk=document.pk).update(
            state=ElectronicTaxDocument.State.ACCEPTED,
            folio=folio,
            issue_date=date(2026, 9, 3),
            version=document.version + 1,
        )
        document.refresh_from_db()
        return document

    def create_second_sale(self):
        product = Product.objects.create(
            company=self.company,
            category=self.category,
            name="Producto B",
            status=Product.Status.ACTIVE,
        )
        variant = ProductVariant.objects.create(
            product=product,
            sku="SKU-B",
            base_price=Decimal("2380.00"),
            status=ProductVariant.Status.ACTIVE,
        )
        TaxProductProfile.objects.create(
            variant=variant,
            tax_category=TaxProductProfile.TaxCategory.AFFECTED,
        )
        order = Order.objects.create(
            company=self.company,
            branch=self.branch,
            warehouse=self.warehouse,
            customer=self.customer,
            number=2,
            status=Order.Status.DELIVERED,
            created_by=self.user,
        )
        OrderItem.objects.create(
            order=order,
            variant=variant,
            quantity=Decimal("1.000"),
            unit_price=Decimal("2380.00"),
        )
        return Sale.objects.create(
            company=self.company,
            branch=self.branch,
            order=order,
            number=2,
            status=Sale.Status.PENDING,
            total_amount=Decimal("2380.00"),
            paid_amount=Decimal("0.00"),
            idempotency_key="sale-2",
            created_by=self.user,
        )


class ElectronicTaxServiceTests(ElectronicTaxFixtureMixin, TestCase):
    def test_permissions_are_seeded_with_expected_scope(self):
        for code in DOCUMENT_PERMISSIONS:
            self.assertEqual(
                Permission.objects.get(code=code).scope_behavior,
                Permission.ScopeBehavior.BRANCH_SCOPED,
            )
        self.assertEqual(
            Permission.objects.get(code="electronic_tax_folio.manage").scope_behavior,
            Permission.ScopeBehavior.COMPANY_ONLY,
        )

    def test_normalize_rut_validates_modulo_11(self):
        self.assertEqual(normalize_rut("76.123.456-0"), "76123456-0")
        with self.assertRaises(DTEValidationError):
            normalize_rut("76.123.456-9")

    def test_create_dte_33_calculates_server_totals_and_snapshot(self):
        document, created = create_base_document(
            company=self.company,
            sale=self.sale,
            type_code=33,
            idempotency_key="dte-33",
            created_by=self.user,
        )
        self.assertTrue(created)
        self.assertEqual(document.net_amount, 1000)
        self.assertEqual(document.vat_amount, 190)
        self.assertEqual(document.exempt_amount, 0)
        self.assertEqual(document.total_amount, 1190)
        self.assertEqual(document.receiver_rut, "12345678-5")
        self.assertEqual(document.lines.count(), 1)
        self.assertEqual(document.events.get().event_type, ElectronicTaxEvent.EventType.DRAFT_CREATED)
        self.assertEqual(len(document.snapshot_hash), 64)

    def test_snapshot_does_not_change_when_customer_profile_changes(self):
        document = self.create_document()
        profile = TaxCustomerProfile.objects.get(customer=self.customer)
        profile.legal_name = "Cliente Cambiado"
        profile.address = "Otra direccion"
        profile.save()
        document.refresh_from_db()
        self.assertEqual(document.receiver_legal_name, "Cliente Uno Ltda")
        self.assertEqual(document.receiver_address, "Calle Dos 456")

    def test_create_dte_34_requires_all_lines_exempt(self):
        profile = TaxProductProfile.objects.get(variant=self.variant)
        profile.tax_category = TaxProductProfile.TaxCategory.EXEMPT
        profile.save()
        document = self.create_document(type_code=34)
        self.assertEqual(document.net_amount, 0)
        self.assertEqual(document.vat_amount, 0)
        self.assertEqual(document.exempt_amount, 1190)
        self.assertEqual(document.total_amount, 1190)

    def test_dte_34_rejects_affected_line(self):
        with self.assertRaises(DTEValidationError):
            self.create_document(type_code=34)

    def test_dte_33_requires_affected_line(self):
        profile = TaxProductProfile.objects.get(variant=self.variant)
        profile.tax_category = TaxProductProfile.TaxCategory.EXEMPT
        profile.save()
        with self.assertRaises(DTEValidationError):
            self.create_document(type_code=33)

    def test_cancelled_sale_is_not_eligible(self):
        Sale.objects.filter(pk=self.sale.pk).update(
            status=Sale.Status.CANCELLED,
            cancelled_by=self.user,
            cancelled_at="2026-09-03T12:00:00Z",
        )
        self.sale.refresh_from_db()
        with self.assertRaises(DTEValidationError):
            self.create_document()

    def test_missing_receiver_profile_is_rejected(self):
        TaxCustomerProfile.objects.filter(customer=self.customer).delete()
        with self.assertRaises(DTEValidationError):
            self.create_document()

    def test_same_create_idempotency_key_replays_original(self):
        first, first_created = create_base_document(
            company=self.company,
            sale=self.sale,
            type_code=33,
            idempotency_key="same-key",
            created_by=self.user,
        )
        second, second_created = create_base_document(
            company=self.company,
            sale=self.sale,
            type_code=33,
            idempotency_key="same-key",
            created_by=self.user,
        )
        self.assertTrue(first_created)
        self.assertFalse(second_created)
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(ElectronicTaxDocument.objects.count(), 1)

    def test_idempotency_key_reuse_with_different_payload_conflicts(self):
        self.create_document(key="shared-key")
        second_sale = self.create_second_sale()
        with self.assertRaises(DTEIdempotencyConflictError):
            create_base_document(
                company=self.company,
                sale=second_sale,
                type_code=33,
                idempotency_key="shared-key",
                created_by=self.user,
            )

    def test_second_active_base_document_is_rejected(self):
        self.create_document(key="first")
        with self.assertRaises(DTEAlreadyExistsError):
            self.create_document(key="second")

    def test_validate_freezes_document_in_ready_and_increments_version(self):
        document = self.create_document()
        document, changed = validate_document(
            document=document,
            expected_version=1,
            idempotency_key="validate-1",
            actor=self.user,
        )
        self.assertTrue(changed)
        self.assertEqual(document.state, ElectronicTaxDocument.State.READY)
        self.assertEqual(document.version, 2)
        self.assertTrue(document.events.filter(event_type=ElectronicTaxEvent.EventType.VALIDATED).exists())

    def test_validate_idempotency_replays_after_state_change(self):
        document = self.create_document()
        first, changed = validate_document(
            document=document,
            expected_version=1,
            idempotency_key="validate-repeat",
            actor=self.user,
        )
        second, changed_again = validate_document(
            document=first,
            expected_version=1,
            idempotency_key="validate-repeat",
            actor=self.user,
        )
        self.assertTrue(changed)
        self.assertFalse(changed_again)
        self.assertEqual(second.pk, first.pk)

    def test_discard_is_logical_and_releases_active_base_constraint(self):
        document = self.create_document()
        discarded, changed = discard_document(
            document=document,
            expected_version=1,
            idempotency_key="discard-1",
            actor=self.user,
        )
        self.assertTrue(changed)
        self.assertEqual(discarded.state, ElectronicTaxDocument.State.DISCARDED)
        self.assertFalse(discarded.is_active_base)
        self.assertIsNotNone(discarded.discarded_at)
        replacement = self.create_document(key="replacement")
        self.assertNotEqual(replacement.pk, document.pk)

    def test_issue_without_provider_never_reserves_folio_or_changes_state(self):
        document = self.create_document()
        document = validate_document(
            document=document,
            expected_version=1,
            idempotency_key="validate-before-issue",
            actor=self.user,
        )[0]
        FolioAuthorization.objects.create(
            company=self.company,
            type_code=33,
            start_folio=1,
            end_folio=10,
            next_folio=1,
        )
        with self.assertRaises(DTEProviderNotConfiguredError):
            issue_document(
                document=document,
                expected_version=document.version,
                idempotency_key="issue-1",
                actor=self.user,
            )
        document.refresh_from_db()
        self.assertEqual(document.state, ElectronicTaxDocument.State.READY)
        self.assertIsNone(document.folio)
        self.assertFalse(FolioReservation.objects.exists())

    def test_reserve_folio_is_unique_and_exhausts_range(self):
        first = validate_document(
            document=self.create_document(),
            expected_version=1,
            idempotency_key="validate-first",
            actor=self.user,
        )[0]
        second_sale = self.create_second_sale()
        second = create_base_document(
            company=self.company,
            sale=second_sale,
            type_code=33,
            idempotency_key="second-dte",
            created_by=self.user,
        )[0]
        second = validate_document(
            document=second,
            expected_version=1,
            idempotency_key="validate-second",
            actor=self.user,
        )[0]
        authorization = FolioAuthorization.objects.create(
            company=self.company,
            type_code=33,
            start_folio=10,
            end_folio=11,
            next_folio=10,
        )
        first_reservation, _ = reserve_folio(document=first, actor=self.user)
        second_reservation, _ = reserve_folio(document=second, actor=self.user)
        self.assertEqual(first_reservation.folio, 10)
        self.assertEqual(second_reservation.folio, 11)
        authorization.refresh_from_db()
        self.assertEqual(authorization.status, FolioAuthorization.Status.EXHAUSTED)
        self.assertEqual(authorization.next_folio, 12)

    def test_fake_provider_issues_without_network_and_tracks_state_machine(self):
        document = validate_document(
            document=self.create_document(),
            expected_version=1,
            idempotency_key="validate-fake-issue",
            actor=self.user,
        )[0]
        FolioAuthorization.objects.create(
            company=self.company,
            type_code=33,
            start_folio=70,
            end_folio=80,
            next_folio=70,
        )
        provider = FakeElectronicTaxProvider(track_id="TRACK-70")
        issued, changed = issue_document(
            document=document,
            expected_version=document.version,
            idempotency_key="fake-issue",
            actor=self.user,
            provider=provider,
        )
        self.assertTrue(changed)
        self.assertEqual(issued.state, ElectronicTaxDocument.State.SUBMITTED)
        self.assertEqual(issued.folio, 70)
        self.assertEqual(issued.provider_track_id, "TRACK-70")
        self.assertEqual(provider.sign_calls, 1)
        self.assertEqual(provider.submit_calls, 1)
        event_types = list(issued.events.values_list("event_type", flat=True))
        self.assertIn(ElectronicTaxEvent.EventType.FOLIO_RESERVED, event_types)
        self.assertIn(ElectronicTaxEvent.EventType.SIGNED, event_types)
        self.assertIn(ElectronicTaxEvent.EventType.SUBMITTED, event_types)

    def test_fake_timeout_moves_to_send_uncertain_and_refresh_queries_before_retry(self):
        document = validate_document(
            document=self.create_document(),
            expected_version=1,
            idempotency_key="validate-uncertain",
            actor=self.user,
        )[0]
        FolioAuthorization.objects.create(
            company=self.company,
            type_code=33,
            start_folio=90,
            end_folio=100,
            next_folio=90,
        )
        provider = FakeElectronicTaxProvider(send_uncertain=True)
        uncertain, _ = issue_document(
            document=document,
            expected_version=document.version,
            idempotency_key="fake-uncertain",
            actor=self.user,
            provider=provider,
        )
        self.assertEqual(uncertain.state, ElectronicTaxDocument.State.SEND_UNCERTAIN)
        self.assertEqual(len(uncertain.xml_hash), 64)
        self.assertEqual(provider.submit_calls, 1)

        query_provider = FakeElectronicTaxProvider(
            refresh_state=ElectronicTaxDocument.State.ACCEPTED,
            refresh_code="ACEPTADO",
        )
        refreshed, changed = refresh_document_status(
            document=uncertain,
            expected_version=uncertain.version,
            idempotency_key="refresh-uncertain",
            actor=self.user,
            provider=query_provider,
        )
        self.assertTrue(changed)
        self.assertEqual(refreshed.state, ElectronicTaxDocument.State.ACCEPTED)
        self.assertEqual(query_provider.refresh_calls, 1)
        self.assertEqual(provider.submit_calls, 1)

    def test_accepted_cancellation_note_marks_origin_cancelled_by_reference(self):
        source = self.accept_document(self.create_document(), folio=106)
        note, _ = create_credit_note(
            source_document=source,
            reason=ElectronicTaxReference.Reason.CANCEL_DOCUMENT,
            description="Anula factura",
            correction={},
            expected_version=source.version,
            idempotency_key="nc-provider-effect",
            actor=self.user,
        )
        note = validate_document(
            document=note,
            expected_version=1,
            idempotency_key="validate-nc-provider-effect",
            actor=self.user,
        )[0]
        FolioAuthorization.objects.create(
            company=self.company,
            type_code=61,
            start_folio=300,
            end_folio=310,
            next_folio=300,
        )
        issue_provider = FakeElectronicTaxProvider(track_id="TRACK-NC")
        note, _ = issue_document(
            document=note,
            expected_version=note.version,
            idempotency_key="issue-nc-provider-effect",
            actor=self.user,
            provider=issue_provider,
        )
        refresh_provider = FakeElectronicTaxProvider(
            refresh_state=ElectronicTaxDocument.State.ACCEPTED
        )
        note, _ = refresh_document_status(
            document=note,
            expected_version=note.version,
            idempotency_key="refresh-nc-provider-effect",
            actor=self.user,
            provider=refresh_provider,
        )
        source.refresh_from_db()
        self.assertEqual(note.state, ElectronicTaxDocument.State.ACCEPTED)
        self.assertEqual(source.state, ElectronicTaxDocument.State.CANCELLED_BY_REFERENCE)
        self.assertFalse(source.is_active_base)

    def test_fiscal_fields_are_immutable_after_folio_reserved(self):
        document = validate_document(
            document=self.create_document(),
            expected_version=1,
            idempotency_key="validate-lock",
            actor=self.user,
        )[0]
        FolioAuthorization.objects.create(
            company=self.company,
            type_code=33,
            start_folio=50,
            end_folio=60,
            next_folio=50,
        )
        reserve_folio(document=document, actor=self.user)
        document.refresh_from_db()
        document.receiver_legal_name = "Cambio ilegal"
        with self.assertRaises(ValidationError):
            document.save()

    def test_credit_note_cancels_accepted_invoice_with_no_payments(self):
        source = self.accept_document(self.create_document(), folio=101)
        note, created = create_credit_note(
            source_document=source,
            reason=ElectronicTaxReference.Reason.CANCEL_DOCUMENT,
            description="Anulacion total",
            correction={},
            expected_version=source.version,
            idempotency_key="nc-cancel",
            actor=self.user,
        )
        self.assertTrue(created)
        self.assertEqual(note.type_code, ElectronicTaxDocument.TypeCode.CREDIT_NOTE)
        self.assertEqual(note.total_amount, source.total_amount)
        reference = note.references.get()
        self.assertEqual(reference.referenced_document, source)
        self.assertEqual(reference.referenced_folio, 101)

    def test_credit_note_total_cancellation_rejects_paid_sale(self):
        source = self.accept_document(self.create_document(), folio=102)
        Sale.objects.filter(pk=self.sale.pk).update(
            status=Sale.Status.PARTIAL,
            paid_amount=Decimal("100.00"),
        )
        source.sale.refresh_from_db()
        with self.assertRaises(DTERefundRequiredError):
            create_credit_note(
                source_document=source,
                reason=ElectronicTaxReference.Reason.CANCEL_DOCUMENT,
                description="Anulacion",
                correction={},
                expected_version=source.version,
                idempotency_key="nc-paid",
                actor=self.user,
            )

    def test_correct_amounts_is_reserved_for_later_slice(self):
        source = self.accept_document(self.create_document(), folio=103)
        with self.assertRaises(DTECommercialAdjustmentRequiredError):
            create_credit_note(
                source_document=source,
                reason=ElectronicTaxReference.Reason.CORRECT_AMOUNTS,
                description="Ajuste",
                correction={},
                expected_version=source.version,
                idempotency_key="nc-amounts",
                actor=self.user,
            )

    def test_correct_text_creates_zero_amount_credit_note_with_corrected_snapshot(self):
        source = self.accept_document(self.create_document(), folio=104)
        note, _ = create_credit_note(
            source_document=source,
            reason=ElectronicTaxReference.Reason.CORRECT_TEXT,
            description="Corrige direccion",
            correction={"receiver_address": "Nueva 999"},
            expected_version=source.version,
            idempotency_key="nc-text",
            actor=self.user,
        )
        self.assertEqual(note.total_amount, 0)
        self.assertEqual(note.receiver_address, "Nueva 999")
        self.assertEqual(note.lines.count(), 0)

    def test_debit_note_only_cancels_accepted_credit_note(self):
        source = self.accept_document(self.create_document(), folio=105)
        credit, _ = create_credit_note(
            source_document=source,
            reason=ElectronicTaxReference.Reason.CANCEL_DOCUMENT,
            description="Anula factura",
            correction={},
            expected_version=source.version,
            idempotency_key="nc-for-nd",
            actor=self.user,
        )
        credit = self.accept_document(credit, folio=205)
        debit, created = create_debit_note(
            source_document=credit,
            reason=ElectronicTaxReference.Reason.CANCEL_CREDIT_NOTE,
            description="Anula NC",
            expected_version=credit.version,
            idempotency_key="nd-cancel-nc",
            actor=self.user,
        )
        self.assertTrue(created)
        self.assertEqual(debit.type_code, ElectronicTaxDocument.TypeCode.DEBIT_NOTE)
        self.assertEqual(debit.references.get().referenced_document, credit)

    def test_audit_metadata_drops_sensitive_fields(self):
        document = self.create_document()
        event = record_event(
            document=document,
            event_type=ElectronicTaxEvent.EventType.SECRET_OPERATION,
            actor=self.user,
            metadata={"token": "abc", "xml": "<xml/>", "safe": "ok"},
        )
        self.assertEqual(event.metadata, {"safe": "ok"})


class ElectronicTaxApiTests(ElectronicTaxFixtureMixin, APITestCase):
    def setUp(self):
        super().setUp()
        self.client.force_authenticate(self.user)

    def post_create(self, *, key="api-create", sale=None, type_code=33):
        sale = sale or self.sale
        return self.client.post(
            "/api/v1/electronic-tax-documents/",
            {"company": self.company.id, "sale_id": sale.id, "type_code": type_code},
            format="json",
            HTTP_IDEMPOTENCY_KEY=key,
        )

    def test_create_requires_idempotency_header(self):
        response = self.client.post(
            "/api/v1/electronic-tax-documents/",
            {"company": self.company.id, "sale_id": self.sale.id, "type_code": 33},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["code"], "DTE_VALIDATION_ERROR")

    def test_create_and_detail_api(self):
        response = self.post_create()
        self.assertEqual(response.status_code, 201)
        document_id = response.data["document"]["id"]
        detail = self.client.get(
            f"/api/v1/electronic-tax-documents/{document_id}/",
            {"company": self.company.id},
        )
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.data["document"]["total_amount"], 1190)
        self.assertEqual(len(detail.data["document"]["events"]), 1)

    def test_cross_tenant_document_behaves_as_not_found(self):
        document = self.create_document()
        foreign = Company.objects.create(name="Otra Empresa")
        foreign_membership = CompanyMembership.objects.create(
            user=self.user,
            company=foreign,
            status=CompanyMembership.Status.ACTIVE,
        )
        response = self.client.get(
            f"/api/v1/electronic-tax-documents/{document.id}/",
            {"company": foreign.id},
        )
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data["code"], "DTE_NOT_FOUND")
        self.assertIsNotNone(foreign_membership.pk)

    def test_missing_action_permission_returns_403(self):
        response = self.post_create()
        document_id = response.data["document"]["id"]
        permission = Permission.objects.get(code="electronic_tax_document.validate")
        CompanyRolePermission.objects.filter(role=self.role, permission=permission).delete()
        validate_response = self.client.post(
            f"/api/v1/electronic-tax-documents/{document_id}/validate/",
            {"company": self.company.id, "version": 1},
            format="json",
            HTTP_IDEMPOTENCY_KEY="validate-api",
        )
        self.assertEqual(validate_response.status_code, 403)
        self.assertEqual(validate_response.data["code"], "DTE_PERMISSION_DENIED")

    def test_version_conflict_is_audited(self):
        response = self.post_create()
        document_id = response.data["document"]["id"]
        validate_response = self.client.post(
            f"/api/v1/electronic-tax-documents/{document_id}/validate/",
            {"company": self.company.id, "version": 99},
            format="json",
            HTTP_IDEMPOTENCY_KEY="version-conflict",
        )
        self.assertEqual(validate_response.status_code, 409)
        self.assertEqual(validate_response.data["code"], "DTE_VERSION_CONFLICT")
        self.assertTrue(
            ElectronicTaxEvent.objects.filter(
                document_id=document_id,
                event_type=ElectronicTaxEvent.EventType.VERSION_CONFLICT,
            ).exists()
        )

    def test_issue_without_provider_returns_stable_error_and_does_not_reserve(self):
        create = self.post_create()
        document_id = create.data["document"]["id"]
        validate = self.client.post(
            f"/api/v1/electronic-tax-documents/{document_id}/validate/",
            {"company": self.company.id, "version": 1},
            format="json",
            HTTP_IDEMPOTENCY_KEY="api-validate",
        )
        self.assertEqual(validate.status_code, 200)
        FolioAuthorization.objects.create(
            company=self.company,
            type_code=33,
            start_folio=1,
            end_folio=10,
            next_folio=1,
        )
        issue = self.client.post(
            f"/api/v1/electronic-tax-documents/{document_id}/issue/",
            {"company": self.company.id, "version": 2},
            format="json",
            HTTP_IDEMPOTENCY_KEY="api-issue",
        )
        self.assertEqual(issue.status_code, 409)
        self.assertEqual(issue.data["code"], "PROVIDER_NOT_CONFIGURED")
        document = ElectronicTaxDocument.objects.get(pk=document_id)
        self.assertEqual(document.state, ElectronicTaxDocument.State.READY)
        self.assertIsNone(document.folio)
        self.assertFalse(FolioReservation.objects.exists())

    def test_folio_summary_never_exposes_caf_material(self):
        FolioAuthorization.objects.create(
            company=self.company,
            type_code=33,
            start_folio=1,
            end_folio=5,
            next_folio=2,
            caf_hash="do-not-expose",
        )
        response = self.client.get(
            "/api/v1/folio-authorizations/summary/",
            {"company": self.company.id},
        )
        self.assertEqual(response.status_code, 200)
        item = response.data["authorizations"][0]
        self.assertEqual(item["available"], 4)
        self.assertNotIn("caf_hash", item)
