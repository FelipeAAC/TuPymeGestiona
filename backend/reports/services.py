from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from io import BytesIO

from django.contrib.auth import get_user_model
from django.db.models import Q, QuerySet
from django.utils import timezone

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
import xlsxwriter

from catalog.models import Category
from inventory.models import InventoryStock
from organizations.models import (
    Branch,
    Company,
    CompanyMembership,
    RoleAssignment,
    Warehouse,
)
from sales.models import Sale


ADMIN_PERMISSION_CODE = "administration.manage"
INVENTORY_PERMISSION_CODE = "inventory.stocks.manage"


class ReportPermissionError(Exception):
    pass


class ReportValidationError(Exception):
    pass


@dataclass(frozen=True)
class ReportContext:
    membership: CompanyMembership
    company: Company
    can_sales: bool
    can_inventory: bool
    inventory_warehouse_ids: frozenset[int]


@dataclass(frozen=True)
class SalesFilters:
    date_from: date | None = None
    date_to: date | None = None
    branch_id: int | None = None
    seller_id: int | None = None


@dataclass(frozen=True)
class InventoryFilters:
    warehouse_id: int | None = None
    category_id: int | None = None
    stock_level: str = "ALL"
    critical_threshold: Decimal = Decimal("5.000")


def _active_assignments(*, user, company, permission_code):
    return RoleAssignment.objects.filter(
        membership__user=user,
        membership__company=company,
        membership__status=CompanyMembership.Status.ACTIVE,
        role__company=company,
        role__status="ACTIVE",
        role__permission_links__permission__code=permission_code,
    ).distinct()


def resolve_report_context(*, user, company_id: int) -> ReportContext:
    membership = (
        CompanyMembership.objects.filter(
            user=user,
            company_id=company_id,
            status=CompanyMembership.Status.ACTIVE,
        )
        .select_related("company")
        .first()
    )
    if membership is None:
        raise ReportPermissionError("No tienes acceso a esta empresa.")

    company = membership.company
    if getattr(user, "is_superuser", False):
        warehouse_ids = frozenset(
            Warehouse.objects.filter(company=company).values_list("id", flat=True)
        )
        return ReportContext(membership, company, True, True, warehouse_ids)

    admin_assignments = _active_assignments(
        user=user,
        company=company,
        permission_code=ADMIN_PERMISSION_CODE,
    )
    can_sales = admin_assignments.filter(branch__isnull=True).exists()

    inventory_assignments = _active_assignments(
        user=user,
        company=company,
        permission_code=INVENTORY_PERMISSION_CODE,
    )
    can_inventory = can_sales or inventory_assignments.exists()

    if can_sales:
        warehouse_ids = frozenset(
            Warehouse.objects.filter(company=company).values_list("id", flat=True)
        )
    elif inventory_assignments.filter(branch__isnull=True).exists():
        warehouse_ids = frozenset(
            Warehouse.objects.filter(company=company).values_list("id", flat=True)
        )
    else:
        branch_ids = inventory_assignments.values_list("branch_id", flat=True)
        warehouse_ids = frozenset(
            Warehouse.objects.filter(
                company=company,
                branch_id__in=branch_ids,
            ).values_list("id", flat=True)
        )

    return ReportContext(
        membership=membership,
        company=company,
        can_sales=can_sales,
        can_inventory=can_inventory,
        inventory_warehouse_ids=warehouse_ids,
    )


def report_options(*, user, company_id: int) -> dict:
    context = resolve_report_context(user=user, company_id=company_id)

    branches = []
    sellers = []
    if context.can_sales:
        branches = list(
            Branch.objects.filter(company=context.company, is_active=True)
            .order_by("name")
            .values("id", "code", "name")
        )
        User = get_user_model()
        seller_ids = (
            Sale.objects.filter(company=context.company)
            .values_list("created_by_id", flat=True)
            .distinct()
        )
        sellers = list(
            User.objects.filter(id__in=seller_ids)
            .order_by("username")
            .values("id", "username", "email")
        )

    warehouses = []
    categories = []
    if context.can_inventory:
        warehouses = list(
            Warehouse.objects.filter(
                company=context.company,
                id__in=context.inventory_warehouse_ids,
            )
            .select_related("branch")
            .order_by("name")
            .values("id", "code", "name", "branch_id", "branch__name")
        )
        category_ids = (
            InventoryStock.objects.filter(
                warehouse__company=context.company,
                warehouse_id__in=context.inventory_warehouse_ids,
            )
            .values_list("variant__product__category_id", flat=True)
            .distinct()
        )
        categories = list(
            Category.objects.filter(company=context.company, id__in=category_ids)
            .order_by("name")
            .values("id", "name")
        )

    return {
        "company": {"id": context.company.id, "name": context.company.name},
        "permissions": {
            "sales": context.can_sales,
            "inventory": context.can_inventory,
        },
        "branches": branches,
        "sellers": sellers,
        "warehouses": warehouses,
        "categories": categories,
    }


def sales_queryset(*, context: ReportContext, filters: SalesFilters) -> QuerySet[Sale]:
    if not context.can_sales:
        raise ReportPermissionError("No tienes permiso para generar reportes de ventas.")
    if filters.date_from and filters.date_to and filters.date_from > filters.date_to:
        raise ReportValidationError("La fecha desde no puede ser posterior a la fecha hasta.")

    queryset = (
        Sale.objects.filter(company=context.company)
        .select_related("branch", "order__customer", "created_by")
        .order_by("-created_at", "-number")
    )
    if filters.date_from:
        queryset = queryset.filter(created_at__date__gte=filters.date_from)
    if filters.date_to:
        queryset = queryset.filter(created_at__date__lte=filters.date_to)
    if filters.branch_id:
        if not Branch.objects.filter(company=context.company, id=filters.branch_id).exists():
            raise ReportValidationError("La sucursal no pertenece a la empresa activa.")
        queryset = queryset.filter(branch_id=filters.branch_id)
    if filters.seller_id:
        if not Sale.objects.filter(
            company=context.company,
            created_by_id=filters.seller_id,
        ).exists():
            raise ReportValidationError("El vendedor no pertenece al historial de ventas de la empresa.")
        queryset = queryset.filter(created_by_id=filters.seller_id)
    return queryset


def sales_report_data(*, context: ReportContext, filters: SalesFilters) -> dict:
    sales = list(sales_queryset(context=context, filters=filters))
    active_sales = [sale for sale in sales if sale.status != Sale.Status.CANCELLED]
    gross_total = sum((sale.total_amount for sale in active_sales), Decimal("0.00"))
    paid_total = sum((sale.paid_amount for sale in active_sales), Decimal("0.00"))
    balance_total = gross_total - paid_total

    rows = [
        {
            "id": sale.id,
            "number": sale.number,
            "date": timezone.localtime(sale.created_at).date().isoformat(),
            "branch": sale.branch.name,
            "branch_code": sale.branch.code,
            "seller": sale.created_by.get_full_name().strip() or sale.created_by.username,
            "seller_username": sale.created_by.username,
            "customer": sale.order.customer.name,
            "customer_code": sale.order.customer.code,
            "status": sale.status,
            "total_amount": str(sale.total_amount),
            "paid_amount": str(sale.paid_amount),
            "balance": str(sale.balance),
        }
        for sale in sales
    ]
    return {
        "filters": _sales_filter_labels(context=context, filters=filters),
        "summary": {
            "records": len(sales),
            "active_sales": len(active_sales),
            "gross_total": str(gross_total),
            "paid_total": str(paid_total),
            "balance_total": str(balance_total),
        },
        "rows": rows,
    }


def inventory_queryset(*, context: ReportContext, filters: InventoryFilters) -> QuerySet[InventoryStock]:
    if not context.can_inventory:
        raise ReportPermissionError("No tienes permiso para generar reportes de inventario.")
    if filters.critical_threshold < 0:
        raise ReportValidationError("El umbral crítico no puede ser negativo.")

    queryset = (
        InventoryStock.objects.filter(
            warehouse__company=context.company,
            warehouse_id__in=context.inventory_warehouse_ids,
        )
        .select_related(
            "warehouse__branch",
            "variant__product__category",
            "variant__product__brand",
        )
        .order_by("warehouse__name", "variant__product__name", "variant__sku")
    )
    if filters.warehouse_id:
        if filters.warehouse_id not in context.inventory_warehouse_ids:
            raise ReportValidationError("La bodega no está dentro del alcance autorizado.")
        queryset = queryset.filter(warehouse_id=filters.warehouse_id)
    if filters.category_id:
        if not Category.objects.filter(
            company=context.company,
            id=filters.category_id,
        ).exists():
            raise ReportValidationError("La categoría no pertenece a la empresa activa.")
        queryset = queryset.filter(variant__product__category_id=filters.category_id)

    level = filters.stock_level.upper()
    if level == "OUT":
        queryset = queryset.filter(quantity=0)
    elif level == "CRITICAL":
        queryset = queryset.filter(quantity__gt=0, quantity__lte=filters.critical_threshold)
    elif level == "AVAILABLE":
        queryset = queryset.filter(quantity__gt=filters.critical_threshold)
    elif level != "ALL":
        raise ReportValidationError("El nivel de existencias no es válido.")
    return queryset


def inventory_report_data(*, context: ReportContext, filters: InventoryFilters) -> dict:
    stocks = list(inventory_queryset(context=context, filters=filters))
    total_units = sum((stock.quantity for stock in stocks), Decimal("0.000"))
    total_value = sum(
        ((stock.quantity * stock.variant.base_price).quantize(Decimal("0.01")) for stock in stocks),
        Decimal("0.00"),
    )
    critical_count = sum(
        1
        for stock in stocks
        if Decimal("0.000") < stock.quantity <= filters.critical_threshold
    )
    out_count = sum(1 for stock in stocks if stock.quantity == 0)

    rows = []
    for stock in stocks:
        if stock.quantity == 0:
            stock_level = "OUT"
        elif stock.quantity <= filters.critical_threshold:
            stock_level = "CRITICAL"
        else:
            stock_level = "AVAILABLE"
        rows.append(
            {
                "id": stock.id,
                "warehouse": stock.warehouse.name,
                "warehouse_code": stock.warehouse.code,
                "branch": stock.warehouse.branch.name if stock.warehouse.branch_id else "Empresa",
                "category": stock.variant.product.category.name,
                "product": stock.variant.product.name,
                "sku": stock.variant.sku,
                "quantity": str(stock.quantity),
                "unit_price": str(stock.variant.base_price),
                "reference_value": str(
                    (stock.quantity * stock.variant.base_price).quantize(Decimal("0.01"))
                ),
                "stock_level": stock_level,
            }
        )

    return {
        "filters": _inventory_filter_labels(context=context, filters=filters),
        "summary": {
            "records": len(stocks),
            "total_units": str(total_units),
            "reference_value": str(total_value),
            "critical_count": critical_count,
            "out_count": out_count,
            "critical_threshold": str(filters.critical_threshold),
        },
        "valuation_note": (
            "La valorización usa el precio base vigente de cada variante como valor referencial; "
            "el modelo actual no contiene costo contable de adquisición."
        ),
        "rows": rows,
    }


def _sales_filter_labels(*, context, filters):
    branch = "Todas"
    if filters.branch_id:
        branch = Branch.objects.get(company=context.company, id=filters.branch_id).name
    seller = "Todos"
    if filters.seller_id:
        User = get_user_model()
        user = User.objects.get(id=filters.seller_id)
        seller = user.get_full_name().strip() or user.username
    return {
        "date_from": filters.date_from.isoformat() if filters.date_from else "Sin límite",
        "date_to": filters.date_to.isoformat() if filters.date_to else "Sin límite",
        "branch": branch,
        "seller": seller,
    }


def _inventory_filter_labels(*, context, filters):
    warehouse = "Todas"
    if filters.warehouse_id:
        warehouse = Warehouse.objects.get(id=filters.warehouse_id).name
    category = "Todas"
    if filters.category_id:
        category = Category.objects.get(id=filters.category_id).name
    level_labels = {
        "ALL": "Todos",
        "OUT": "Sin stock",
        "CRITICAL": "Crítico",
        "AVAILABLE": "Disponible",
    }
    return {
        "warehouse": warehouse,
        "category": category,
        "stock_level": level_labels[filters.stock_level.upper()],
        "critical_threshold": str(filters.critical_threshold),
    }


def _money(value):
    return f"${Decimal(value):,.0f}".replace(",", ".")


def build_sales_pdf(*, context: ReportContext, filters: SalesFilters) -> bytes:
    data = sales_report_data(context=context, filters=filters)
    if not data["rows"]:
        raise ReportValidationError("No se encontraron transacciones para exportar.")
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        rightMargin=12 * mm,
        leftMargin=12 * mm,
        topMargin=12 * mm,
        bottomMargin=12 * mm,
        title="Reporte de ventas",
    )
    styles = getSampleStyleSheet()
    small = ParagraphStyle("small", parent=styles["BodyText"], fontSize=7.5, leading=9, alignment=TA_LEFT)
    story = [
        Paragraph(f"Reporte de ventas · {context.company.name}", styles["Title"]),
        Paragraph(
            f"Fechas: {data['filters']['date_from']} a {data['filters']['date_to']} · "
            f"Sucursal: {data['filters']['branch']} · Vendedor: {data['filters']['seller']}",
            styles["BodyText"],
        ),
        Spacer(1, 5 * mm),
        Paragraph(
            f"Registros: {data['summary']['records']} · Ventas vigentes: {data['summary']['active_sales']} · "
            f"Total: {_money(data['summary']['gross_total'])} · Abonado: {_money(data['summary']['paid_total'])} · "
            f"Saldo: {_money(data['summary']['balance_total'])}",
            styles["BodyText"],
        ),
        Spacer(1, 4 * mm),
    ]
    table_data = [["Venta", "Fecha", "Sucursal", "Vendedor", "Cliente", "Estado", "Total", "Abonado", "Saldo"]]
    for row in data["rows"]:
        table_data.append([
            f"#{row['number']}", row["date"], row["branch"], row["seller"], row["customer"], row["status"],
            _money(row["total_amount"]), _money(row["paid_amount"]), _money(row["balance"]),
        ])
    table = Table(table_data, repeatRows=1, colWidths=[15*mm, 21*mm, 31*mm, 31*mm, 42*mm, 23*mm, 23*mm, 23*mm, 23*mm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#2F75B5")),
        ("TEXTCOLOR", (0,0), (-1,0), colors.white),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE", (0,0), (-1,-1), 7.2),
        ("GRID", (0,0), (-1,-1), 0.3, colors.HexColor("#D0D5DD")),
        ("VALIGN", (0,0), (-1,-1), "TOP"),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#F7F9FC")]),
        ("ALIGN", (6,1), (-1,-1), "RIGHT"),
        ("LEFTPADDING", (0,0), (-1,-1), 3), ("RIGHTPADDING", (0,0), (-1,-1), 3),
        ("TOPPADDING", (0,0), (-1,-1), 3), ("BOTTOMPADDING", (0,0), (-1,-1), 3),
    ]))
    story.append(table)
    doc.build(story)
    return buffer.getvalue()


def build_inventory_pdf(*, context: ReportContext, filters: InventoryFilters) -> bytes:
    data = inventory_report_data(context=context, filters=filters)
    if not data["rows"]:
        raise ReportValidationError("No se encontraron productos para exportar.")
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        rightMargin=12 * mm,
        leftMargin=12 * mm,
        topMargin=12 * mm,
        bottomMargin=12 * mm,
        title="Reporte de inventario",
    )
    styles = getSampleStyleSheet()
    story = [
        Paragraph(f"Reporte de inventario · {context.company.name}", styles["Title"]),
        Paragraph(
            f"Bodega: {data['filters']['warehouse']} · Categoría: {data['filters']['category']} · "
            f"Nivel: {data['filters']['stock_level']} · Umbral crítico: {data['filters']['critical_threshold']}",
            styles["BodyText"],
        ),
        Spacer(1, 4 * mm),
        Paragraph(
            f"Registros: {data['summary']['records']} · Unidades: {data['summary']['total_units']} · "
            f"Valor referencial: {_money(data['summary']['reference_value'])} · "
            f"Críticos: {data['summary']['critical_count']} · Sin stock: {data['summary']['out_count']}",
            styles["BodyText"],
        ),
        Paragraph(data["valuation_note"], styles["Italic"]),
        Spacer(1, 4 * mm),
    ]
    table_data = [["Bodega", "Sucursal", "Categoría", "Producto", "SKU", "Cantidad", "Precio base", "Valor ref.", "Nivel"]]
    for row in data["rows"]:
        table_data.append([
            row["warehouse"], row["branch"], row["category"], row["product"], row["sku"], row["quantity"],
            _money(row["unit_price"]), _money(row["reference_value"]), row["stock_level"],
        ])
    table = Table(table_data, repeatRows=1, colWidths=[30*mm, 28*mm, 30*mm, 42*mm, 28*mm, 22*mm, 24*mm, 25*mm, 24*mm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#2F75B5")),
        ("TEXTCOLOR", (0,0), (-1,0), colors.white),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE", (0,0), (-1,-1), 7.1),
        ("GRID", (0,0), (-1,-1), 0.3, colors.HexColor("#D0D5DD")),
        ("VALIGN", (0,0), (-1,-1), "TOP"),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#F7F9FC")]),
        ("ALIGN", (5,1), (7,-1), "RIGHT"),
        ("LEFTPADDING", (0,0), (-1,-1), 3), ("RIGHTPADDING", (0,0), (-1,-1), 3),
        ("TOPPADDING", (0,0), (-1,-1), 3), ("BOTTOMPADDING", (0,0), (-1,-1), 3),
    ]))
    story.append(table)
    doc.build(story)
    return buffer.getvalue()


def _xlsx_workbook():
    buffer = BytesIO()
    workbook = xlsxwriter.Workbook(buffer, {"in_memory": True})
    return buffer, workbook


def build_sales_xlsx(*, context: ReportContext, filters: SalesFilters) -> bytes:
    data = sales_report_data(context=context, filters=filters)
    if not data["rows"]:
        raise ReportValidationError("No se encontraron transacciones para exportar.")
    buffer, workbook = _xlsx_workbook()
    sheet = workbook.add_worksheet("Ventas")
    title_fmt = workbook.add_format({"bold": True, "font_size": 16, "font_color": "#15233C"})
    label_fmt = workbook.add_format({"bold": True, "font_color": "#475467"})
    header_fmt = workbook.add_format({"bold": True, "bg_color": "#2F75B5", "font_color": "#FFFFFF", "border": 1})
    text_fmt = workbook.add_format({"border": 1, "border_color": "#D0D5DD"})
    money_fmt = workbook.add_format({"border": 1, "border_color": "#D0D5DD", "num_format": '$#,##0'})
    sheet.write("A1", f"Reporte de ventas · {context.company.name}", title_fmt)
    sheet.write("A3", "Fecha desde", label_fmt); sheet.write("B3", data["filters"]["date_from"])
    sheet.write("C3", "Fecha hasta", label_fmt); sheet.write("D3", data["filters"]["date_to"])
    sheet.write("E3", "Sucursal", label_fmt); sheet.write("F3", data["filters"]["branch"])
    sheet.write("G3", "Vendedor", label_fmt); sheet.write("H3", data["filters"]["seller"])
    sheet.write("A4", "Registros", label_fmt); sheet.write_number("B4", data["summary"]["records"])
    sheet.write("C4", "Total", label_fmt); sheet.write_number("D4", float(data["summary"]["gross_total"]), money_fmt)
    sheet.write("E4", "Abonado", label_fmt); sheet.write_number("F4", float(data["summary"]["paid_total"]), money_fmt)
    sheet.write("G4", "Saldo", label_fmt); sheet.write_number("H4", float(data["summary"]["balance_total"]), money_fmt)
    headers = ["Venta", "Fecha", "Sucursal", "Vendedor", "Cliente", "Estado", "Total", "Abonado", "Saldo"]
    for col, header in enumerate(headers):
        sheet.write(6, col, header, header_fmt)
    for idx, row in enumerate(data["rows"], start=7):
        values = [f"#{row['number']}", row["date"], row["branch"], row["seller"], row["customer"], row["status"]]
        for col, value in enumerate(values):
            sheet.write(idx, col, value, text_fmt)
        sheet.write_number(idx, 6, float(row["total_amount"]), money_fmt)
        sheet.write_number(idx, 7, float(row["paid_amount"]), money_fmt)
        sheet.write_number(idx, 8, float(row["balance"]), money_fmt)
    sheet.freeze_panes(7, 0)
    sheet.autofilter(6, 0, 6 + len(data["rows"]), len(headers)-1)
    sheet.set_column("A:A", 11); sheet.set_column("B:B", 12); sheet.set_column("C:E", 24)
    sheet.set_column("F:F", 14); sheet.set_column("G:I", 14)
    workbook.close()
    return buffer.getvalue()


def build_inventory_xlsx(*, context: ReportContext, filters: InventoryFilters) -> bytes:
    data = inventory_report_data(context=context, filters=filters)
    if not data["rows"]:
        raise ReportValidationError("No se encontraron productos para exportar.")
    buffer, workbook = _xlsx_workbook()
    sheet = workbook.add_worksheet("Inventario")
    title_fmt = workbook.add_format({"bold": True, "font_size": 16, "font_color": "#15233C"})
    label_fmt = workbook.add_format({"bold": True, "font_color": "#475467"})
    note_fmt = workbook.add_format({"italic": True, "font_color": "#667085", "text_wrap": True})
    header_fmt = workbook.add_format({"bold": True, "bg_color": "#2F75B5", "font_color": "#FFFFFF", "border": 1})
    text_fmt = workbook.add_format({"border": 1, "border_color": "#D0D5DD"})
    qty_fmt = workbook.add_format({"border": 1, "border_color": "#D0D5DD", "num_format": '0.000'})
    money_fmt = workbook.add_format({"border": 1, "border_color": "#D0D5DD", "num_format": '$#,##0'})
    sheet.write("A1", f"Reporte de inventario · {context.company.name}", title_fmt)
    sheet.write("A3", "Bodega", label_fmt); sheet.write("B3", data["filters"]["warehouse"])
    sheet.write("C3", "Categoría", label_fmt); sheet.write("D3", data["filters"]["category"])
    sheet.write("E3", "Nivel", label_fmt); sheet.write("F3", data["filters"]["stock_level"])
    sheet.write("G3", "Umbral", label_fmt); sheet.write_number("H3", float(data["summary"]["critical_threshold"]), qty_fmt)
    sheet.write("A4", "Registros", label_fmt); sheet.write_number("B4", data["summary"]["records"])
    sheet.write("C4", "Unidades", label_fmt); sheet.write_number("D4", float(data["summary"]["total_units"]), qty_fmt)
    sheet.write("E4", "Valor ref.", label_fmt); sheet.write_number("F4", float(data["summary"]["reference_value"]), money_fmt)
    sheet.write("G4", "Críticos / sin stock", label_fmt); sheet.write("H4", f"{data['summary']['critical_count']} / {data['summary']['out_count']}")
    sheet.merge_range("A5:I5", data["valuation_note"], note_fmt)
    headers = ["Bodega", "Sucursal", "Categoría", "Producto", "SKU", "Cantidad", "Precio base", "Valor referencial", "Nivel"]
    for col, header in enumerate(headers):
        sheet.write(6, col, header, header_fmt)
    for idx, row in enumerate(data["rows"], start=7):
        values = [row["warehouse"], row["branch"], row["category"], row["product"], row["sku"]]
        for col, value in enumerate(values):
            sheet.write(idx, col, value, text_fmt)
        sheet.write_number(idx, 5, float(row["quantity"]), qty_fmt)
        sheet.write_number(idx, 6, float(row["unit_price"]), money_fmt)
        sheet.write_number(idx, 7, float(row["reference_value"]), money_fmt)
        sheet.write(idx, 8, row["stock_level"], text_fmt)
    sheet.freeze_panes(7, 0)
    sheet.autofilter(6, 0, 6 + len(data["rows"]), len(headers)-1)
    sheet.set_column("A:D", 24); sheet.set_column("E:E", 18); sheet.set_column("F:H", 16); sheet.set_column("I:I", 14)
    workbook.close()
    return buffer.getvalue()
