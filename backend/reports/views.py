from datetime import date
from decimal import Decimal, InvalidOperation

from django.http import HttpResponse
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .services import (
    InventoryFilters,
    ReportPermissionError,
    ReportValidationError,
    SalesFilters,
    build_inventory_pdf,
    build_inventory_xlsx,
    build_sales_pdf,
    build_sales_xlsx,
    inventory_report_data,
    report_options,
    resolve_report_context,
    sales_report_data,
)


def _positive_int(raw, label, *, required=False):
    if raw in (None, ""):
        if required:
            raise ReportValidationError(f"El parámetro {label} es obligatorio.")
        return None
    try:
        value = int(raw)
    except (TypeError, ValueError) as exc:
        raise ReportValidationError(f"El parámetro {label} debe ser un entero válido.") from exc
    if value <= 0:
        raise ReportValidationError(f"El parámetro {label} debe ser mayor a cero.")
    return value


def _date(raw, label):
    if raw in (None, ""):
        return None
    try:
        return date.fromisoformat(str(raw))
    except ValueError as exc:
        raise ReportValidationError(f"El parámetro {label} debe usar formato YYYY-MM-DD.") from exc


def _decimal(raw, label, default):
    if raw in (None, ""):
        return default
    try:
        return Decimal(str(raw))
    except InvalidOperation as exc:
        raise ReportValidationError(f"El parámetro {label} debe ser numérico.") from exc


def _company_id(request):
    return _positive_int(request.query_params.get("company"), "company", required=True)


def _sales_filters(request):
    return SalesFilters(
        date_from=_date(request.query_params.get("date_from"), "date_from"),
        date_to=_date(request.query_params.get("date_to"), "date_to"),
        branch_id=_positive_int(request.query_params.get("branch"), "branch"),
        seller_id=_positive_int(request.query_params.get("seller"), "seller"),
    )


def _inventory_filters(request):
    return InventoryFilters(
        warehouse_id=_positive_int(request.query_params.get("warehouse"), "warehouse"),
        category_id=_positive_int(request.query_params.get("category"), "category"),
        stock_level=(request.query_params.get("stock_level") or "ALL").strip().upper(),
        critical_threshold=_decimal(request.query_params.get("critical_threshold"), "critical_threshold", Decimal("5.000")),
    )


def _handle_error(exc):
    if isinstance(exc, ReportPermissionError):
        return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
    return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def report_options_view(request):
    try:
        return Response(report_options(user=request.user, company_id=_company_id(request)))
    except (ReportPermissionError, ReportValidationError) as exc:
        return _handle_error(exc)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def sales_report_view(request):
    try:
        context = resolve_report_context(user=request.user, company_id=_company_id(request))
        return Response(sales_report_data(context=context, filters=_sales_filters(request)))
    except (ReportPermissionError, ReportValidationError) as exc:
        return _handle_error(exc)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def inventory_report_view(request):
    try:
        context = resolve_report_context(user=request.user, company_id=_company_id(request))
        return Response(inventory_report_data(context=context, filters=_inventory_filters(request)))
    except (ReportPermissionError, ReportValidationError) as exc:
        return _handle_error(exc)


def _download_response(content, *, content_type, filename):
    response = HttpResponse(content, content_type=content_type)
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    response["X-Content-Type-Options"] = "nosniff"
    return response


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def sales_pdf_view(request):
    try:
        context = resolve_report_context(user=request.user, company_id=_company_id(request))
        content = build_sales_pdf(context=context, filters=_sales_filters(request))
        return _download_response(content, content_type="application/pdf", filename=f"reporte_ventas_{context.company.id}.pdf")
    except (ReportPermissionError, ReportValidationError) as exc:
        return _handle_error(exc)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def sales_xls_view(request):
    try:
        context = resolve_report_context(user=request.user, company_id=_company_id(request))
        content = build_sales_xlsx(context=context, filters=_sales_filters(request))
        return _download_response(
            content,
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            filename=f"reporte_ventas_{context.company.id}.xlsx",
        )
    except (ReportPermissionError, ReportValidationError) as exc:
        return _handle_error(exc)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def inventory_pdf_view(request):
    try:
        context = resolve_report_context(user=request.user, company_id=_company_id(request))
        content = build_inventory_pdf(context=context, filters=_inventory_filters(request))
        return _download_response(content, content_type="application/pdf", filename=f"reporte_inventario_{context.company.id}.pdf")
    except (ReportPermissionError, ReportValidationError) as exc:
        return _handle_error(exc)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def inventory_xls_view(request):
    try:
        context = resolve_report_context(user=request.user, company_id=_company_id(request))
        content = build_inventory_xlsx(context=context, filters=_inventory_filters(request))
        return _download_response(
            content,
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            filename=f"reporte_inventario_{context.company.id}.xlsx",
        )
    except (ReportPermissionError, ReportValidationError) as exc:
        return _handle_error(exc)
