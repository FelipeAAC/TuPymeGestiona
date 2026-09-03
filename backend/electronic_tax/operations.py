import hashlib
import json
import os
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.db import connection, transaction
from django.db.models import Count
from django.utils import timezone

from .models import (
    ElectronicTaxArtifact,
    ElectronicTaxDocument,
    ElectronicTaxExchange,
    ElectronicTaxOperationalAlert,
    ElectronicTaxStatusCheckTask,
    FolioAuthorization,
    FolioReservation,
    TaxCompanyProfile,
)
from .services import refresh_document_status


STATUS_QUERY_STATES = {
    ElectronicTaxDocument.State.SUBMITTED,
    ElectronicTaxDocument.State.PROCESSING,
    ElectronicTaxDocument.State.SEND_UNCERTAIN,
}
TERMINAL_REMOTE_STATES = {
    ElectronicTaxDocument.State.ACCEPTED,
    ElectronicTaxDocument.State.ACCEPTED_WITH_REPAIR,
    ElectronicTaxDocument.State.REJECTED,
}


def _int_setting(name, default, *, minimum=1):
    try:
        value = int(getattr(settings, name, default))
    except (TypeError, ValueError):
        value = default
    return max(minimum, value)


def _upsert_alert(*, company, dedupe_key, code, severity, message, resource_kind="", resource_id="", details=None):
    alert, _ = ElectronicTaxOperationalAlert.objects.update_or_create(
        company=company,
        dedupe_key=dedupe_key,
        defaults={
            "code": code,
            "severity": severity,
            "status": ElectronicTaxOperationalAlert.Status.OPEN,
            "resource_kind": resource_kind,
            "resource_id": str(resource_id or ""),
            "message": message[:500],
            "details": details or {},
            "resolved_at": None,
        },
    )
    return alert


def _resolve_absent_alerts(*, company, active_keys, now):
    queryset = ElectronicTaxOperationalAlert.objects.filter(
        company=company,
        status=ElectronicTaxOperationalAlert.Status.OPEN,
    )
    if active_keys:
        queryset = queryset.exclude(dedupe_key__in=active_keys)
    return queryset.update(
        status=ElectronicTaxOperationalAlert.Status.RESOLVED,
        resolved_at=now,
        last_seen_at=now,
    )


def _pending_status_task(document):
    return ElectronicTaxStatusCheckTask.objects.filter(
        document=document,
        state__in=(
            ElectronicTaxStatusCheckTask.State.PENDING,
            ElectronicTaxStatusCheckTask.State.RUNNING,
        ),
    ).order_by("id").first()


def ensure_status_check_task(*, document, reason, due_at=None):
    existing = _pending_status_task(document)
    if existing is not None:
        if due_at is not None and due_at < existing.due_at:
            existing.due_at = due_at
            existing.reason = reason[:80]
            existing.save(update_fields=("due_at", "reason", "updated_at"))
        return existing, False
    task = ElectronicTaxStatusCheckTask.objects.create(
        company=document.company,
        branch=document.branch,
        document=document,
        actor=document.created_by,
        reason=reason[:80],
        due_at=due_at or timezone.now(),
        max_attempts=_int_setting("ELECTRONIC_TAX_STATUS_RETRY_MAX_ATTEMPTS", 8),
    )
    return task, True


def _certificate_alert(company, active_keys, now):
    if not getattr(settings, "SII_ADAPTER_ENABLED", False):
        return
    if not TaxCompanyProfile.objects.filter(company=company, active=True).exists():
        return
    path = Path(getattr(settings, "SII_CERTIFICATE_PFX_PATH", ""))
    password_env = getattr(settings, "SII_CERTIFICATE_PASSWORD_ENV", "SII_CERTIFICATE_PASSWORD")
    key = "CERTIFICATE_CONFIGURATION"
    active_keys.add(key)
    if not path.is_file() or not os.getenv(password_env, ""):
        _upsert_alert(
            company=company,
            dedupe_key=key,
            code="CERTIFICATE_NOT_CONFIGURED",
            severity=ElectronicTaxOperationalAlert.Severity.CRITICAL,
            message="El adaptador SII esta activo, pero el certificado PFX o su password de entorno no estan disponibles.",
            resource_kind="CERTIFICATE",
        )
        return
    try:
        from .sii_adapter import _certificate_material

        _, cert, _ = _certificate_material()
    except Exception as error:
        _upsert_alert(
            company=company,
            dedupe_key=key,
            code="CERTIFICATE_INVALID",
            severity=ElectronicTaxOperationalAlert.Severity.CRITICAL,
            message="El certificado configurado no puede utilizarse para operar con SII.",
            resource_kind="CERTIFICATE",
            details={"error_type": type(error).__name__},
        )
        return
    warning_days = _int_setting("ELECTRONIC_TAX_CERTIFICATE_WARNING_DAYS", 30)
    expires_at = cert.not_valid_after_utc
    remaining = expires_at - now
    if remaining <= timedelta(days=warning_days):
        code = "CERTIFICATE_EXPIRED" if remaining.total_seconds() <= 0 else "CERTIFICATE_EXPIRING"
        severity = (
            ElectronicTaxOperationalAlert.Severity.CRITICAL
            if code == "CERTIFICATE_EXPIRED"
            else ElectronicTaxOperationalAlert.Severity.WARNING
        )
        _upsert_alert(
            company=company,
            dedupe_key=key,
            code=code,
            severity=severity,
            message=f"El certificado SII vence el {expires_at.date().isoformat()}.",
            resource_kind="CERTIFICATE",
            details={"expires_at": expires_at.isoformat(), "warning_days": warning_days},
        )
    else:
        active_keys.discard(key)


@transaction.atomic
def scan_company_operations(*, company, now=None):
    now = now or timezone.now()
    active_keys = set()
    folio_threshold = _int_setting("ELECTRONIC_TAX_FOLIO_LOW_THRESHOLD", 25)
    stale_minutes = _int_setting("ELECTRONIC_TAX_STALE_MINUTES", 30)
    retry_minutes = _int_setting("ELECTRONIC_TAX_STATUS_RETRY_MINUTES", 5)
    stale_before = now - timedelta(minutes=stale_minutes)

    for authorization in FolioAuthorization.objects.filter(company=company).order_by("type_code", "id"):
        remaining = max(0, authorization.end_folio - authorization.next_folio + 1)
        if authorization.status == FolioAuthorization.Status.EXHAUSTED or remaining == 0:
            key = f"FOLIO_EXHAUSTED:{authorization.id}"
            active_keys.add(key)
            _upsert_alert(
                company=company,
                dedupe_key=key,
                code="FOLIO_EXHAUSTED",
                severity=ElectronicTaxOperationalAlert.Severity.CRITICAL,
                message=f"No quedan folios disponibles para DTE {authorization.type_code} en el rango {authorization.start_folio}-{authorization.end_folio}.",
                resource_kind="FOLIO_AUTHORIZATION",
                resource_id=authorization.id,
                details={"type_code": authorization.type_code, "remaining": remaining},
            )
        elif authorization.status == FolioAuthorization.Status.ACTIVE and remaining <= folio_threshold:
            key = f"FOLIO_LOW:{authorization.id}"
            active_keys.add(key)
            _upsert_alert(
                company=company,
                dedupe_key=key,
                code="FOLIO_LOW",
                severity=ElectronicTaxOperationalAlert.Severity.WARNING,
                message=f"Quedan {remaining} folios disponibles para DTE {authorization.type_code}.",
                resource_kind="FOLIO_AUTHORIZATION",
                resource_id=authorization.id,
                details={"type_code": authorization.type_code, "remaining": remaining, "threshold": folio_threshold},
            )
        if authorization.valid_to and authorization.valid_to <= now.date():
            key = f"CAF_EXPIRED:{authorization.id}"
            active_keys.add(key)
            _upsert_alert(
                company=company,
                dedupe_key=key,
                code="CAF_EXPIRED",
                severity=ElectronicTaxOperationalAlert.Severity.CRITICAL,
                message=f"La autorizacion CAF para DTE {authorization.type_code} tiene vigencia final {authorization.valid_to.isoformat()}.",
                resource_kind="FOLIO_AUTHORIZATION",
                resource_id=authorization.id,
                details={"valid_to": authorization.valid_to.isoformat()},
            )

    stale_documents = ElectronicTaxDocument.objects.filter(
        company=company,
        state__in=STATUS_QUERY_STATES,
        updated_at__lte=stale_before,
    ).select_related("company", "branch", "created_by")
    for document in stale_documents:
        key = f"REMOTE_STATUS_STALE:{document.id}"
        active_keys.add(key)
        severity = (
            ElectronicTaxOperationalAlert.Severity.CRITICAL
            if document.state == ElectronicTaxDocument.State.SEND_UNCERTAIN
            else ElectronicTaxOperationalAlert.Severity.WARNING
        )
        _upsert_alert(
            company=company,
            dedupe_key=key,
            code="REMOTE_STATUS_STALE",
            severity=severity,
            message=f"DTE {document.type_code} folio {document.folio or 'sin-folio'} permanece en {document.state} sin resolucion reciente.",
            resource_kind="DTE",
            resource_id=document.id,
            details={"state": document.state, "stale_minutes": stale_minutes},
        )
        ensure_status_check_task(
            document=document,
            reason="REMOTE_STATUS_STALE",
            due_at=now + timedelta(minutes=retry_minutes),
        )

    uncertain_exchanges = ElectronicTaxExchange.objects.filter(
        document__company=company,
        delivery_state=ElectronicTaxExchange.DeliveryState.SEND_UNCERTAIN,
        updated_at__lte=stale_before,
    ).select_related("document")
    for exchange in uncertain_exchanges:
        key = f"RECEIVER_EXCHANGE_UNCERTAIN:{exchange.document_id}"
        active_keys.add(key)
        _upsert_alert(
            company=company,
            dedupe_key=key,
            code="RECEIVER_EXCHANGE_UNCERTAIN",
            severity=ElectronicTaxOperationalAlert.Severity.WARNING,
            message="El envio al receptor quedo incierto; no se reenvia automaticamente para evitar duplicados.",
            resource_kind="DTE",
            resource_id=exchange.document_id,
            details={"send_attempts": exchange.send_attempts},
        )

    _certificate_alert(company, active_keys, now)
    resolved = _resolve_absent_alerts(company=company, active_keys=active_keys, now=now)
    open_alerts = ElectronicTaxOperationalAlert.objects.filter(
        company=company,
        status=ElectronicTaxOperationalAlert.Status.OPEN,
    )
    return {
        "company_id": company.id,
        "open": open_alerts.count(),
        "critical": open_alerts.filter(severity=ElectronicTaxOperationalAlert.Severity.CRITICAL).count(),
        "warning": open_alerts.filter(severity=ElectronicTaxOperationalAlert.Severity.WARNING).count(),
        "resolved_now": resolved,
    }


def scan_all_operations(*, company=None, now=None):
    if company is not None:
        return [scan_company_operations(company=company, now=now)]
    from organizations.models import Company

    return [scan_company_operations(company=item, now=now) for item in Company.objects.order_by("id")]


def operational_summary(*, company):
    document_counts = {
        row["state"]: row["count"]
        for row in ElectronicTaxDocument.objects.filter(company=company)
        .values("state")
        .annotate(count=Count("id"))
        .order_by("state")
    }
    folios = []
    for authorization in FolioAuthorization.objects.filter(company=company).order_by("type_code", "id"):
        folios.append(
            {
                "authorization_id": authorization.id,
                "type_code": authorization.type_code,
                "status": authorization.status,
                "remaining": max(0, authorization.end_folio - authorization.next_folio + 1),
                "valid_to": authorization.valid_to.isoformat() if authorization.valid_to else None,
            }
        )
    alerts = ElectronicTaxOperationalAlert.objects.filter(
        company=company,
        status=ElectronicTaxOperationalAlert.Status.OPEN,
    )
    tasks = ElectronicTaxStatusCheckTask.objects.filter(company=company)
    return {
        "company_id": company.id,
        "database": {"vendor": connection.vendor, "alias": connection.alias},
        "integration": {
            "sii_adapter_enabled": bool(getattr(settings, "SII_ADAPTER_ENABLED", False)),
            "receiver_exchange_enabled": bool(getattr(settings, "SII_EXCHANGE_ENABLED", False)),
        },
        "documents_by_state": document_counts,
        "folios": folios,
        "alerts": {
            "open": alerts.count(),
            "critical": alerts.filter(severity=ElectronicTaxOperationalAlert.Severity.CRITICAL).count(),
            "warning": alerts.filter(severity=ElectronicTaxOperationalAlert.Severity.WARNING).count(),
        },
        "status_checks": {
            "pending": tasks.filter(state=ElectronicTaxStatusCheckTask.State.PENDING).count(),
            "running": tasks.filter(state=ElectronicTaxStatusCheckTask.State.RUNNING).count(),
            "failed": tasks.filter(state=ElectronicTaxStatusCheckTask.State.FAILED).count(),
        },
    }


def process_status_check_tasks(*, limit=20, execute=False, provider=None, now=None):
    now = now or timezone.now()
    queryset = ElectronicTaxStatusCheckTask.objects.filter(
        state=ElectronicTaxStatusCheckTask.State.PENDING,
        due_at__lte=now,
    ).select_related("document", "actor", "company", "branch").order_by("due_at", "id")[:limit]
    task_ids = [task.id for task in queryset]
    if not execute:
        return {"due": len(task_ids), "processed": 0, "succeeded": 0, "rescheduled": 0, "failed": 0}
    if provider is None and not getattr(settings, "SII_ADAPTER_ENABLED", False):
        raise RuntimeError("SII_ADAPTER_ENABLED debe estar activo para ejecutar consultas remotas.")

    result = {"due": len(task_ids), "processed": 0, "succeeded": 0, "rescheduled": 0, "failed": 0}
    retry_minutes = _int_setting("ELECTRONIC_TAX_STATUS_RETRY_MINUTES", 5)
    for task_id in task_ids:
        with transaction.atomic():
            task = ElectronicTaxStatusCheckTask.objects.select_for_update().select_related("document", "actor").get(pk=task_id)
            if task.state != ElectronicTaxStatusCheckTask.State.PENDING or task.due_at > now:
                continue
            task.state = ElectronicTaxStatusCheckTask.State.RUNNING
            task.attempts += 1
            task.last_attempt_at = now
            task.last_error = ""
            task.save(update_fields=("state", "attempts", "last_attempt_at", "last_error", "updated_at"))
        result["processed"] += 1
        document = ElectronicTaxDocument.objects.get(pk=task.document_id)
        if document.state not in STATUS_QUERY_STATES:
            task.state = ElectronicTaxStatusCheckTask.State.CANCELLED
            task.completed_at = timezone.now()
            task.save(update_fields=("state", "completed_at", "updated_at"))
            continue
        try:
            refreshed, _ = refresh_document_status(
                document=document,
                expected_version=document.version,
                idempotency_key=f"ops-status-{task.id}-{task.attempts}",
                actor=task.actor,
                provider=provider,
            )
        except Exception as error:
            task.last_error = f"{type(error).__name__}: {str(error)}"[:500]
            if task.attempts >= task.max_attempts:
                task.state = ElectronicTaxStatusCheckTask.State.FAILED
                task.completed_at = timezone.now()
                result["failed"] += 1
            else:
                task.state = ElectronicTaxStatusCheckTask.State.PENDING
                delay = retry_minutes * min(12, 2 ** max(0, task.attempts - 1))
                task.due_at = timezone.now() + timedelta(minutes=delay)
                result["rescheduled"] += 1
            task.save()
            continue
        if refreshed.state in TERMINAL_REMOTE_STATES:
            task.state = ElectronicTaxStatusCheckTask.State.SUCCEEDED
            task.completed_at = timezone.now()
            task.save(update_fields=("state", "completed_at", "updated_at"))
            result["succeeded"] += 1
        elif task.attempts >= task.max_attempts:
            task.state = ElectronicTaxStatusCheckTask.State.FAILED
            task.last_error = f"El DTE continuo en {refreshed.state} despues del maximo de intentos."
            task.completed_at = timezone.now()
            task.save(update_fields=("state", "last_error", "completed_at", "updated_at"))
            result["failed"] += 1
        else:
            task.state = ElectronicTaxStatusCheckTask.State.PENDING
            delay = retry_minutes * min(12, 2 ** max(0, task.attempts - 1))
            task.due_at = timezone.now() + timedelta(minutes=delay)
            task.save(update_fields=("state", "due_at", "updated_at"))
            result["rescheduled"] += 1
    return result


def integrity_snapshot(*, company=None):
    documents = ElectronicTaxDocument.objects.all()
    reservations = FolioReservation.objects.all()
    artifacts = ElectronicTaxArtifact.objects.all()
    if company is not None:
        documents = documents.filter(company=company)
        reservations = reservations.filter(company=company)
        artifacts = artifacts.filter(document__company=company)
    problems = []
    for document in documents.filter(folio__isnull=False).select_related("folio_authorization"):
        if not FolioReservation.objects.filter(document=document, folio=document.folio, type_code=document.type_code).exists():
            problems.append({"code": "MISSING_FOLIO_RESERVATION", "document_id": document.id})
    for reservation in reservations.select_related("document", "authorization"):
        if reservation.folio < reservation.authorization.start_folio or reservation.folio > reservation.authorization.end_folio:
            problems.append({"code": "FOLIO_OUT_OF_RANGE", "reservation_id": reservation.id})
    manifest_rows = list(
        documents.order_by("id").values_list(
            "id", "company_id", "type_code", "folio", "state", "snapshot_hash", "xml_hash"
        )
    )
    artifact_rows = list(
        artifacts.order_by("id").values_list("id", "document_id", "kind", "content_hash")
    )
    digest_payload = json.dumps(
        {"documents": manifest_rows, "artifacts": artifact_rows},
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return {
        "database_vendor": connection.vendor,
        "company_id": company.id if company is not None else None,
        "documents": len(manifest_rows),
        "artifacts": len(artifact_rows),
        "reservations": reservations.count(),
        "problems": problems,
        "integrity_digest_sha256": hashlib.sha256(digest_payload).hexdigest(),
        "generated_at": timezone.now().isoformat(),
    }
