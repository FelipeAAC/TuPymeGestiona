import hashlib
import json
from decimal import Decimal, ROUND_HALF_UP

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from orders.models import Order
from organizations.models import Company
from sales.models import Sale

from .models import (
    ElectronicTaxDocument,
    ElectronicTaxEvent,
    ElectronicTaxLine,
    ElectronicTaxReference,
    FolioAuthorization,
    FolioReservation,
    IdempotencyRecord,
    TaxCompanyProfile,
    TaxCustomerProfile,
    TaxProductProfile,
)


DEFAULT_VAT_RATE = Decimal("19.00")


class DTEError(Exception):
    code = "DTE_ERROR"

    def __init__(self, detail, *, code=None):
        self.detail = detail
        if code is not None:
            self.code = code
        super().__init__(detail)


class DTEValidationError(DTEError):
    code = "DTE_VALIDATION_ERROR"


class DTEAlreadyExistsError(DTEError):
    code = "DTE_ALREADY_EXISTS"


class DTEInvalidStateError(DTEError):
    code = "DTE_INVALID_STATE"


class DTEVersionConflictError(DTEError):
    code = "DTE_VERSION_CONFLICT"


class DTEIdempotencyConflictError(DTEError):
    code = "IDEMPOTENCY_KEY_REUSED"


class DTERefundRequiredError(DTEError):
    code = "REFUND_REQUIRED"


class DTEProviderNotConfiguredError(DTEError):
    code = "PROVIDER_NOT_CONFIGURED"


class DTECommercialAdjustmentRequiredError(DTEError):
    code = "COMMERCIAL_ADJUSTMENT_REQUIRED"


class DTEFolioUnavailableError(DTEError):
    code = "FOLIO_UNAVAILABLE"


class ElectronicTaxProviderPort:
    """Puerto desacoplado; la implementacion real SII pertenece al slice posterior."""

    configured = False

    def sign(self, *, document):
        raise NotImplementedError

    def submit(self, *, document):
        raise NotImplementedError

    def refresh_status(self, *, document):
        raise NotImplementedError


class ProviderSendUncertain(Exception):
    pass


class NotConfiguredTaxProvider(ElectronicTaxProviderPort):
    configured = False


class FakeElectronicTaxProvider(ElectronicTaxProviderPort):
    """Fake local determinista para pruebas; nunca realiza red ni accede a secretos."""

    configured = True

    def __init__(
        self,
        *,
        track_id="FAKE-TRACK-1",
        xml_hash="f" * 64,
        send_uncertain=False,
        refresh_state=ElectronicTaxDocument.State.ACCEPTED,
        refresh_code="FAKE_ACCEPTED",
        refresh_message="Aceptado por fake local",
    ):
        self.track_id = track_id
        self.xml_hash = xml_hash
        self.send_uncertain = send_uncertain
        self.refresh_state = refresh_state
        self.refresh_code = refresh_code
        self.refresh_message = refresh_message
        self.sign_calls = 0
        self.submit_calls = 0
        self.refresh_calls = 0

    def sign(self, *, document):
        self.sign_calls += 1
        return {"xml_hash": self.xml_hash}

    def submit(self, *, document):
        self.submit_calls += 1
        if self.send_uncertain:
            raise ProviderSendUncertain("Resultado remoto desconocido despues del envio simulado.")
        return {"track_id": self.track_id}

    def refresh_status(self, *, document):
        self.refresh_calls += 1
        return {
            "state": self.refresh_state,
            "code": self.refresh_code,
            "message": self.refresh_message,
        }


DEFAULT_PROVIDER = NotConfiguredTaxProvider()


SENSITIVE_METADATA_KEYS = (
    "password",
    "secret",
    "token",
    "private_key",
    "xml",
    "caf",
    "certificate",
)


def normalize_rut(value):
    raw = (value or "").strip().upper().replace(".", "").replace("-", "")
    if len(raw) < 2:
        raise DTEValidationError("El RUT es obligatorio y debe ser valido.")
    body, verifier = raw[:-1], raw[-1]
    if not body.isdigit() or verifier not in "0123456789K":
        raise DTEValidationError("El RUT es invalido.")

    factor = 2
    total = 0
    for digit in reversed(body):
        total += int(digit) * factor
        factor = 2 if factor == 7 else factor + 1
    remainder = 11 - (total % 11)
    expected = "0" if remainder == 11 else "K" if remainder == 10 else str(remainder)
    if verifier != expected:
        raise DTEValidationError("El RUT es invalido.")
    return f"{int(body)}-{verifier}"


def _canonical_hash(payload):
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _safe_metadata(metadata):
    clean = {}
    for key, value in (metadata or {}).items():
        lowered = str(key).casefold()
        if any(secret in lowered for secret in SENSITIVE_METADATA_KEYS):
            continue
        if isinstance(value, (str, int, float, bool)) or value is None:
            clean[str(key)] = value
    return clean


def record_event(*, document, event_type, actor, correlation_id=None, code="", metadata=None):
    return ElectronicTaxEvent.objects.create(
        document=document,
        company=document.company,
        branch=document.branch,
        event_type=event_type,
        actor=actor,
        correlation_id=correlation_id or document.correlation_id,
        normalized_code=code,
        metadata=_safe_metadata(metadata),
    )


def record_version_conflict(*, document, actor, expected_version):
    return record_event(
        document=document,
        event_type=ElectronicTaxEvent.EventType.VERSION_CONFLICT,
        actor=actor,
        code=DTEVersionConflictError.code,
        metadata={"expected_version": expected_version, "current_version": document.version},
    )


def _check_version(document, expected_version):
    if expected_version != document.version:
        raise DTEVersionConflictError(
            f"Version obsoleta: se esperaba {expected_version} y el DTE esta en version {document.version}."
        )


def _replay_or_conflict(*, company, operation, key, payload_hash):
    normalized_key = (key or "").strip()
    if not normalized_key:
        raise DTEValidationError("Idempotency-Key es obligatorio.")
    existing = IdempotencyRecord.objects.filter(
        company=company,
        operation=operation,
        key=normalized_key,
    ).select_related("document").first()
    if existing is None:
        return normalized_key, None
    if existing.request_hash != payload_hash:
        raise DTEIdempotencyConflictError(
            "La misma clave de idempotencia fue usada con una solicitud diferente."
        )
    return normalized_key, existing


def _store_idempotency(*, company, operation, key, payload_hash, document, status_code=200):
    try:
        return IdempotencyRecord.objects.create(
            company=company,
            operation=operation,
            key=key,
            request_hash=payload_hash,
            document=document,
            response_status=status_code,
            response_body={"document_id": document.id},
        )
    except IntegrityError:
        existing = IdempotencyRecord.objects.get(company=company, operation=operation, key=key)
        if existing.request_hash != payload_hash:
            raise DTEIdempotencyConflictError(
                "La misma clave de idempotencia fue usada con una solicitud diferente."
            )
        return existing


def _require_profile_fields(profile, *, party_name):
    required = (
        "rut",
        "legal_name",
        "business_activity",
        "address",
        "commune",
    )
    missing = [field for field in required if not str(getattr(profile, field, "") or "").strip()]
    if missing:
        raise DTEValidationError(
            f"El perfil tributario de {party_name} esta incompleto: {', '.join(missing)}."
        )
    if not profile.active:
        raise DTEValidationError(f"El perfil tributario de {party_name} no esta activo.")
    return normalize_rut(profile.rut)


def _load_tax_profiles(*, sale):
    company_profile = TaxCompanyProfile.objects.filter(company=sale.company).first()
    if company_profile is None:
        raise DTEValidationError("La empresa no tiene perfil tributario configurado.")
    customer_profile = TaxCustomerProfile.objects.filter(customer=sale.order.customer).first()
    if customer_profile is None:
        raise DTEValidationError("El receptor no tiene perfil tributario configurado.")
    issuer_rut = _require_profile_fields(company_profile, party_name="la empresa emisora")
    receiver_rut = _require_profile_fields(customer_profile, party_name="el receptor")
    return company_profile, customer_profile, issuer_rut, receiver_rut


def _round_clp(value):
    return int(Decimal(value).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _calculate_sale_lines(*, sale, type_code, vat_rate=DEFAULT_VAT_RATE):
    items = list(
        sale.order.items.select_related("variant__product").order_by("id")
    )
    if not items:
        raise DTEValidationError("La venta no contiene lineas facturables.")

    variant_ids = [item.variant_id for item in items]
    tax_profiles = {
        profile.variant_id: profile
        for profile in TaxProductProfile.objects.filter(variant_id__in=variant_ids)
    }
    missing = [item.variant.sku for item in items if item.variant_id not in tax_profiles]
    if missing:
        raise DTEValidationError(
            "Falta clasificacion tributaria para las variantes: " + ", ".join(missing)
        )
    inactive = [item.variant.sku for item in items if not tax_profiles[item.variant_id].active]
    if inactive:
        raise DTEValidationError(
            "La clasificacion tributaria esta inactiva para: " + ", ".join(inactive)
        )

    rows = []
    affected_count = 0
    totals = {"net": 0, "exempt": 0, "vat": 0, "total": 0}
    rate_factor = Decimal("1") + (vat_rate / Decimal("100"))

    for line_number, item in enumerate(items, start=1):
        profile = tax_profiles[item.variant_id]
        line_total = _round_clp(item.quantity * item.unit_price)
        if profile.tax_category == TaxProductProfile.TaxCategory.AFFECTED:
            affected_count += 1
            if type_code == ElectronicTaxDocument.TypeCode.EXEMPT_INVOICE:
                raise DTEValidationError("El DTE 34 solo admite lineas exentas/no gravadas.")
            net_amount = _round_clp(Decimal(line_total) / rate_factor)
            vat_amount = line_total - net_amount
            exempt_amount = 0
        else:
            net_amount = 0
            vat_amount = 0
            exempt_amount = line_total

        totals["net"] += net_amount
        totals["exempt"] += exempt_amount
        totals["vat"] += vat_amount
        totals["total"] += line_total
        rows.append(
            {
                "line_number": line_number,
                "variant": item.variant,
                "sku": item.variant.sku,
                "description": item.variant.product.name,
                "quantity": item.quantity,
                "unit_price": item.unit_price,
                "discount_amount": 0,
                "tax_category": profile.tax_category,
                "net_amount": net_amount,
                "exempt_amount": exempt_amount,
                "vat_amount": vat_amount,
                "total_amount": line_total,
            }
        )

    if type_code == ElectronicTaxDocument.TypeCode.INVOICE and affected_count == 0:
        raise DTEValidationError("El DTE 33 exige al menos una linea afecta a IVA.")
    if type_code == ElectronicTaxDocument.TypeCode.EXEMPT_INVOICE and affected_count:
        raise DTEValidationError("El DTE 34 no puede contener lineas afectas a IVA.")

    sale_total = Decimal(sale.total_amount)
    if sale_total != sale_total.quantize(Decimal("1")):
        raise DTEValidationError("El total de la venta no es reproducible en pesos CLP enteros.")
    if totals["total"] != int(sale_total):
        raise DTEValidationError(
            "Los totales tributarios recalculados no coinciden con el total de la venta."
        )
    return rows, totals


def _snapshot_payload(*, sale, type_code, company_profile, customer_profile, issuer_rut, receiver_rut, rows, totals):
    return {
        "company_id": sale.company_id,
        "branch_id": sale.branch_id,
        "sale_id": sale.id,
        "type_code": int(type_code),
        "issuer": {
            "rut": issuer_rut,
            "legal_name": company_profile.legal_name.strip(),
            "business_activity": company_profile.business_activity.strip(),
            "address": company_profile.address.strip(),
            "commune": company_profile.commune.strip(),
            "city": company_profile.city.strip(),
            "tax_email": company_profile.tax_email.strip(),
        },
        "receiver": {
            "rut": receiver_rut,
            "legal_name": customer_profile.legal_name.strip(),
            "business_activity": customer_profile.business_activity.strip(),
            "address": customer_profile.address.strip(),
            "commune": customer_profile.commune.strip(),
            "city": customer_profile.city.strip(),
            "tax_email": customer_profile.tax_email.strip(),
        },
        "vat_rate": str(DEFAULT_VAT_RATE),
        "totals": totals,
        "currency": "CLP",
        "lines": [
            {
                key: (value.id if key == "variant" else str(value) if isinstance(value, Decimal) else value)
                for key, value in row.items()
            }
            for row in rows
        ],
    }


def _document_kwargs_from_snapshot(snapshot, *, idempotency_key, created_by):
    issuer = snapshot["issuer"]
    receiver = snapshot["receiver"]
    totals = snapshot["totals"]
    return {
        "company_id": snapshot["company_id"],
        "branch_id": snapshot["branch_id"],
        "sale_id": snapshot["sale_id"],
        "type_code": snapshot["type_code"],
        "state": ElectronicTaxDocument.State.DRAFT,
        "version": 1,
        "is_active_base": snapshot["type_code"] in (
            ElectronicTaxDocument.TypeCode.INVOICE,
            ElectronicTaxDocument.TypeCode.EXEMPT_INVOICE,
        ),
        "issuer_rut": issuer["rut"],
        "issuer_legal_name": issuer["legal_name"],
        "issuer_business_activity": issuer["business_activity"],
        "issuer_address": issuer["address"],
        "issuer_commune": issuer["commune"],
        "issuer_city": issuer["city"],
        "issuer_tax_email": issuer["tax_email"],
        "receiver_rut": receiver["rut"],
        "receiver_legal_name": receiver["legal_name"],
        "receiver_business_activity": receiver["business_activity"],
        "receiver_address": receiver["address"],
        "receiver_commune": receiver["commune"],
        "receiver_city": receiver["city"],
        "receiver_tax_email": receiver["tax_email"],
        "net_amount": totals["net"],
        "exempt_amount": totals["exempt"],
        "vat_rate": DEFAULT_VAT_RATE,
        "vat_amount": totals["vat"],
        "total_amount": totals["total"],
        "currency": "CLP",
        "snapshot_hash": _canonical_hash(snapshot),
        "creation_idempotency_key": idempotency_key,
        "created_by": created_by,
    }


@transaction.atomic
def create_base_document(*, company, sale, type_code, idempotency_key, created_by):
    if type_code not in (
        ElectronicTaxDocument.TypeCode.INVOICE,
        ElectronicTaxDocument.TypeCode.EXEMPT_INVOICE,
    ):
        raise DTEValidationError("La factura base solo admite DTE 33 o 34.")

    locked_company = Company.objects.select_for_update().get(pk=company.pk)
    try:
        locked_sale = (
            Sale.objects.select_for_update()
            .select_related("company", "branch", "order__customer")
            .get(pk=sale.pk, company=locked_company)
        )
    except Sale.DoesNotExist as error:
        raise DTEValidationError("La venta no pertenece a la empresa activa.") from error

    request_hash = _canonical_hash({"sale_id": locked_sale.id, "type_code": int(type_code)})
    key, replay = _replay_or_conflict(
        company=locked_company,
        operation="CREATE_BASE_DTE",
        key=idempotency_key,
        payload_hash=request_hash,
    )
    if replay is not None:
        return replay.document, False

    if locked_sale.status == Sale.Status.CANCELLED:
        raise DTEValidationError("Una venta CANCELLED no es elegible para facturacion.")
    if locked_sale.order.status != Order.Status.DELIVERED:
        raise DTEValidationError("La venta debe mantener un pedido entregado.")
    if ElectronicTaxDocument.objects.filter(
        company=locked_company,
        sale=locked_sale,
        is_active_base=True,
    ).exists():
        raise DTEAlreadyExistsError("Ya existe una factura base activa para la venta.")

    company_profile, customer_profile, issuer_rut, receiver_rut = _load_tax_profiles(sale=locked_sale)
    rows, totals = _calculate_sale_lines(sale=locked_sale, type_code=type_code)
    snapshot = _snapshot_payload(
        sale=locked_sale,
        type_code=type_code,
        company_profile=company_profile,
        customer_profile=customer_profile,
        issuer_rut=issuer_rut,
        receiver_rut=receiver_rut,
        rows=rows,
        totals=totals,
    )
    document = ElectronicTaxDocument.objects.create(
        **_document_kwargs_from_snapshot(snapshot, idempotency_key=key, created_by=created_by)
    )
    ElectronicTaxLine.objects.bulk_create(
        [ElectronicTaxLine(document=document, **row) for row in rows]
    )
    record_event(
        document=document,
        event_type=ElectronicTaxEvent.EventType.DRAFT_CREATED,
        actor=created_by,
        metadata={"sale_id": locked_sale.id, "type_code": int(type_code)},
    )
    _store_idempotency(
        company=locked_company,
        operation="CREATE_BASE_DTE",
        key=key,
        payload_hash=request_hash,
        document=document,
        status_code=201,
    )
    return document, True


def _recalculate_snapshot_document(document):
    lines = list(document.lines.order_by("line_number", "id"))
    if document.type_code == ElectronicTaxDocument.TypeCode.INVOICE:
        if not any(line.tax_category == TaxProductProfile.TaxCategory.AFFECTED for line in lines):
            raise DTEValidationError("El DTE 33 exige al menos una linea afecta a IVA.")
    if document.type_code == ElectronicTaxDocument.TypeCode.EXEMPT_INVOICE:
        if any(line.tax_category != TaxProductProfile.TaxCategory.EXEMPT for line in lines):
            raise DTEValidationError("El DTE 34 solo admite lineas exentas/no gravadas.")
    return {
        "net": sum(line.net_amount for line in lines),
        "exempt": sum(line.exempt_amount for line in lines),
        "vat": sum(line.vat_amount for line in lines),
        "total": sum(line.total_amount for line in lines),
    }


@transaction.atomic
def validate_document(*, document, expected_version, idempotency_key, actor):
    locked = ElectronicTaxDocument.objects.select_for_update().get(pk=document.pk)
    request_hash = _canonical_hash({"document_id": locked.id, "version": expected_version})
    key, replay = _replay_or_conflict(
        company=locked.company,
        operation="VALIDATE_DTE",
        key=idempotency_key,
        payload_hash=request_hash,
    )
    if replay is not None:
        return replay.document, False
    _check_version(locked, expected_version)
    if locked.state != ElectronicTaxDocument.State.DRAFT:
        raise DTEInvalidStateError("Solo un DRAFT puede validarse y pasar a READY.")

    totals = _recalculate_snapshot_document(locked)
    expected = {
        "net": locked.net_amount,
        "exempt": locked.exempt_amount,
        "vat": locked.vat_amount,
        "total": locked.total_amount,
    }
    if totals != expected:
        raise DTEValidationError("Los importes del snapshot ya no son reproducibles.")
    if locked.type_code == ElectronicTaxDocument.TypeCode.EXEMPT_INVOICE and locked.vat_amount != 0:
        raise DTEValidationError("El DTE 34 debe tener IVA igual a cero.")

    locked.state = ElectronicTaxDocument.State.READY
    locked.version += 1
    locked.save(update_fields=("state", "version", "updated_at"))
    record_event(document=locked, event_type=ElectronicTaxEvent.EventType.VALIDATED, actor=actor)
    _store_idempotency(
        company=locked.company,
        operation="VALIDATE_DTE",
        key=key,
        payload_hash=request_hash,
        document=locked,
    )
    return locked, True


@transaction.atomic
def discard_document(*, document, expected_version, idempotency_key, actor):
    locked = ElectronicTaxDocument.objects.select_for_update().get(pk=document.pk)
    request_hash = _canonical_hash({"document_id": locked.id, "version": expected_version})
    key, replay = _replay_or_conflict(
        company=locked.company,
        operation="DISCARD_DTE",
        key=idempotency_key,
        payload_hash=request_hash,
    )
    if replay is not None:
        return replay.document, False
    _check_version(locked, expected_version)
    if locked.state not in {ElectronicTaxDocument.State.DRAFT, ElectronicTaxDocument.State.READY}:
        raise DTEInvalidStateError("Solo DRAFT o READY pueden descartarse.")
    locked.state = ElectronicTaxDocument.State.DISCARDED
    locked.is_active_base = False
    locked.discarded_at = timezone.now()
    locked.version += 1
    locked.save(update_fields=("state", "is_active_base", "discarded_at", "version", "updated_at"))
    record_event(document=locked, event_type=ElectronicTaxEvent.EventType.DISCARDED, actor=actor)
    _store_idempotency(
        company=locked.company,
        operation="DISCARD_DTE",
        key=key,
        payload_hash=request_hash,
        document=locked,
    )
    return locked, True


def _clone_party_fields(source):
    return {
        "issuer_rut": source.issuer_rut,
        "issuer_legal_name": source.issuer_legal_name,
        "issuer_business_activity": source.issuer_business_activity,
        "issuer_address": source.issuer_address,
        "issuer_commune": source.issuer_commune,
        "issuer_city": source.issuer_city,
        "issuer_tax_email": source.issuer_tax_email,
        "receiver_rut": source.receiver_rut,
        "receiver_legal_name": source.receiver_legal_name,
        "receiver_business_activity": source.receiver_business_activity,
        "receiver_address": source.receiver_address,
        "receiver_commune": source.receiver_commune,
        "receiver_city": source.receiver_city,
        "receiver_tax_email": source.receiver_tax_email,
    }


def _make_reference_snapshot(*, source, target_type, reason, correction=None):
    correction = correction or {}
    party = _clone_party_fields(source)
    allowed_correction_fields = {
        "issuer_business_activity",
        "issuer_address",
        "issuer_commune",
        "issuer_city",
        "receiver_business_activity",
        "receiver_address",
        "receiver_commune",
        "receiver_city",
    }
    for field, value in correction.items():
        if field not in allowed_correction_fields:
            raise DTEValidationError(f"El campo {field} no admite correccion de texto en este MVP.")
        clean = str(value or "").strip()
        if not clean:
            raise DTEValidationError(f"El campo {field} corregido no puede quedar vacio.")
        party[field] = clean

    zero_amount = reason == ElectronicTaxReference.Reason.CORRECT_TEXT
    totals = {
        "net": 0 if zero_amount else source.net_amount,
        "exempt": 0 if zero_amount else source.exempt_amount,
        "vat": 0 if zero_amount else source.vat_amount,
        "total": 0 if zero_amount else source.total_amount,
    }
    payload = {
        "source_document_id": source.id,
        "company_id": source.company_id,
        "branch_id": source.branch_id,
        "sale_id": source.sale_id,
        "type_code": int(target_type),
        "reason": reason,
        "party": party,
        "totals": totals,
        "vat_rate": str(source.vat_rate),
        "currency": source.currency,
        "correction": correction,
    }
    return payload, party, totals


def _create_reference_document(*, source, target_type, reason, description, correction, key, payload_hash, operation, actor):
    payload, party, totals = _make_reference_snapshot(
        source=source,
        target_type=target_type,
        reason=reason,
        correction=correction,
    )
    document = ElectronicTaxDocument.objects.create(
        company=source.company,
        branch=source.branch,
        sale=source.sale,
        type_code=target_type,
        state=ElectronicTaxDocument.State.DRAFT,
        version=1,
        is_active_base=False,
        **party,
        net_amount=totals["net"],
        exempt_amount=totals["exempt"],
        vat_rate=source.vat_rate,
        vat_amount=totals["vat"],
        total_amount=totals["total"],
        currency=source.currency,
        snapshot_hash=_canonical_hash(payload),
        creation_idempotency_key=key,
        created_by=actor,
    )
    if reason != ElectronicTaxReference.Reason.CORRECT_TEXT:
        ElectronicTaxLine.objects.bulk_create(
            [
                ElectronicTaxLine(
                    document=document,
                    line_number=line.line_number,
                    variant=line.variant,
                    sku=line.sku,
                    description=line.description,
                    quantity=line.quantity,
                    unit_price=line.unit_price,
                    discount_amount=line.discount_amount,
                    tax_category=line.tax_category,
                    net_amount=line.net_amount,
                    exempt_amount=line.exempt_amount,
                    vat_amount=line.vat_amount,
                    total_amount=line.total_amount,
                )
                for line in source.lines.order_by("line_number", "id")
            ]
        )
    ElectronicTaxReference.objects.create(
        document=document,
        referenced_document=source,
        reason=reason,
        reference_code=1,
        reference_date=source.issue_date,
        referenced_type_code=source.type_code,
        referenced_folio=source.folio,
        description=description.strip(),
    )
    event_type = (
        ElectronicTaxEvent.EventType.CREDIT_NOTE_CREATED
        if target_type == ElectronicTaxDocument.TypeCode.CREDIT_NOTE
        else ElectronicTaxEvent.EventType.DEBIT_NOTE_CREATED
    )
    record_event(
        document=document,
        event_type=event_type,
        actor=actor,
        metadata={"source_document_id": source.id, "reason": reason},
    )
    _store_idempotency(
        company=source.company,
        operation=operation,
        key=key,
        payload_hash=payload_hash,
        document=document,
        status_code=201,
    )
    return document


@transaction.atomic
def create_credit_note(*, source_document, reason, description, correction, expected_version, idempotency_key, actor):
    source = ElectronicTaxDocument.objects.select_for_update().select_related("sale").get(pk=source_document.pk)
    request_payload = {
        "source_document_id": source.id,
        "reason": reason,
        "description": description.strip(),
        "correction": correction or {},
        "version": expected_version,
    }
    payload_hash = _canonical_hash(request_payload)
    key, replay = _replay_or_conflict(
        company=source.company,
        operation="CREATE_CREDIT_NOTE",
        key=idempotency_key,
        payload_hash=payload_hash,
    )
    if replay is not None:
        return replay.document, False
    _check_version(source, expected_version)
    if source.state not in {
        ElectronicTaxDocument.State.ACCEPTED,
        ElectronicTaxDocument.State.ACCEPTED_WITH_REPAIR,
    }:
        raise DTEInvalidStateError("La nota de credito exige un DTE aceptado o aceptado con reparo.")
    if source.folio is None or source.issue_date is None:
        raise DTEValidationError("El documento referenciado debe tener folio y fecha de emision.")
    if reason == ElectronicTaxReference.Reason.CORRECT_AMOUNTS:
        raise DTECommercialAdjustmentRequiredError(
            "Los ajustes parciales de monto requieren el slice de ajuste comercial/reembolso."
        )
    if reason == ElectronicTaxReference.Reason.CANCEL_DOCUMENT:
        if source.type_code not in (
            ElectronicTaxDocument.TypeCode.INVOICE,
            ElectronicTaxDocument.TypeCode.EXEMPT_INVOICE,
        ):
            raise DTEValidationError("CANCEL_DOCUMENT solo referencia una factura 33/34.")
        if source.sale.paid_amount != 0:
            raise DTERefundRequiredError("La anulacion total exige paid_amount = 0.")
    elif reason == ElectronicTaxReference.Reason.CORRECT_TEXT:
        if source.type_code not in (
            ElectronicTaxDocument.TypeCode.INVOICE,
            ElectronicTaxDocument.TypeCode.EXEMPT_INVOICE,
        ):
            raise DTEValidationError("CORRECT_TEXT solo se habilita sobre factura 33/34 en este MVP.")
        if not correction:
            raise DTEValidationError("CORRECT_TEXT exige al menos un campo de texto corregido.")
    elif reason == ElectronicTaxReference.Reason.CANCEL_DEBIT_NOTE:
        if source.type_code != ElectronicTaxDocument.TypeCode.DEBIT_NOTE:
            raise DTEValidationError("CANCEL_DEBIT_NOTE exige una nota de debito 56.")
    else:
        raise DTEValidationError("El motivo no esta habilitado para una nota de credito.")

    document = _create_reference_document(
        source=source,
        target_type=ElectronicTaxDocument.TypeCode.CREDIT_NOTE,
        reason=reason,
        description=description,
        correction=correction,
        key=key,
        payload_hash=payload_hash,
        operation="CREATE_CREDIT_NOTE",
        actor=actor,
    )
    return document, True


@transaction.atomic
def create_debit_note(*, source_document, reason, description, expected_version, idempotency_key, actor):
    source = ElectronicTaxDocument.objects.select_for_update().get(pk=source_document.pk)
    request_payload = {
        "source_document_id": source.id,
        "reason": reason,
        "description": description.strip(),
        "version": expected_version,
    }
    payload_hash = _canonical_hash(request_payload)
    key, replay = _replay_or_conflict(
        company=source.company,
        operation="CREATE_DEBIT_NOTE",
        key=idempotency_key,
        payload_hash=payload_hash,
    )
    if replay is not None:
        return replay.document, False
    _check_version(source, expected_version)
    if source.state not in {
        ElectronicTaxDocument.State.ACCEPTED,
        ElectronicTaxDocument.State.ACCEPTED_WITH_REPAIR,
    }:
        raise DTEInvalidStateError("La nota de debito exige un DTE aceptado o aceptado con reparo.")
    if source.type_code != ElectronicTaxDocument.TypeCode.CREDIT_NOTE:
        raise DTEValidationError("El DTE 56 solo anula una nota de credito aceptada en este MVP.")
    if reason != ElectronicTaxReference.Reason.CANCEL_CREDIT_NOTE:
        raise DTEValidationError("El unico motivo habilitado para DTE 56 es CANCEL_CREDIT_NOTE.")
    if source.folio is None or source.issue_date is None:
        raise DTEValidationError("El documento referenciado debe tener folio y fecha de emision.")

    document = _create_reference_document(
        source=source,
        target_type=ElectronicTaxDocument.TypeCode.DEBIT_NOTE,
        reason=reason,
        description=description,
        correction=None,
        key=key,
        payload_hash=payload_hash,
        operation="CREATE_DEBIT_NOTE",
        actor=actor,
    )
    return document, True


@transaction.atomic
def reserve_folio(*, document, actor):
    locked = ElectronicTaxDocument.objects.select_for_update().get(pk=document.pk)
    if locked.state != ElectronicTaxDocument.State.READY:
        raise DTEInvalidStateError("Solo un DTE READY puede reservar folio.")
    if hasattr(locked, "folio_reservation"):
        return locked.folio_reservation, False
    authorization = (
        FolioAuthorization.objects.select_for_update()
        .filter(
            company=locked.company,
            type_code=locked.type_code,
            status=FolioAuthorization.Status.ACTIVE,
            next_folio__lte=models_f("end_folio"),
        )
        .order_by("start_folio", "id")
        .first()
    )
    if authorization is None:
        raise DTEFolioUnavailableError("No hay folios activos disponibles para la empresa y tipo de DTE.")
    folio = authorization.next_folio
    reservation = FolioReservation.objects.create(
        company=locked.company,
        branch=locked.branch,
        authorization=authorization,
        document=locked,
        type_code=locked.type_code,
        folio=folio,
    )
    authorization.next_folio = folio + 1
    if authorization.next_folio > authorization.end_folio:
        authorization.status = FolioAuthorization.Status.EXHAUSTED
    authorization.save(update_fields=("next_folio", "status", "updated_at"))
    locked.folio = folio
    locked.folio_authorization = authorization
    locked.state = ElectronicTaxDocument.State.FOLIO_RESERVED
    locked.issue_date = locked.issue_date or timezone.localdate()
    locked.version += 1
    locked.save(update_fields=("folio", "folio_authorization", "state", "issue_date", "version", "updated_at"))
    record_event(
        document=locked,
        event_type=ElectronicTaxEvent.EventType.FOLIO_RESERVED,
        actor=actor,
        metadata={"folio": folio, "authorization_id": authorization.id},
    )
    return reservation, True


def models_f(field_name):
    # Import local para mantener el modulo libre de dependencias de ORM no usadas en otros caminos.
    from django.db.models import F

    return F(field_name)


@transaction.atomic
def issue_document(*, document, expected_version, idempotency_key, actor, provider=DEFAULT_PROVIDER):
    locked = ElectronicTaxDocument.objects.select_for_update().get(pk=document.pk)
    request_hash = _canonical_hash({"document_id": locked.id, "version": expected_version})
    key, replay = _replay_or_conflict(
        company=locked.company,
        operation="ISSUE_DTE",
        key=idempotency_key,
        payload_hash=request_hash,
    )
    if replay is not None:
        return replay.document, False
    _check_version(locked, expected_version)
    if not getattr(provider, "configured", False):
        raise DTEProviderNotConfiguredError(
            "El adaptador SII no esta configurado en el backend base; no se reservo folio ni se cambio el estado."
        )
    if locked.state != ElectronicTaxDocument.State.READY:
        raise DTEInvalidStateError("Solo un DTE READY puede iniciar emision.")

    reservation, _ = reserve_folio(document=locked, actor=actor)
    locked.refresh_from_db()

    sign_result = provider.sign(document=locked)
    xml_hash = str(sign_result.get("xml_hash") or "").strip()
    if len(xml_hash) != 64:
        raise DTEValidationError("El adaptador no entrego un hash XML valido.")
    locked.xml_hash = xml_hash
    locked.state = ElectronicTaxDocument.State.SIGNED
    locked.version += 1
    locked.save(update_fields=("xml_hash", "state", "version", "updated_at"))
    record_event(
        document=locked,
        event_type=ElectronicTaxEvent.EventType.SIGNED,
        actor=actor,
        metadata={"folio": locked.folio},
    )
    record_event(
        document=locked,
        event_type=ElectronicTaxEvent.EventType.SUBMIT_REQUESTED,
        actor=actor,
        metadata={"folio": reservation.folio},
    )

    try:
        submit_result = provider.submit(document=locked)
    except ProviderSendUncertain:
        locked.state = ElectronicTaxDocument.State.SEND_UNCERTAIN
        locked.version += 1
        locked.save(update_fields=("state", "version", "updated_at"))
        record_event(
            document=locked,
            event_type=ElectronicTaxEvent.EventType.SEND_UNCERTAIN,
            actor=actor,
            code="SEND_UNCERTAIN",
            metadata={"folio": locked.folio},
        )
        _store_idempotency(
            company=locked.company,
            operation="ISSUE_DTE",
            key=key,
            payload_hash=request_hash,
            document=locked,
            status_code=202,
        )
        return locked, True

    track_id = str(submit_result.get("track_id") or "").strip()
    if not track_id:
        raise DTEValidationError("El adaptador no entrego un track id valido.")

    locked.provider_track_id = track_id
    locked.state = ElectronicTaxDocument.State.SUBMITTED
    locked.version += 1
    locked.save(update_fields=("provider_track_id", "state", "version", "updated_at"))
    record_event(
        document=locked,
        event_type=ElectronicTaxEvent.EventType.SUBMITTED,
        actor=actor,
        metadata={"track_id": track_id, "folio": locked.folio},
    )
    _store_idempotency(
        company=locked.company,
        operation="ISSUE_DTE",
        key=key,
        payload_hash=request_hash,
        document=locked,
    )
    return locked, True


def _apply_reference_effect_if_accepted(*, document, actor):
    if document.type_code not in (
        ElectronicTaxDocument.TypeCode.CREDIT_NOTE,
        ElectronicTaxDocument.TypeCode.DEBIT_NOTE,
    ):
        return
    reference = document.references.select_related("referenced_document").first()
    if reference is None:
        return
    cancelling_reasons = {
        ElectronicTaxReference.Reason.CANCEL_DOCUMENT,
        ElectronicTaxReference.Reason.CANCEL_DEBIT_NOTE,
        ElectronicTaxReference.Reason.CANCEL_CREDIT_NOTE,
    }
    if reference.reason not in cancelling_reasons:
        return
    source = ElectronicTaxDocument.objects.select_for_update().get(
        pk=reference.referenced_document_id
    )
    if source.state in {
        ElectronicTaxDocument.State.ACCEPTED,
        ElectronicTaxDocument.State.ACCEPTED_WITH_REPAIR,
    }:
        source.state = ElectronicTaxDocument.State.CANCELLED_BY_REFERENCE
        source.is_active_base = False if source.type_code in (33, 34) else source.is_active_base
        source.version += 1
        source.save(update_fields=("state", "is_active_base", "version", "updated_at"))
        record_event(
            document=source,
            event_type=ElectronicTaxEvent.EventType.CANCELLED_BY_REFERENCE,
            actor=actor,
            metadata={"cancelling_document_id": document.id},
        )


@transaction.atomic
def refresh_document_status(*, document, expected_version, idempotency_key, actor, provider=DEFAULT_PROVIDER):
    locked = ElectronicTaxDocument.objects.select_for_update().get(pk=document.pk)
    request_hash = _canonical_hash({"document_id": locked.id, "version": expected_version})
    key, replay = _replay_or_conflict(
        company=locked.company,
        operation="REFRESH_DTE_STATUS",
        key=idempotency_key,
        payload_hash=request_hash,
    )
    if replay is not None:
        return replay.document, False
    _check_version(locked, expected_version)
    if not getattr(provider, "configured", False):
        raise DTEProviderNotConfiguredError("El adaptador SII no esta configurado para consultar estado.")
    if locked.state not in {
        ElectronicTaxDocument.State.SUBMITTED,
        ElectronicTaxDocument.State.PROCESSING,
        ElectronicTaxDocument.State.SEND_UNCERTAIN,
    }:
        raise DTEInvalidStateError(
            "La consulta de estado solo aplica a SUBMITTED, PROCESSING o SEND_UNCERTAIN."
        )

    result = provider.refresh_status(document=locked)
    new_state = result.get("state")
    allowed_states = {
        ElectronicTaxDocument.State.PROCESSING,
        ElectronicTaxDocument.State.ACCEPTED,
        ElectronicTaxDocument.State.ACCEPTED_WITH_REPAIR,
        ElectronicTaxDocument.State.REJECTED,
    }
    if new_state not in allowed_states:
        raise DTEValidationError("El adaptador devolvio un estado normalizado no permitido.")

    locked.state = new_state
    locked.provider_status_code = str(result.get("code") or "")[:80]
    locked.provider_status_message = str(result.get("message") or "")[:500]
    locked.provider_last_checked_at = timezone.now()
    locked.version += 1
    locked.save(
        update_fields=(
            "state",
            "provider_status_code",
            "provider_status_message",
            "provider_last_checked_at",
            "version",
            "updated_at",
        )
    )
    event_type = {
        ElectronicTaxDocument.State.PROCESSING: ElectronicTaxEvent.EventType.STATUS_REFRESHED,
        ElectronicTaxDocument.State.ACCEPTED: ElectronicTaxEvent.EventType.ACCEPTED,
        ElectronicTaxDocument.State.ACCEPTED_WITH_REPAIR: ElectronicTaxEvent.EventType.ACCEPTED_WITH_REPAIR,
        ElectronicTaxDocument.State.REJECTED: ElectronicTaxEvent.EventType.REJECTED,
    }[new_state]
    record_event(
        document=locked,
        event_type=event_type,
        actor=actor,
        code=locked.provider_status_code,
        metadata={"state": new_state},
    )
    if new_state in {
        ElectronicTaxDocument.State.ACCEPTED,
        ElectronicTaxDocument.State.ACCEPTED_WITH_REPAIR,
    }:
        _apply_reference_effect_if_accepted(document=locked, actor=actor)

    _store_idempotency(
        company=locked.company,
        operation="REFRESH_DTE_STATUS",
        key=key,
        payload_hash=request_hash,
        document=locked,
    )
    return locked, True
