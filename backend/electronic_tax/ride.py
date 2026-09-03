import hashlib
import io
from copy import deepcopy
from decimal import Decimal

from django.db import transaction
from lxml import etree
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader

from .models import ElectronicTaxArtifact, ElectronicTaxDocument, ElectronicTaxEvent, TaxCompanyProfile
from .services import DTEInvalidStateError, DTEProviderNotConfiguredError, DTEValidationError, record_event
from .sii_adapter import XML_ENCODING, _decrypt, _encrypt, _safe_xml_parser


_DOCUMENT_NAMES = {
    ElectronicTaxDocument.TypeCode.INVOICE: "FACTURA ELECTRONICA",
    ElectronicTaxDocument.TypeCode.EXEMPT_INVOICE: "FACTURA NO AFECTA O EXENTA ELECTRONICA",
    ElectronicTaxDocument.TypeCode.DEBIT_NOTE: "NOTA DE DEBITO ELECTRONICA",
    ElectronicTaxDocument.TypeCode.CREDIT_NOTE: "NOTA DE CREDITO ELECTRONICA",
}

_PRINTABLE_STATES = {
    ElectronicTaxDocument.State.SIGNED,
    ElectronicTaxDocument.State.SUBMITTED,
    ElectronicTaxDocument.State.PROCESSING,
    ElectronicTaxDocument.State.ACCEPTED,
    ElectronicTaxDocument.State.ACCEPTED_WITH_REPAIR,
    ElectronicTaxDocument.State.REJECTED,
    ElectronicTaxDocument.State.CANCELLED_BY_REFERENCE,
}


def _signed_envelope(document):
    try:
        artifact = document.artifacts.get(kind=ElectronicTaxArtifact.Kind.SIGNED_ENVELOPE)
    except ElectronicTaxArtifact.DoesNotExist as error:
        raise DTEInvalidStateError("El DTE no tiene un EnvioDTE firmado para generar RIDE.") from error
    return _decrypt(bytes(artifact.nonce), bytes(artifact.encrypted_payload))


def _extract_dte_and_ted(document):
    payload = _signed_envelope(document)
    try:
        root = etree.fromstring(payload, parser=_safe_xml_parser())
    except Exception as error:
        raise DTEValidationError("El EnvioDTE firmado persistido no es XML valido.") from error
    dtes = root.xpath("//*[local-name()='DTE']")
    if len(dtes) != 1:
        raise DTEValidationError("El EnvioDTE persistido debe contener exactamente un DTE.")
    ted_nodes = dtes[0].xpath(".//*[local-name()='TED']")
    if len(ted_nodes) != 1:
        raise DTEValidationError("El DTE firmado no contiene un TED unico.")
    return deepcopy(dtes[0]), deepcopy(ted_nodes[0])


def _strip_namespaces(element):
    node = deepcopy(element)
    for item in node.iter():
        if isinstance(item.tag, str):
            item.tag = etree.QName(item).localname
        for key in list(item.attrib):
            if key.startswith("{"):
                value = item.attrib.pop(key)
                item.attrib[etree.QName(key).localname] = value
    etree.cleanup_namespaces(node)
    return node


def ted_payload_for_pdf417(document):
    _, ted = _extract_dte_and_ted(document)
    # El PDF417 representa el TED como cadena XML compacta; se elimina la
    # declaracion de namespace heredada para reproducir el formato del anexo SII.
    compact = etree.tostring(
        _strip_namespaces(ted),
        encoding=XML_ENCODING,
        xml_declaration=False,
        pretty_print=False,
        with_tail=False,
    )
    if b"\n" in compact or b"\r" in compact:
        compact = compact.replace(b"\r", b"").replace(b"\n", b"")
    return compact


def _render_pdf417_png(ted_bytes):
    try:
        from pdf417gen import encode, render_image
    except ImportError as error:
        raise DTEProviderNotConfiguredError(
            "Falta pdf417gen para generar el timbre PDF417 del RIDE."
        ) from error

    # Resolucion logica: 300 DPI. scale=2 equivale a X Dim ~= 6.67 mils;
    # ratio=3 respeta Y:X 3:1. padding=75 px conserva quiet zone de 0,25".
    candidates = []
    for columns in range(4, 21):
        try:
            codes = encode(ted_bytes, columns=columns, security_level=5)
            image = render_image(codes, scale=2, ratio=3, padding=75)
        except Exception:
            continue
        width_px, height_px = image.size
        width_cm = width_px / 300.0 * 2.54
        height_cm = height_px / 300.0 * 2.54
        if 4.5 <= width_cm <= 9.0 and 2.0 <= height_cm <= 4.0:
            target_ratio = 8.0 / 3.0
            score = abs((width_cm / height_cm) - target_ratio)
            candidates.append((score, image, width_cm, height_cm))
    if not candidates:
        raise DTEValidationError(
            "El TED no pudo representarse como PDF417 dentro de las dimensiones SII configuradas."
        )
    _, image, width_cm, height_cm = min(candidates, key=lambda item: item[0])
    output = io.BytesIO()
    image.save(output, format="PNG", dpi=(300, 300))
    return output.getvalue(), width_cm * cm, height_cm * cm


def _money(value):
    return f"$ {int(value):,}".replace(",", ".")


def _short(value, limit):
    text = " ".join(str(value or "").split())
    return text if len(text) <= limit else text[: max(0, limit - 1)] + "…"


def _draw_tax_box(pdf, document, profile):
    page_width, page_height = A4
    x = page_width - 8.0 * cm
    y = page_height - 4.0 * cm
    width = 7.2 * cm
    height = 3.0 * cm
    pdf.setLineWidth(1.1)
    pdf.rect(x, y, width, height)
    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawCentredString(x + width / 2, y + height - 0.55 * cm, f"R.U.T.: {document.issuer_rut}")
    pdf.setFont("Helvetica-Bold", 9)
    pdf.drawCentredString(x + width / 2, y + height - 1.35 * cm, _DOCUMENT_NAMES[document.type_code])
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawCentredString(x + width / 2, y + 0.55 * cm, f"N° {document.folio}")
    pdf.setFont("Helvetica", 8)
    pdf.drawCentredString(x + width / 2, y - 0.4 * cm, f"S.I.I. {profile.sii_regional_office}")


def _draw_header(pdf, document, profile, *, cedible, page_number, total_pages):
    page_width, page_height = A4
    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(1.5 * cm, page_height - 1.5 * cm, _short(document.issuer_legal_name, 60))
    pdf.setFont("Helvetica", 8.5)
    pdf.drawString(1.5 * cm, page_height - 2.0 * cm, _short(document.issuer_business_activity, 85))
    pdf.drawString(1.5 * cm, page_height - 2.45 * cm, _short(document.issuer_address, 85))
    pdf.drawString(1.5 * cm, page_height - 2.9 * cm, _short(f"{document.issuer_commune} {document.issuer_city}", 85))
    _draw_tax_box(pdf, document, profile)

    if cedible:
        pdf.setFont("Helvetica-Bold", 9)
        pdf.drawRightString(page_width - 1.5 * cm, page_height - 4.8 * cm, "CEDIBLE")
    pdf.setFont("Helvetica", 7.5)
    pdf.drawRightString(page_width - 1.5 * cm, page_height - 5.2 * cm, f"Pagina {page_number} de {total_pages}")

    y = page_height - 5.7 * cm
    pdf.setLineWidth(0.6)
    pdf.rect(1.5 * cm, y - 2.25 * cm, page_width - 3 * cm, 2.25 * cm)
    pdf.setFont("Helvetica-Bold", 8)
    pdf.drawString(1.75 * cm, y - 0.45 * cm, "RECEPTOR")
    pdf.setFont("Helvetica", 8)
    pdf.drawString(3.7 * cm, y - 0.45 * cm, _short(document.receiver_legal_name, 75))
    pdf.drawString(1.75 * cm, y - 0.95 * cm, f"RUT: {document.receiver_rut}")
    pdf.drawString(6.5 * cm, y - 0.95 * cm, _short(f"Giro: {document.receiver_business_activity}", 65))
    pdf.drawString(1.75 * cm, y - 1.45 * cm, _short(f"Direccion: {document.receiver_address}", 75))
    pdf.drawString(1.75 * cm, y - 1.95 * cm, _short(f"Comuna/Ciudad: {document.receiver_commune} {document.receiver_city}", 75))
    pdf.drawRightString(page_width - 1.75 * cm, y - 1.95 * cm, f"Fecha emision: {document.issue_date.isoformat()}")
    return y - 2.65 * cm


def _draw_table_header(pdf, y):
    page_width, _ = A4
    x0 = 1.5 * cm
    widths = [1.0, 2.2, 8.0, 2.0, 2.2, 2.4]
    labels = ["N°", "Codigo", "Descripcion", "Cant.", "P.Unit.", "Total"]
    pdf.setFont("Helvetica-Bold", 7.5)
    x = x0
    for width, label in zip(widths, labels):
        pdf.rect(x, y - 0.6 * cm, width * cm, 0.6 * cm)
        pdf.drawCentredString(x + width * cm / 2, y - 0.4 * cm, label)
        x += width * cm
    return y - 0.6 * cm


def _draw_line(pdf, line, y):
    x0 = 1.5 * cm
    values = [
        str(line.line_number),
        _short(line.sku, 16),
        _short(line.description, 52),
        format(line.quantity, "f").rstrip("0").rstrip("."),
        _money(line.unit_price),
        _money(line.total_amount),
    ]
    widths = [1.0, 2.2, 8.0, 2.0, 2.2, 2.4]
    pdf.setFont("Helvetica", 7.2)
    x = x0
    for index, (width, value) in enumerate(zip(widths, values)):
        pdf.rect(x, y - 0.52 * cm, width * cm, 0.52 * cm)
        if index in {3, 4, 5}:
            pdf.drawRightString(x + width * cm - 0.1 * cm, y - 0.35 * cm, value)
        else:
            pdf.drawString(x + 0.1 * cm, y - 0.35 * cm, value)
        x += width * cm
    return y - 0.52 * cm


def _draw_totals(pdf, document, y):
    page_width, _ = A4
    x = page_width - 8.0 * cm
    pdf.setFont("Helvetica", 8)
    rows = []
    if document.net_amount:
        rows.append(("Neto", document.net_amount))
    if document.exempt_amount:
        rows.append(("Exento", document.exempt_amount))
    if document.vat_amount:
        rows.append((f"IVA {int(Decimal(document.vat_rate))}%", document.vat_amount))
    rows.append(("TOTAL", document.total_amount))
    for label, value in rows:
        pdf.drawRightString(x + 2.8 * cm, y, label + ":")
        pdf.setFont("Helvetica-Bold" if label == "TOTAL" else "Helvetica", 8)
        pdf.drawRightString(page_width - 1.5 * cm, y, _money(value))
        pdf.setFont("Helvetica", 8)
        y -= 0.48 * cm
    return y


def _draw_references(pdf, document, y):
    refs = list(document.references.order_by("id"))
    if not refs:
        return y
    pdf.setFont("Helvetica-Bold", 7.5)
    pdf.drawString(1.5 * cm, y, "REFERENCIAS")
    y -= 0.4 * cm
    pdf.setFont("Helvetica", 7.2)
    for ref in refs[:4]:
        text = f"DTE {ref.referenced_type_code} Folio {ref.referenced_folio} - {ref.reference_date.isoformat()} - {ref.description}"
        pdf.drawString(1.5 * cm, y, _short(text, 115))
        y -= 0.38 * cm
    return y


def _draw_receipt_box(pdf, y):
    page_width, _ = A4
    height = 2.3 * cm
    pdf.setFont("Helvetica-Bold", 7.5)
    pdf.drawString(10.3 * cm, y, "ACUSE DE RECIBO - LEY 19.983")
    y -= 0.2 * cm
    pdf.rect(10.2 * cm, y - height, page_width - 11.7 * cm, height)
    pdf.setFont("Helvetica", 6.5)
    pdf.drawString(10.4 * cm, y - 0.45 * cm, "Nombre: ______________________________")
    pdf.drawString(10.4 * cm, y - 0.85 * cm, "RUT: _________________________________")
    pdf.drawString(10.4 * cm, y - 1.25 * cm, "Fecha/recinto: ________________________")
    pdf.drawString(10.4 * cm, y - 1.65 * cm, "Firma: ________________________________")
    pdf.setFont("Helvetica", 5.4)
    legend = "El acuse de recibo acredita que la entrega de mercaderias o servicio(s) prestado(s) ha(n) sido recibido(s)."
    pdf.drawString(10.4 * cm, y - 2.05 * cm, _short(legend, 95))


def _draw_timbre(pdf, document, profile, barcode_png, barcode_width, barcode_height, *, cedible):
    _, page_height = A4
    x = 1.5 * cm
    y = 1.65 * cm
    pdf.drawImage(
        ImageReader(io.BytesIO(barcode_png)),
        x,
        y,
        width=barcode_width,
        height=barcode_height,
        preserveAspectRatio=True,
        mask="auto",
    )
    text_y = y - 0.3 * cm
    pdf.setFont("Helvetica-Bold", 7)
    pdf.drawString(x, text_y, "Timbre electronico SII")
    pdf.setFont("Helvetica", 6.7)
    year = profile.sii_resolution_date.year
    pdf.drawString(x, text_y - 0.35 * cm, f"Res. {profile.sii_resolution_number} de {year} - Verifique documento: www.sii.cl")
    if cedible:
        pdf.setFont("Helvetica-Bold", 9)
        pdf.drawRightString(A4[0] - 1.5 * cm, 1.0 * cm, "CEDIBLE")


def render_ride_pdf(document):
    if document.state not in _PRINTABLE_STATES:
        raise DTEInvalidStateError("El RIDE solo puede generarse desde un DTE firmado o posterior.")
    if not document.folio or not document.issue_date:
        raise DTEInvalidStateError("El DTE requiere folio y fecha de emision para generar RIDE.")
    profile = TaxCompanyProfile.objects.filter(company=document.company, active=True).first()
    if profile is None:
        raise DTEValidationError("La empresa no tiene perfil tributario activo.")
    missing = []
    if not profile.sii_resolution_number:
        missing.append("sii_resolution_number")
    if not profile.sii_resolution_date:
        missing.append("sii_resolution_date")
    if not profile.sii_regional_office:
        missing.append("sii_regional_office")
    if missing:
        raise DTEValidationError("Faltan datos para RIDE: " + ", ".join(missing))

    ted_bytes = ted_payload_for_pdf417(document)
    barcode_png, barcode_width, barcode_height = _render_pdf417_png(ted_bytes)
    lines = list(document.lines.order_by("line_number", "id"))
    if not lines and document.type_code not in {
        ElectronicTaxDocument.TypeCode.CREDIT_NOTE,
        ElectronicTaxDocument.TypeCode.DEBIT_NOTE,
    }:
        raise DTEValidationError("El RIDE de factura requiere lineas de detalle.")

    pages_of_lines = [lines[index:index + 28] for index in range(0, len(lines), 28)] or [[]]
    copies = [False]
    if document.type_code in {
        ElectronicTaxDocument.TypeCode.INVOICE,
        ElectronicTaxDocument.TypeCode.EXEMPT_INVOICE,
    }:
        copies.append(True)

    output = io.BytesIO()
    pdf = canvas.Canvas(output, pagesize=A4, invariant=1, pageCompression=1)
    total_pages = len(pages_of_lines) * len(copies)
    absolute_page = 0
    for cedible in copies:
        for page_index, page_lines in enumerate(pages_of_lines):
            absolute_page += 1
            y = _draw_header(
                pdf,
                document,
                profile,
                cedible=cedible,
                page_number=absolute_page,
                total_pages=total_pages,
            )
            y = _draw_table_header(pdf, y)
            for line in page_lines:
                y = _draw_line(pdf, line, y)
            is_last_copy_page = page_index == len(pages_of_lines) - 1
            if is_last_copy_page:
                y -= 0.35 * cm
                y = _draw_references(pdf, document, y)
                _draw_totals(pdf, document, min(y - 0.2 * cm, 5.7 * cm))
                if cedible:
                    _draw_receipt_box(pdf, 5.5 * cm)
                _draw_timbre(
                    pdf,
                    document,
                    profile,
                    barcode_png,
                    barcode_width,
                    barcode_height,
                    cedible=cedible,
                )
            pdf.showPage()
    pdf.save()
    return output.getvalue()


@transaction.atomic
def get_or_create_ride(*, document, actor=None):
    existing = document.artifacts.filter(kind=ElectronicTaxArtifact.Kind.RIDE_PDF).first()
    if existing is not None:
        return _decrypt(bytes(existing.nonce), bytes(existing.encrypted_payload)), False
    payload = render_ride_pdf(document)
    digest = hashlib.sha256(payload).hexdigest()
    nonce, encrypted = _encrypt(payload)
    ElectronicTaxArtifact.objects.create(
        document=document,
        kind=ElectronicTaxArtifact.Kind.RIDE_PDF,
        content_hash=digest,
        nonce=nonce,
        encrypted_payload=encrypted,
    )
    if actor is not None:
        record_event(
            document=document,
            event_type=ElectronicTaxEvent.EventType.RIDE_GENERATED,
            actor=actor,
            metadata={"ride_hash": digest, "pages_include_cedible": document.type_code in {33, 34}},
        )
    return payload, True
