from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .services import DashboardPermissionError, dashboard_overview


def _company_id(request):
    raw = request.query_params.get("company")
    if raw in (None, ""):
        return None, Response(
            {"detail": "El parámetro company es obligatorio."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    try:
        company_id = int(raw)
    except (TypeError, ValueError):
        company_id = 0
    if company_id <= 0:
        return None, Response(
            {"detail": "El parámetro company debe ser un entero mayor a cero."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    return company_id, None


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def dashboard_overview_view(request):
    company_id, error_response = _company_id(request)
    if error_response is not None:
        return error_response

    try:
        return Response(
            dashboard_overview(
                user=request.user,
                company_id=company_id,
            )
        )
    except DashboardPermissionError as exc:
        return Response(
            {"detail": str(exc)},
            status=status.HTTP_403_FORBIDDEN,
        )
