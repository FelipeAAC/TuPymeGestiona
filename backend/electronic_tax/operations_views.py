from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from organizations.models import CompanyMembership, RoleAssignment

from .models import ElectronicTaxOperationalAlert
from .operations import operational_summary


VIEW_PERMISSION = "electronic_tax_document.view"


def _parse_company_id(raw):
    if isinstance(raw, bool):
        return None
    if isinstance(raw, int):
        return raw if raw > 0 else None
    if isinstance(raw, str) and raw.strip().isdecimal():
        value = int(raw.strip())
        return value if value > 0 else None
    return None


def _resolve_membership(*, request):
    raw_company = request.query_params.get("company")
    if raw_company in (None, ""):
        return None, Response(
            {"code": "DTE_VALIDATION_ERROR", "detail": "company es obligatorio."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    company_id = _parse_company_id(raw_company)
    if company_id is None:
        return None, Response(
            {"code": "DTE_VALIDATION_ERROR", "detail": "company debe ser un entero valido."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    membership = (
        CompanyMembership.objects.filter(
            user=request.user,
            company_id=company_id,
            status=CompanyMembership.Status.ACTIVE,
        )
        .select_related("company")
        .first()
    )
    if membership is None:
        return None, Response(
            {"code": "DTE_PERMISSION_DENIED", "detail": "No tienes acceso a esta empresa."},
            status=status.HTTP_403_FORBIDDEN,
        )
    return membership, None


def _can_view_operations(*, user, company):
    return RoleAssignment.objects.filter(
        membership__user=user,
        membership__company=company,
        membership__status=CompanyMembership.Status.ACTIVE,
        role__company=company,
        role__status="ACTIVE",
        role__permission_links__permission__code=VIEW_PERMISSION,
    ).exists()


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def operations_summary_view(request):
    membership, error = _resolve_membership(request=request)
    if error:
        return error
    if not _can_view_operations(user=request.user, company=membership.company):
        return Response(
            {"code": "DTE_PERMISSION_DENIED", "detail": "No tienes permiso para consultar operacion tributaria."},
            status=status.HTTP_403_FORBIDDEN,
        )
    return Response({"operations": operational_summary(company=membership.company)})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def operations_alerts_view(request):
    membership, error = _resolve_membership(request=request)
    if error:
        return error
    if not _can_view_operations(user=request.user, company=membership.company):
        return Response(
            {"code": "DTE_PERMISSION_DENIED", "detail": "No tienes permiso para consultar alertas tributarias."},
            status=status.HTTP_403_FORBIDDEN,
        )
    alerts = ElectronicTaxOperationalAlert.objects.filter(company=membership.company).order_by(
        "status", "-severity", "code", "id"
    )[:200]
    return Response(
        {
            "alerts": [
                {
                    "id": item.id,
                    "code": item.code,
                    "severity": item.severity,
                    "status": item.status,
                    "resource_kind": item.resource_kind,
                    "resource_id": item.resource_id,
                    "message": item.message,
                    "details": item.details,
                    "first_seen_at": item.first_seen_at,
                    "last_seen_at": item.last_seen_at,
                    "resolved_at": item.resolved_at,
                }
                for item in alerts
            ]
        }
    )
