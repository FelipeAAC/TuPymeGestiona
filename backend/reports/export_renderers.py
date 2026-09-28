"""Render already authorized report data as PDF or XLSX.

Permission checks, database queries and empty-result validation live in services.
Text from company records is always literal: it is neither Excel code nor PDF markup.
"""
from __future__ import annotations

from decimal import Decimal
from html import escape
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
import xlsxwriter


def _literal_paragraph(value, style):
    # Escape once, at the rendering boundary, including names that resemble tags.
    return Paragraph(escape(str(value), quote=False), style)


def _money(value):
    return f"${Decimal(value):,.0f}".replace(",", ".")


def _sale_label(row):
    origin = row.get("origin")
    if origin == "POS":
        return f"#{row['number']} · POS"
    if origin == "ORDER":
        return f"#{row['number']} · Pedido"
    return f"#{row['number']}"


def sales_pdf(*, company_name: str, data: dict) -> bytes:
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
    cell_style = ParagraphStyle("ReportCell", parent=styles["BodyText"], fontSize=7.2, leading=9, alignment=TA_LEFT)
    story = [
        _literal_paragraph(f"Reporte de ventas · {company_name}", styles["Title"]),
        _literal_paragraph(
            f"Fechas: {data['filters']['date_from']} a {data['filters']['date_to']} · "
            f"Sucursal: {data['filters']['branch']} · Vendedor: {data['filters']['seller']}",
            styles["BodyText"],
        ),
        Spacer(1, 5 * mm),
        _literal_paragraph(
            f"Registros: {data['summary']['records']} · Ventas vigentes: {data['summary']['active_sales']} · "
            f"Total: {_money(data['summary']['gross_total'])} · Abonado: {_money(data['summary']['paid_total'])} · "
            f"Saldo: {_money(data['summary']['balance_total'])}",
            styles["BodyText"],
        ),
        Spacer(1, 4 * mm),
    ]
    table_data = [["Venta", "Fecha", "Sucursal", "Vendedor", "Cliente", "Estado", "Total", "Abonado", "Saldo"]]
    for row in data["rows"]:
        text_values = [_sale_label(row), row["date"], row["branch"], row["seller"], row["customer"], row["status"]]
        table_data.append(
            [_literal_paragraph(value, cell_style) for value in text_values]
            + [_money(row["total_amount"]), _money(row["paid_amount"]), _money(row["balance"])]
        )
    table = Table(table_data, repeatRows=1, colWidths=[15*mm, 21*mm, 31*mm, 31*mm, 42*mm, 29*mm, 23*mm, 23*mm, 23*mm])
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


def inventory_pdf(*, company_name: str, data: dict) -> bytes:
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
    cell_style = ParagraphStyle("ReportCell", parent=styles["BodyText"], fontSize=7.1, leading=9, alignment=TA_LEFT)
    story = [
        _literal_paragraph(f"Reporte de inventario · {company_name}", styles["Title"]),
        _literal_paragraph(
            f"Bodega: {data['filters']['warehouse']} · Categoría: {data['filters']['category']} · "
            f"Nivel: {data['filters']['stock_level']} · Umbral crítico: {data['filters']['critical_threshold']}",
            styles["BodyText"],
        ),
        Spacer(1, 4 * mm),
        _literal_paragraph(
            f"Registros: {data['summary']['records']} · Unidades: {data['summary']['total_units']} · "
            f"Valor referencial: {_money(data['summary']['reference_value'])} · "
            f"Críticos: {data['summary']['critical_count']} · Sin stock: {data['summary']['out_count']}",
            styles["BodyText"],
        ),
        _literal_paragraph(data["valuation_note"], styles["Italic"]),
        Spacer(1, 4 * mm),
    ]
    table_data = [["Bodega", "Sucursal", "Categoría", "Producto", "SKU", "Cantidad", "Precio base", "Valor ref.", "Nivel"]]
    for row in data["rows"]:
        text_values = [row["warehouse"], row["branch"], row["category"], row["product"], row["sku"]]
        table_data.append(
            [_literal_paragraph(value, cell_style) for value in text_values]
            + [row["quantity"], _money(row["unit_price"]), _money(row["reference_value"]),
               _literal_paragraph(row["stock_level"], cell_style)]
        )
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
    workbook = xlsxwriter.Workbook(buffer, {
        "in_memory": True,
        "strings_to_formulas": False,
        "strings_to_urls": False,
    })
    return buffer, workbook


def sales_xlsx(*, company_name: str, data: dict) -> bytes:
    buffer, workbook = _xlsx_workbook()
    sheet = workbook.add_worksheet("Ventas")
    title_fmt = workbook.add_format({"bold": True, "font_size": 16, "font_color": "#15233C"})
    label_fmt = workbook.add_format({"bold": True, "font_color": "#475467"})
    header_fmt = workbook.add_format({"bold": True, "bg_color": "#2F75B5", "font_color": "#FFFFFF", "border": 1})
    text_fmt = workbook.add_format({"border": 1, "border_color": "#D0D5DD"})
    money_fmt = workbook.add_format({"border": 1, "border_color": "#D0D5DD", "num_format": '$#,##0'})
    sheet.write_string("A1", f"Reporte de ventas · {company_name}", title_fmt)
    sheet.write_string("A3", "Fecha desde", label_fmt); sheet.write_string("B3", data["filters"]["date_from"])
    sheet.write_string("C3", "Fecha hasta", label_fmt); sheet.write_string("D3", data["filters"]["date_to"])
    sheet.write_string("E3", "Sucursal", label_fmt); sheet.write_string("F3", data["filters"]["branch"])
    sheet.write_string("G3", "Vendedor", label_fmt); sheet.write_string("H3", data["filters"]["seller"])
    sheet.write_string("A4", "Registros", label_fmt); sheet.write_number("B4", data["summary"]["records"])
    sheet.write_string("C4", "Total", label_fmt); sheet.write_number("D4", float(data["summary"]["gross_total"]), money_fmt)
    sheet.write_string("E4", "Abonado", label_fmt); sheet.write_number("F4", float(data["summary"]["paid_total"]), money_fmt)
    sheet.write_string("G4", "Saldo", label_fmt); sheet.write_number("H4", float(data["summary"]["balance_total"]), money_fmt)
    headers = ["Venta", "Fecha", "Sucursal", "Vendedor", "Cliente", "Estado", "Total", "Abonado", "Saldo"]
    for col, header in enumerate(headers):
        sheet.write_string(6, col, header, header_fmt)
    for idx, row in enumerate(data["rows"], start=7):
        values = [_sale_label(row), row["date"], row["branch"], row["seller"], row["customer"], row["status"]]
        for col, value in enumerate(values):
            sheet.write_string(idx, col, value, text_fmt)
        sheet.write_number(idx, 6, float(row["total_amount"]), money_fmt)
        sheet.write_number(idx, 7, float(row["paid_amount"]), money_fmt)
        sheet.write_number(idx, 8, float(row["balance"]), money_fmt)
    sheet.freeze_panes(7, 0)
    sheet.autofilter(6, 0, 6 + len(data["rows"]), len(headers)-1)
    sheet.set_column("A:A", 11); sheet.set_column("B:B", 12); sheet.set_column("C:E", 24)
    sheet.set_column("F:F", 14); sheet.set_column("G:I", 14)
    workbook.close()
    return buffer.getvalue()


def inventory_xlsx(*, company_name: str, data: dict) -> bytes:
    buffer, workbook = _xlsx_workbook()
    sheet = workbook.add_worksheet("Inventario")
    title_fmt = workbook.add_format({"bold": True, "font_size": 16, "font_color": "#15233C"})
    label_fmt = workbook.add_format({"bold": True, "font_color": "#475467"})
    note_fmt = workbook.add_format({"italic": True, "font_color": "#667085", "text_wrap": True})
    header_fmt = workbook.add_format({"bold": True, "bg_color": "#2F75B5", "font_color": "#FFFFFF", "border": 1})
    text_fmt = workbook.add_format({"border": 1, "border_color": "#D0D5DD"})
    qty_fmt = workbook.add_format({"border": 1, "border_color": "#D0D5DD", "num_format": '0.000'})
    money_fmt = workbook.add_format({"border": 1, "border_color": "#D0D5DD", "num_format": '$#,##0'})
    sheet.write_string("A1", f"Reporte de inventario · {company_name}", title_fmt)
    sheet.write_string("A3", "Bodega", label_fmt); sheet.write_string("B3", data["filters"]["warehouse"])
    sheet.write_string("C3", "Categoría", label_fmt); sheet.write_string("D3", data["filters"]["category"])
    sheet.write_string("E3", "Nivel", label_fmt); sheet.write_string("F3", data["filters"]["stock_level"])
    sheet.write_string("G3", "Umbral", label_fmt); sheet.write_number("H3", float(data["summary"]["critical_threshold"]), qty_fmt)
    sheet.write_string("A4", "Registros", label_fmt); sheet.write_number("B4", data["summary"]["records"])
    sheet.write_string("C4", "Unidades", label_fmt); sheet.write_number("D4", float(data["summary"]["total_units"]), qty_fmt)
    sheet.write_string("E4", "Valor ref.", label_fmt); sheet.write_number("F4", float(data["summary"]["reference_value"]), money_fmt)
    sheet.write_string("G4", "Críticos / sin stock", label_fmt); sheet.write_string("H4", f"{data['summary']['critical_count']} / {data['summary']['out_count']}")
    sheet.merge_range("A5:I5", data["valuation_note"], note_fmt)
    headers = ["Bodega", "Sucursal", "Categoría", "Producto", "SKU", "Cantidad", "Precio base", "Valor referencial", "Nivel"]
    for col, header in enumerate(headers):
        sheet.write_string(6, col, header, header_fmt)
    for idx, row in enumerate(data["rows"], start=7):
        values = [row["warehouse"], row["branch"], row["category"], row["product"], row["sku"]]
        for col, value in enumerate(values):
            sheet.write_string(idx, col, value, text_fmt)
        sheet.write_number(idx, 5, float(row["quantity"]), qty_fmt)
        sheet.write_number(idx, 6, float(row["unit_price"]), money_fmt)
        sheet.write_number(idx, 7, float(row["reference_value"]), money_fmt)
        sheet.write_string(idx, 8, row["stock_level"], text_fmt)
    sheet.freeze_panes(7, 0)
    sheet.autofilter(6, 0, 6 + len(data["rows"]), len(headers)-1)
    sheet.set_column("A:D", 24); sheet.set_column("E:E", 18); sheet.set_column("F:H", 16); sheet.set_column("I:I", 14)
    workbook.close()
    return buffer.getvalue()
