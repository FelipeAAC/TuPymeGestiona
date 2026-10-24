"""Safe lifecycle operations for the protected maintainer workspace."""

from __future__ import annotations

import hashlib
import secrets
from datetime import timedelta

from django.db import transaction
from django.db.models.deletion import ProtectedError
from django.utils import timezone

from administration.models import OrderStatusConfiguration, PaymentMethod
from accounts.access import is_destructive_admin
from accounts.models import User
from catalog.models import Brand, Category, Product, ProductVariant, Supplier
from customers.models import Customer
from maintainers.models import DestructiveActionChallenge, MaintainerAuditEvent
from organizations.models import (
    Branch,
    Company,
    CompanyMembership,
    CompanyRole,
    Warehouse,
)


CHALLENGE_MINUTES = 5
AUDIT_ITEM_LIMIT = 200

RELATION_LABELS = {
    "branches": "sucursales",
    "memberships": "membresías de empresa",
    "branch_memberships": "asignaciones de sucursal",
    "roles": "roles de empresa",
    "permission_links": "permisos del rol",
    "assignments": "asignaciones de rol",
    "categories": "categorías",
    "brands": "marcas",
    "products": "productos",
    "variants": "variantes",
    "suppliers": "proveedores",
    "warehouses": "bodegas",
    "customers": "clientes",
    "orders": "pedidos",
    "payment_methods": "métodos de pago",
    "general_settings": "configuración general",
    "order_status_configurations": "estados de pedido",
    "administration_events": "eventos administrativos",
}


RESOURCE_MODELS = {
    "company": Company,
    "branch": Branch,
    "membership": CompanyMembership,
    "category": Category,
    "brand": Brand,
    "product": Product,
    "variant": ProductVariant,
    "supplier": Supplier,
    "warehouse": Warehouse,
    "customer": Customer,
    "role": CompanyRole,
    "payment_method": PaymentMethod,
    "order_status": OrderStatusConfiguration,
}

STATE_FIELDS = {
    "company": ("is_active", True, False),
    "branch": ("is_active", True, False),
    "membership": ("status", CompanyMembership.Status.ACTIVE, CompanyMembership.Status.SUSPENDED),
    "category": ("status", Category.Status.ACTIVE, Category.Status.INACTIVE),
    "brand": ("is_active", True, False),
    "product": ("status", Product.Status.ACTIVE, Product.Status.INACTIVE),
    "variant": ("status", ProductVariant.Status.ACTIVE, ProductVariant.Status.INACTIVE),
    "supplier": ("status", Supplier.Status.ACTIVE, Supplier.Status.INACTIVE),
    "warehouse": ("is_active", True, False),
    "customer": ("status", Customer.Status.ACTIVE, Customer.Status.INACTIVE),
    "role": ("status", CompanyRole.Status.ACTIVE, CompanyRole.Status.INACTIVE),
    "payment_method": ("is_active", True, False),
    "order_status": ("is_active", True, False),
}

PROTECTED_FROM_HARD_DELETE = {"membership", "customer", "order_status"}
COMPANY_CLEANUP_RELATIONS = {
    "payment_methods",
    "general_settings",
    "order_status_configurations",
    "administration_events",
}


class LifecycleError(Exception):
    status_code = 400


class LifecycleNotFound(LifecycleError):
    status_code = 404


class LifecycleForbidden(LifecycleError):
    status_code = 403


class LifecycleConflict(LifecycleError):
    status_code = 409


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _company_id_for(resource_type: str, resource) -> int | None:
    if resource_type == "company":
        return resource.id
    if resource_type == "variant":
        return resource.product.company_id
    if resource_type == "membership":
        return resource.company_id
    if hasattr(resource, "company_id"):
        return resource.company_id
    if resource_type == "role":
        return resource.company_id
    if resource_type == "payment_method":
        return resource.company_id
    if resource_type == "order_status":
        return resource.company_id
    return None


def resolve_resource(*, company_id: int, resource_type: str, resource_id: int):
    model = RESOURCE_MODELS.get(resource_type)
    if model is None:
        raise LifecycleError("Tipo de recurso no soportado.")

    if resource_type == "company":
        resource = model.objects.filter(pk=resource_id).first()
    elif resource_type == "variant":
        resource = model.objects.select_related("product").filter(
            pk=resource_id,
            product__company_id=company_id,
        ).first()
    elif resource_type == "membership":
        resource = model.objects.select_related("user").filter(
            pk=resource_id,
            company_id=company_id,
        ).first()
    elif resource_type == "role":
        resource = model.objects.filter(pk=resource_id, company_id=company_id).first()
    else:
        resource = model.objects.filter(pk=resource_id, company_id=company_id).first()

    if resource is None:
        raise LifecycleNotFound("El recurso no existe en la empresa seleccionada.")
    if _company_id_for(resource_type, resource) != company_id:
        raise LifecycleNotFound("El recurso no pertenece a la empresa seleccionada.")
    return resource


def resource_label(resource_type: str, resource) -> str:
    if resource_type == "membership":
        return resource.user.get_full_name() or resource.user.email or resource.user.username
    if resource_type == "variant":
        return resource.sku
    if resource_type == "warehouse":
        return f"{resource.code} · {resource.name}"
    if resource_type == "role":
        return resource.name
    if hasattr(resource, "name"):
        return resource.name
    return f"{resource_type} {resource.pk}"


def relation_label(relation, related_model) -> str:
    accessor = relation.get_accessor_name()
    return RELATION_LABELS.get(
        accessor,
        str(related_model._meta.verbose_name_plural).capitalize(),
    )


def confirmation_phrase(resource_type: str, resource_id: int) -> str:
    return f"ELIMINAR {resource_type.upper()} {resource_id}"


def related_impact(resource) -> list[dict[str, int | str]]:
    """Return all related rows before a hard delete.

    We intentionally treat every reverse relation as a blocker, including
    cascades, so a maintainer can never trigger an accidental historical
    cascade.  The operator can archive the record instead.
    """
    impact = []
    for relation in resource._meta.related_objects:
        related_model = relation.related_model
        field_name = relation.field.name
        try:
            count = related_model._default_manager.filter(**{field_name: resource}).count()
        except (TypeError, ValueError):
            continue
        if count:
            impact.append(
                {
                    "relation": relation.get_accessor_name(),
                    "label": relation_label(relation, related_model),
                    "count": count,
                }
            )
    return impact


def _safe_value(value):
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _safe_object_label(obj, relation: str) -> str:
    if relation == "memberships" and hasattr(obj, "user"):
        return obj.user.get_full_name() or obj.user.email or obj.user.username
    values = []
    for field in ("name", "display_name", "code", "sku", "event_type"):
        value = getattr(obj, field, None)
        if value not in (None, ""):
            values.append(str(value))
            if field in {"name", "display_name", "sku"}:
                break
    return " · ".join(values) or f"{obj.__class__.__name__} {obj.pk}"


def _safe_object_snapshot(obj, relation: str) -> dict[str, object]:
    snapshot: dict[str, object] = {
        "id": obj.pk,
        "label": _safe_object_label(obj, relation),
    }
    for field in (
        "code",
        "name",
        "display_name",
        "sku",
        "status",
        "is_active",
        "event_type",
        "resource_type",
        "resource_id",
    ):
        value = getattr(obj, field, None)
        if value not in (None, ""):
            snapshot[field] = _safe_value(value)
    return snapshot


def audit_related_snapshot(resource) -> list[dict[str, object]]:
    """Capture bounded, non-secret summaries before a destructive delete."""
    snapshots: list[dict[str, object]] = []
    for relation in resource._meta.related_objects:
        related_model = relation.related_model
        accessor = relation.get_accessor_name()
        field_name = relation.field.name
        try:
            if getattr(relation, "one_to_one", False):
                related = getattr(resource, accessor, None)
                related_items = [related] if related is not None else []
                total = len(related_items)
            else:
                queryset = related_model._default_manager.filter(**{field_name: resource}).order_by("pk")
                total = queryset.count()
                related_items = list(queryset[:AUDIT_ITEM_LIMIT])
        except (AttributeError, TypeError, ValueError):
            continue
        if not total:
            continue
        snapshots.append(
            {
                "relation": accessor,
                "label": relation_label(relation, related_model),
                "count": total,
                "truncated": total > AUDIT_ITEM_LIMIT,
                "items": [_safe_object_snapshot(item, accessor) for item in related_items],
            }
        )
    return snapshots


def resource_snapshot(resource_type: str, resource) -> dict[str, object]:
    snapshot = {
        "id": resource.pk,
        "resource_type": resource_type,
        "label": resource_label(resource_type, resource),
    }
    for field in ("name", "legal_name", "rut", "code", "sku", "status", "is_active"):
        value = getattr(resource, field, None)
        if value not in (None, ""):
            snapshot[field] = _safe_value(value)
    return snapshot


def _hard_delete_blockers(resource_type: str, impact: list[dict[str, int | str]]):
    if resource_type == "company":
        return [
            item
            for item in impact
            if item["relation"] not in COMPANY_CLEANUP_RELATIONS
        ]
    return impact


def _purge_empty_company(company):
    """Remove only generated configuration before deleting an empty company."""
    company.payment_methods.all().delete()
    if hasattr(company, "general_settings"):
        company.general_settings.delete()
    company.order_status_configurations.all().delete()
    company.administration_events.all().delete()


def _state_payload(resource_type: str, resource) -> dict[str, object]:
    field, active_value, inactive_value = STATE_FIELDS[resource_type]
    current = getattr(resource, field)
    is_active = current == active_value
    return {
        "field": field,
        "value": current,
        "is_active": is_active,
        "can_deactivate": is_active,
        "can_reactivate": not is_active,
        "active_value": active_value,
        "inactive_value": inactive_value,
    }


def preview(*, actor, company_id: int, resource_type: str, resource_id: int) -> dict:
    resource = resolve_resource(
        company_id=company_id,
        resource_type=resource_type,
        resource_id=resource_id,
    )
    impact = related_impact(resource)
    blockers = _hard_delete_blockers(resource_type, impact)
    hard_delete_allowed = (
        resource_type not in PROTECTED_FROM_HARD_DELETE
        and not blockers
    )
    if resource_type == "role" and resource.assignments.exists():
        hard_delete_allowed = False
        impact.append(
            {
                "relation": "assignments",
                "label": "asignaciones de rol",
                "count": resource.assignments.count(),
            }
        )
    if resource_type == "membership" and resource.user_id == actor.id:
        hard_delete_allowed = False
        impact.append(
            {
                "relation": "current_user",
                "label": "cuenta actualmente autenticada",
                "count": 1,
            }
        )
    return {
        "resource_type": resource_type,
        "resource_id": resource.id,
        "label": resource_label(resource_type, resource),
        "company_id": company_id,
        "state": _state_payload(resource_type, resource),
        "impact": impact,
        "can_hard_delete": hard_delete_allowed and is_destructive_admin(actor),
        "destructive_admin": is_destructive_admin(actor),
        "confirmation_phrase": confirmation_phrase(resource_type, resource.id),
        "hard_delete_blocked_reason": (
            "Hay registros relacionados. Desactiva o archiva el recurso para conservar el historial."
            if blockers
            else (
                "El recurso requiere conservación histórica."
                if resource_type in PROTECTED_FROM_HARD_DELETE
                else "La configuración generada se limpiará antes de eliminar la empresa."
                if resource_type == "company" and impact
                else "La cuenta actual no tiene la capacidad destructiva delegada."
                if not is_destructive_admin(actor)
                else ""
            )
        ),
    }


def _audit(*, actor, company_id: int | None, event_type: str, resource_type: str, resource_id, metadata=None):
    return MaintainerAuditEvent.objects.create(
        actor=actor,
        company_id_snapshot=company_id,
        event_type=event_type,
        resource_type=resource_type,
        resource_id=str(resource_id or ""),
        metadata=metadata or {},
    )


@transaction.atomic
def change_state(*, actor, company_id: int, resource_type: str, resource_id: int, active: bool):
    resource = resolve_resource(
        company_id=company_id,
        resource_type=resource_type,
        resource_id=resource_id,
    )
    field, active_value, inactive_value = STATE_FIELDS[resource_type]
    requested = active_value if active else inactive_value
    if resource_type == "membership" and active and resource.status == CompanyMembership.Status.LEFT:
        raise LifecycleError("Una membresía desvinculada no puede reactivarse desde esta pantalla.")
    setattr(resource, field, requested)
    resource.save(update_fields=[field] + (["updated_at"] if hasattr(resource, "updated_at") else []))
    _audit(
        actor=actor,
        company_id=company_id,
        event_type="RESOURCE_REACTIVATED" if active else "RESOURCE_DEACTIVATED",
        resource_type=resource_type,
        resource_id=resource.id,
        metadata={"label": resource_label(resource_type, resource), "value": requested},
    )
    return resource


def create_challenge(*, actor, company_id: int, resource_type: str, resource_id: int, confirmation: str, reason: str):
    if not is_destructive_admin(actor):
        raise LifecycleForbidden("Esta cuenta no puede iniciar una eliminación permanente.")
    details = preview(
        actor=actor,
        company_id=company_id,
        resource_type=resource_type,
        resource_id=resource_id,
    )
    if confirmation != details["confirmation_phrase"]:
        raise LifecycleError("La confirmación no coincide exactamente con la frase solicitada.")
    reason = reason.strip()
    if not reason:
        raise LifecycleError("Indica el motivo de la eliminación permanente.")
    if not details["can_hard_delete"]:
        raise LifecycleConflict(details["hard_delete_blocked_reason"])
    token = secrets.token_urlsafe(32)
    challenge = DestructiveActionChallenge.objects.create(
        actor=actor,
        company_id_snapshot=company_id,
        resource_type=resource_type,
        resource_id=str(resource_id),
        confirmation_phrase=details["confirmation_phrase"],
        reason=reason[:500],
        token_hash=_hash_token(token),
        expires_at=timezone.now() + timedelta(minutes=CHALLENGE_MINUTES),
    )
    return challenge, token, details


@transaction.atomic
def execute_challenge(*, actor, challenge_id: int, token: str, confirmation: str):
    if not is_destructive_admin(actor):
        raise LifecycleForbidden("Esta cuenta ya no tiene capacidad para eliminar datos permanentemente.")
    challenge = (
        DestructiveActionChallenge.objects.select_for_update()
        .filter(pk=challenge_id, actor=actor, used_at__isnull=True)
        .first()
    )
    if challenge is None:
        raise LifecycleError("El desafío no existe o ya fue utilizado.")
    if challenge.expires_at <= timezone.now():
        raise LifecycleError("El desafío de eliminación expiró. Inicia uno nuevo.")
    if not secrets.compare_digest(challenge.token_hash, _hash_token(token)):
        raise LifecycleForbidden("El token de eliminación no es válido.")
    if confirmation != challenge.confirmation_phrase:
        raise LifecycleError("La confirmación no coincide exactamente con la frase solicitada.")
    resource_id = int(challenge.resource_id)
    resource = resolve_resource(
        company_id=challenge.company_id_snapshot,
        resource_type=challenge.resource_type,
        resource_id=resource_id,
    )
    details = preview(
        actor=actor,
        company_id=challenge.company_id_snapshot,
        resource_type=challenge.resource_type,
        resource_id=resource_id,
    )
    if not details["can_hard_delete"]:
        raise LifecycleConflict(details["hard_delete_blocked_reason"])
    label = resource_label(challenge.resource_type, resource)
    impact = details["impact"]
    company = resource if challenge.resource_type == "company" else Company.objects.filter(
        pk=challenge.company_id_snapshot,
    ).only("name").first()
    audit_metadata = {
        "label": label,
        "impact": impact,
        "reason": challenge.reason,
        "company_label": getattr(company, "name", None) or f"Empresa {challenge.company_id_snapshot}",
        "resource_before": resource_snapshot(challenge.resource_type, resource),
        "deleted_related": audit_related_snapshot(resource),
    }
    try:
        if challenge.resource_type == "company":
            _purge_empty_company(resource)
        resource.delete()
    except ProtectedError as exc:
        raise LifecycleConflict(
            "El recurso tiene información protegida. Debe desactivarse o archivarse."
        ) from exc
    challenge.used_at = timezone.now()
    challenge.save(update_fields=["used_at"])
    _audit(
        actor=actor,
        company_id=challenge.company_id_snapshot,
        event_type="RESOURCE_HARD_DELETED",
        resource_type=challenge.resource_type,
        resource_id=resource_id,
        metadata=audit_metadata,
    )
    return {
        "resource_type": challenge.resource_type,
        "resource_id": resource_id,
        "label": label,
    }
