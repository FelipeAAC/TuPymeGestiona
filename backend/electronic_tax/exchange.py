import hashlib
from copy import deepcopy
from pathlib import Path

from django.conf import settings
from django.core.mail import EmailMessage
from django.db import transaction
from django.utils import timezone
from lxml import etree

from .models import (
    ElectronicTaxArtifact,
    ElectronicTaxDocument,
    ElectronicTaxEvent,
    ElectronicTaxExchange,
    IdempotencyRecord,
    TaxCompanyProfile,
)
from .ride import get_or_create_ride
from .services import (
    DTEIdempotencyConflictError,
    DTEInvalidStateError,
    DTEProviderNotConfiguredError,
    DTEValidationError,
    DTEVersionConflictError,
    normalize_rut,
    record_event,
)
from .sii_adapter import (
    SII_NS,
    XSI_NS,
    XML_ENCODING,
    _certificate_material,
    _decrypt,
    _encrypt,
    _safe_xml_parser,
    _text,
    _validate_xsd,
    _xml_signature,
)


_EXCHANGEABLE_STATES = {
    ElectronicTaxDocument.State.ACCEPTED,
    ElectronicTaxDocument.State.ACCEPTED_WITH_REPAIR,
    ElectronicTaxDocument.State.CANCELLED_BY_REFERENCE,
}


def _canonical_hash(payload):
    import json

    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")
    ).hexdigest()


def _idempotency_replay(*, document, operation, key, request_hash):
    clean_key = (key or "").strip()
    if not clean_key:
        raise DTEValidationError("Idempotency-Key es obligatorio.")
    record = IdempotencyRecord.objects.filter(
        company=document.company, operation=operation, key=clean_key
    ).first()
    if record is None:
        return clean_key, None
    if record.request_hash != request_hash:
        raise DTEIdempotencyConflictError(
            "La misma clave idempotente fue reutilizada con otro contenido."
        )
    return clean_key, record


def _signed_dte(document):
    try:
        artifact = document.artifacts.get(kind=ElectronicTaxArtifact.Kind.SIGNED_ENVELOPE)
    except ElectronicTaxArtifact.DoesNotExist as error:
        raise DTEInvalidStateError("No existe EnvioDTE firmado para intercambio con el receptor.") from error
    payload = _decrypt(bytes(artifact.nonce), bytes(artifact.encrypted_payload))
    try:
        root = etree.fromstring(payload, parser=_safe_xml_parser())
    except Exception as error:
        raise DTEValidationError("El EnvioDTE firmado persistido no es XML valido.") from error
    dtes = root.xpath("//*[local-name()='DTE']")
    if len(dtes) != 1:
        raise DTEValidationError("El EnvioDTE persistido debe contener exactamente un DTE.")
    return deepcopy(dtes[0])


def build_receiver_envelope(document):
    if document.state not in _EXCHANGEABLE_STATES:
        raise DTEInvalidStateError(
            "El intercambio al receptor solo se habilita para DTE aceptado, aceptado con reparo o posteriormente anulado por referencia."
        )
    if not document.receiver_tax_email:
        raise DTEValidationError("El snapshot fiscal no contiene correo tributario del receptor.")
    profile = TaxCompanyProfile.objects.filter(company=document.company, active=True).first()
    if profile is None or not profile.sii_resolution_number or not profile.sii_resolution_date:
        raise DTEValidationError("El perfil tributario del emisor no tiene resolucion SII completa.")

    private_key, certificate, _ = _certificate_material()
    dte = _signed_dte(document)
    envelope = etree.Element(
        etree.QName(SII_NS, "EnvioDTE"),
        nsmap={None: SII_NS, "xsi": XSI_NS},
        version="1.0",
    )
    envelope.set(etree.QName(XSI_NS, "schemaLocation"), f"{SII_NS} EnvioDTE_v10.xsd")
    set_dte = etree.SubElement(envelope, etree.QName(SII_NS, "SetDTE"), ID="SetDocReceiver")
    caratula = etree.SubElement(set_dte, etree.QName(SII_NS, "Caratula"), version="1.0")
    sender_rut = getattr(settings, "SII_SENDER_RUT", "").strip()
    if not sender_rut:
        raise DTEProviderNotConfiguredError("Falta SII_SENDER_RUT para firmar el intercambio.")
    _text(caratula, "RutEmisor", document.issuer_rut)
    _text(caratula, "RutEnvia", normalize_rut(sender_rut))
    _text(caratula, "RutReceptor", document.receiver_rut)
    _text(caratula, "FchResol", profile.sii_resolution_date.isoformat())
    _text(caratula, "NroResol", profile.sii_resolution_number)
    _text(caratula, "TmstFirmaEnv", timezone.localtime().strftime("%Y-%m-%dT%H:%M:%S"))
    subtotal = etree.SubElement(caratula, etree.QName(SII_NS, "SubTotDTE"))
    _text(subtotal, "TpoDTE", document.type_code)
    _text(subtotal, "NroDTE", 1)
    set_dte.append(dte)
    _xml_signature(
        envelope,
        reference_element=set_dte,
        reference_uri="#SetDocReceiver",
        private_key=private_key,
        certificate=certificate,
    )
    payload = etree.tostring(
        envelope,
        encoding=XML_ENCODING,
        xml_declaration=True,
        pretty_print=False,
    )
    _validate_xsd(payload)
    return payload


def _store_artifact(document, kind, payload):
    digest = hashlib.sha256(payload).hexdigest()
    nonce, encrypted = _encrypt(payload)
    ElectronicTaxArtifact.objects.update_or_create(
        document=document,
        kind=kind,
        defaults={"content_hash": digest, "nonce": nonce, "encrypted_payload": encrypted},
    )
    return digest


def get_or_create_receiver_envelope(document):
    existing = document.artifacts.filter(kind=ElectronicTaxArtifact.Kind.RECEIVER_ENVELOPE).first()
    if existing is not None:
        return _decrypt(bytes(existing.nonce), bytes(existing.encrypted_payload)), False
    payload = build_receiver_envelope(document)
    _store_artifact(document, ElectronicTaxArtifact.Kind.RECEIVER_ENVELOPE, payload)
    return payload, True


def _mail_sender(document):
    configured = getattr(settings, "SII_EXCHANGE_FROM_EMAIL", "").strip()
    return configured or document.issuer_tax_email


def _build_mail(*, document, envelope, ride):
    sender = _mail_sender(document)
    if not sender:
        raise DTEProviderNotConfiguredError(
            "Falta SII_EXCHANGE_FROM_EMAIL y el snapshot del emisor no contiene correo tributario."
        )
    subject = f"DTE {document.type_code} folio {document.folio} - {document.issuer_legal_name}"
    body = (
        "Se adjunta el Documento Tributario Electronico en formato XML y su representacion impresa.\n"
        "El XML es el documento valido para intercambio entre receptores electronicos."
    )
    message = EmailMessage(
        subject=subject,
        body=body,
        from_email=sender,
        to=[document.receiver_tax_email],
    )
    message.attach(
        f"DTE_{document.type_code}_{document.folio}.xml",
        envelope,
        "application/xml",
    )
    message.attach(
        f"RIDE_{document.type_code}_{document.folio}.pdf",
        ride,
        "application/pdf",
    )
    return message


@transaction.atomic
def deliver_to_receiver(*, document, expected_version, idempotency_key, actor):
    locked = ElectronicTaxDocument.objects.select_for_update().get(pk=document.pk)
    if locked.version != expected_version:
        raise DTEVersionConflictError(
            f"Version obsoleta. Esperada {expected_version}; actual {locked.version}."
        )
    if locked.state not in _EXCHANGEABLE_STATES:
        raise DTEInvalidStateError("El DTE debe estar aceptado antes de enviarlo al receptor.")
    if not getattr(settings, "SII_EXCHANGE_ENABLED", False):
        raise DTEProviderNotConfiguredError("SII_EXCHANGE_ENABLED no esta habilitado.")
    if not locked.receiver_tax_email:
        raise DTEValidationError("El DTE no contiene correo tributario del receptor.")

    request_hash = _canonical_hash(
        {
            "document_id": locked.id,
            "version": expected_version,
            "recipient": locked.receiver_tax_email.lower(),
        }
    )
    key, replay = _idempotency_replay(
        document=locked,
        operation="DELIVER_DTE_RECEIVER",
        key=idempotency_key,
        request_hash=request_hash,
    )
    if replay is not None:
        exchange = ElectronicTaxExchange.objects.get(document=locked)
        return exchange, False

    envelope, _ = get_or_create_receiver_envelope(locked)
    ride, _ = get_or_create_ride(document=locked, actor=actor)
    envelope_hash = hashlib.sha256(envelope).hexdigest()
    ride_hash = hashlib.sha256(ride).hexdigest()
    exchange, _ = ElectronicTaxExchange.objects.get_or_create(document=locked)
    exchange.delivery_state = ElectronicTaxExchange.DeliveryState.PENDING
    exchange.recipient_email = locked.receiver_tax_email
    exchange.envelope_hash = envelope_hash
    exchange.ride_hash = ride_hash
    exchange.send_attempts += 1
    exchange.last_send_error = ""
    exchange.save()

    message = _build_mail(document=locked, envelope=envelope, ride=ride)
    try:
        sent = message.send(fail_silently=False)
    except Exception as error:
        exchange.delivery_state = ElectronicTaxExchange.DeliveryState.SEND_UNCERTAIN
        exchange.last_send_error = str(error)[:500]
        exchange.save(update_fields=("delivery_state", "last_send_error", "updated_at"))
        record_event(
            document=locked,
            event_type=ElectronicTaxEvent.EventType.RECEIVER_EXCHANGE_UNCERTAIN,
            actor=actor,
            code="RECEIVER_SEND_UNCERTAIN",
            metadata={"envelope_hash": envelope_hash, "ride_hash": ride_hash},
        )
        IdempotencyRecord.objects.create(
            company=locked.company,
            operation="DELIVER_DTE_RECEIVER",
            key=key,
            request_hash=request_hash,
            document=locked,
            response_status=202,
            response_body={"delivery_state": exchange.delivery_state},
        )
        return exchange, True
    if sent != 1:
        raise DTEValidationError("El backend de correo no confirmo el envio al receptor.")

    exchange.delivery_state = ElectronicTaxExchange.DeliveryState.SENT
    exchange.sent_at = timezone.now()
    exchange.last_send_error = ""
    exchange.save(update_fields=("delivery_state", "sent_at", "last_send_error", "updated_at"))
    record_event(
        document=locked,
        event_type=ElectronicTaxEvent.EventType.RECEIVER_EXCHANGE_SENT,
        actor=actor,
        metadata={
            "envelope_hash": envelope_hash,
            "ride_hash": ride_hash,
            "recipient_domain": locked.receiver_tax_email.rsplit("@", 1)[-1].lower(),
        },
    )
    IdempotencyRecord.objects.create(
        company=locked.company,
        operation="DELIVER_DTE_RECEIVER",
        key=key,
        request_hash=request_hash,
        document=locked,
        response_status=200,
        response_body={"delivery_state": exchange.delivery_state},
    )
    return exchange, True


def _validate_exchange_response_xsd(payload):
    directory = Path(getattr(settings, "SII_EXCHANGE_XSD_DIR", "").strip())
    schema_name = "RespuestaEnvioDTE_v10.xsd"
    path = directory / schema_name
    if not directory.is_dir() or not path.is_file():
        raise DTEProviderNotConfiguredError(
            f"SII_EXCHANGE_XSD_DIR debe contener {schema_name}."
        )
    try:
        schema = etree.XMLSchema(etree.parse(str(path), parser=_safe_xml_parser()))
        root = etree.fromstring(payload, parser=_safe_xml_parser())
        schema.assertValid(root)
    except etree.DocumentInvalid as error:
        raise DTEValidationError("La respuesta del receptor no cumple el schema oficial de intercambio.") from error


def _first_text(node, names):
    for name in names:
        values = node.xpath(f".//*[local-name()='{name}']/text()")
        if values and values[0].strip():
            return values[0].strip()
    return ""


def _parse_receiver_response(document, payload):
    if not payload or len(payload) > 2 * 1024 * 1024:
        raise DTEValidationError("La respuesta del receptor es vacia o excede 2 MiB.")
    try:
        root = etree.fromstring(payload, parser=_safe_xml_parser())
    except Exception as error:
        raise DTEValidationError("La respuesta del receptor no es XML valido.") from error
    if etree.QName(root).localname != "RespuestaEnvioDTE":
        raise DTEValidationError("El XML no corresponde a RespuestaEnvioDTE.")
    if not root.xpath(".//*[local-name()='Signature']"):
        raise DTEValidationError("La respuesta del receptor no contiene firma XMLDSig.")

    responder = _first_text(root, ("RutResponde", "RUTResponde"))
    receiver = _first_text(root, ("RutRecibe", "RUTRecibe"))
    if responder and normalize_rut(responder) != normalize_rut(document.receiver_rut):
        raise DTEValidationError("El RUT que responde no coincide con el receptor del DTE.")
    if receiver and normalize_rut(receiver) != normalize_rut(document.issuer_rut):
        raise DTEValidationError("El RUT destinatario de la respuesta no coincide con el emisor del DTE.")

    result_nodes = root.xpath(".//*[local-name()='ResultadoDTE']")
    matching = None
    for node in result_nodes:
        type_code = _first_text(node, ("TipoDTE", "TipoDoc"))
        folio = _first_text(node, ("Folio", "FolioDTE"))
        if type_code == str(document.type_code) and folio == str(document.folio):
            matching = node
            break
    if matching is not None:
        code = _first_text(matching, ("EstadoDTE", "Estado"))
        message = _first_text(
            matching,
            ("EstadoDTEGlosa", "Glosa", "GlosaEstado", "GlosaMotivo", "GlosaMotivoRechazo"),
        )
        state = {
            "0": ElectronicTaxExchange.ReceiverResponseState.ACCEPTED,
            "1": ElectronicTaxExchange.ReceiverResponseState.ACCEPTED_WITH_DISCREPANCY,
            "2": ElectronicTaxExchange.ReceiverResponseState.REJECTED,
        }.get(code, ElectronicTaxExchange.ReceiverResponseState.RECEIVED)
        return state, code, message

    reception_nodes = root.xpath(".//*[local-name()='RecepcionDTE']")
    for node in reception_nodes:
        type_code = _first_text(node, ("TipoDTE", "TipoDoc"))
        folio = _first_text(node, ("Folio", "FolioDTE"))
        if type_code == str(document.type_code) and folio == str(document.folio):
            code = _first_text(node, ("EstadoRecepDTE", "Estado"))
            message = _first_text(node, ("RecepDTEGlosa", "Glosa", "GlosaEstado"))
            return ElectronicTaxExchange.ReceiverResponseState.RECEIVED, code, message
    return ElectronicTaxExchange.ReceiverResponseState.RECEIVED, "", "Respuesta de intercambio recibida"


@transaction.atomic
def ingest_receiver_response(*, document, payload, expected_version, idempotency_key, actor):
    locked = ElectronicTaxDocument.objects.select_for_update().get(pk=document.pk)
    if locked.version != expected_version:
        raise DTEVersionConflictError(
            f"Version obsoleta. Esperada {expected_version}; actual {locked.version}."
        )
    if locked.state not in _EXCHANGEABLE_STATES:
        raise DTEInvalidStateError("La respuesta del receptor solo se registra para un DTE aceptado.")
    exchange = ElectronicTaxExchange.objects.filter(document=locked).first()
    if exchange is None or exchange.delivery_state not in {
        ElectronicTaxExchange.DeliveryState.SENT,
        ElectronicTaxExchange.DeliveryState.SEND_UNCERTAIN,
    }:
        raise DTEInvalidStateError("No existe un intercambio saliente registrado para este DTE.")

    response_hash = hashlib.sha256(payload).hexdigest()
    request_hash = _canonical_hash(
        {"document_id": locked.id, "version": expected_version, "response_hash": response_hash}
    )
    key, replay = _idempotency_replay(
        document=locked,
        operation="INGEST_RECEIVER_RESPONSE",
        key=idempotency_key,
        request_hash=request_hash,
    )
    if replay is not None:
        return ElectronicTaxExchange.objects.get(document=locked), False

    _validate_exchange_response_xsd(payload)
    state, code, message = _parse_receiver_response(locked, payload)
    _store_artifact(locked, ElectronicTaxArtifact.Kind.RECEIVER_RESPONSE, payload)
    exchange.receiver_response_state = state
    exchange.receiver_response_code = code[:40]
    exchange.receiver_response_message = message[:500]
    exchange.receiver_response_hash = response_hash
    exchange.receiver_response_at = timezone.now()
    exchange.save(
        update_fields=(
            "receiver_response_state",
            "receiver_response_code",
            "receiver_response_message",
            "receiver_response_hash",
            "receiver_response_at",
            "updated_at",
        )
    )
    record_event(
        document=locked,
        event_type=ElectronicTaxEvent.EventType.RECEIVER_RESPONSE_RECEIVED,
        actor=actor,
        code=exchange.receiver_response_code,
        metadata={"response_hash": response_hash, "receiver_response_state": state},
    )
    IdempotencyRecord.objects.create(
        company=locked.company,
        operation="INGEST_RECEIVER_RESPONSE",
        key=key,
        request_hash=request_hash,
        document=locked,
        response_status=200,
        response_body={"receiver_response_state": state},
    )
    return exchange, True
