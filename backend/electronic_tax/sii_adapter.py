import base64
import copy
import hashlib
import html
import os
import threading
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path

import requests
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.serialization import pkcs12
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from lxml import etree

from .models import (
    ElectronicTaxArtifact,
    ElectronicTaxDocument,
    ElectronicTaxReference,
    FolioAuthorization,
    FolioAuthorizationEvent,
    FolioAuthorizationSecret,
    IdempotencyRecord,
    TaxCompanyProfile,
)
from .services import (
    DTEIdempotencyConflictError,
    DTEProviderNotConfiguredError,
    DTEValidationError,
    ElectronicTaxProviderPort,
    ProviderSendUncertain,
    normalize_rut,
)

SII_NS = "http://www.sii.cl/SiiDte"
DS_NS = "http://www.w3.org/2000/09/xmldsig#"
XSI_NS = "http://www.w3.org/2001/XMLSchema-instance"
SII_RESPONSE_NS = "http://www.sii.cl/XMLSchema"
SII_RUT = "60803000-K"
XML_ENCODING = "ISO-8859-1"


@dataclass(frozen=True)
class SIIEndpoints:
    base_host: str

    @property
    def seed(self):
        return f"https://{self.base_host}/DTEWS/CrSeed.jws"

    @property
    def token(self):
        return f"https://{self.base_host}/DTEWS/GetTokenFromSeed.jws"

    @property
    def upload(self):
        return f"https://{self.base_host}/cgi_dte/UPL/DTEUpload"

    @property
    def query_upload(self):
        return f"https://{self.base_host}/DTEWS/QueryEstUp.jws"

    @property
    def query_dte(self):
        return f"https://{self.base_host}/DTEWS/QueryEstDte.jws"


def _endpoints():
    environment = getattr(settings, "SII_ENVIRONMENT", "certification")
    if environment == "certification":
        return SIIEndpoints("maullin.sii.cl")
    if environment == "production":
        return SIIEndpoints("palena.sii.cl")
    raise DTEProviderNotConfiguredError("SII_ENVIRONMENT debe ser certification o production.")


def _split_rut(value):
    normalized = normalize_rut(value)
    body, dv = normalized.split("-")
    return body, dv


def _require_secret_key():
    raw = getattr(settings, "SII_SECRET_KEY", "")
    if not raw:
        raise DTEProviderNotConfiguredError("Falta SII_SECRET_KEY para custodiar CAF y XML firmado.")
    try:
        key = base64.urlsafe_b64decode(raw.encode("ascii"))
    except Exception as error:
        raise DTEProviderNotConfiguredError("SII_SECRET_KEY no es base64 URL-safe valido.") from error
    if len(key) != 32:
        raise DTEProviderNotConfiguredError("SII_SECRET_KEY debe decodificar exactamente 32 bytes.")
    return key


def _encrypt(payload: bytes):
    nonce = os.urandom(12)
    encrypted = AESGCM(_require_secret_key()).encrypt(nonce, payload, b"TuPymeGestiona:SII:v1")
    return nonce, encrypted


def _decrypt(nonce: bytes, encrypted: bytes):
    return AESGCM(_require_secret_key()).decrypt(nonce, encrypted, b"TuPymeGestiona:SII:v1")


def _safe_xml_parser():
    return etree.XMLParser(resolve_entities=False, no_network=True, remove_blank_text=False, huge_tree=False)


def _pem_private_from_caf(root):
    original = root.findtext("RSASK", default="").strip()
    if not original:
        raise DTEValidationError("El CAF no contiene RSASK.")
    if "BEGIN RSA PRIVATE KEY" not in original:
        raise DTEValidationError("RSASK no contiene una llave privada RSA PEM valida.")
    return original.encode("ascii")


def _load_caf_private_key(root):
    try:
        return serialization.load_pem_private_key(_pem_private_from_caf(root), password=None)
    except Exception as error:
        raise DTEValidationError("No fue posible cargar la llave privada RSA del CAF.") from error


def _decode_int(value):
    raw = base64.b64decode("".join((value or "").split()))
    return int.from_bytes(raw, "big")


def _trusted_sii_public_key(idk):
    directory = getattr(settings, "SII_CAF_TRUSTED_PUBLIC_KEYS_DIR", "")
    if not directory:
        raise DTEProviderNotConfiguredError(
            "Falta SII_CAF_TRUSTED_PUBLIC_KEYS_DIR; el CAF no se activa sin verificar FRMA."
        )
    path = Path(directory) / f"{idk}.pem"
    if not path.is_file():
        raise DTEValidationError(f"No existe llave publica SII confiable para IDK {idk}.")
    try:
        return serialization.load_pem_public_key(path.read_bytes())
    except Exception as error:
        raise DTEValidationError(f"La llave publica SII IDK {idk} no es valida.") from error


def parse_and_validate_caf(caf_bytes: bytes, *, company):
    if not caf_bytes or len(caf_bytes) > 2 * 1024 * 1024:
        raise DTEValidationError("El CAF es vacio o excede 2 MiB.")
    try:
        root = etree.fromstring(caf_bytes, parser=_safe_xml_parser())
    except Exception as error:
        raise DTEValidationError("El CAF no es XML valido.") from error
    if etree.QName(root).localname != "AUTORIZACION":
        raise DTEValidationError("El XML no corresponde a una AUTORIZACION de folios.")
    caf = root.find("CAF")
    da = caf.find("DA") if caf is not None else None
    frma = caf.find("FRMA") if caf is not None else None
    if caf is None or da is None or frma is None:
        raise DTEValidationError("El CAF no contiene CAF/DA/FRMA completos.")

    issuer_rut = normalize_rut(da.findtext("RE", default=""))
    profile = TaxCompanyProfile.objects.filter(company=company, active=True).first()
    if profile is None:
        raise DTEValidationError("La empresa no tiene perfil tributario activo.")
    if issuer_rut != normalize_rut(profile.rut):
        raise DTEValidationError("El RUT del CAF no coincide con la empresa activa.")
    try:
        type_code = int(da.findtext("TD", default="0"))
        start = int(da.findtext("RNG/D", default="0"))
        end = int(da.findtext("RNG/H", default="0"))
    except ValueError as error:
        raise DTEValidationError("Tipo/rango del CAF no es numerico.") from error
    if type_code not in ElectronicTaxDocument.TypeCode.values:
        raise DTEValidationError("El tipo DTE del CAF no esta soportado por este alcance.")
    if start <= 0 or end < start:
        raise DTEValidationError("El rango de folios del CAF es invalido.")

    private_key = _load_caf_private_key(root)
    if not isinstance(private_key, rsa.RSAPrivateKey):
        raise DTEValidationError("RSASK del CAF debe ser RSA.")
    modulus = _decode_int(da.findtext("RSAPK/M", default=""))
    exponent = _decode_int(da.findtext("RSAPK/E", default=""))
    if private_key.public_key().public_numbers() != rsa.RSAPublicNumbers(exponent, modulus):
        raise DTEValidationError("La llave privada RSASK no corresponde a RSAPK del CAF.")

    idk = (da.findtext("IDK", default="") or "").strip()
    if not idk:
        raise DTEValidationError("El CAF no contiene IDK.")
    trusted_key = _trusted_sii_public_key(idk)
    signature = base64.b64decode("".join((frma.text or "").split()))
    candidates = [
        etree.tostring(da, encoding=XML_ENCODING, with_tail=False),
        etree.tostring(da, method="c14n", exclusive=False, with_comments=False),
    ]
    verified = False
    for candidate in candidates:
        try:
            trusted_key.verify(signature, candidate, padding.PKCS1v15(), hashes.SHA1())
            verified = True
            break
        except Exception:
            continue
    if not verified:
        raise DTEValidationError("La firma FRMA del SII sobre el CAF no pudo verificarse.")

    return {
        "root": root,
        "caf": caf,
        "issuer_rut": issuer_rut,
        "type_code": type_code,
        "start_folio": start,
        "end_folio": end,
        "idk": idk,
        "valid_from": da.findtext("FA") or None,
        "hash": hashlib.sha256(caf_bytes).hexdigest(),
    }


@transaction.atomic
def import_caf(*, company, caf_bytes, idempotency_key, actor, source_label=""):
    key = (idempotency_key or "").strip()
    if not key:
        raise DTEValidationError("Idempotency-Key es obligatorio.")
    request_hash = hashlib.sha256(caf_bytes).hexdigest()
    existing = IdempotencyRecord.objects.filter(company=company, operation="IMPORT_CAF", key=key).first()
    if existing:
        if existing.request_hash != request_hash:
            raise DTEIdempotencyConflictError("La misma clave idempotente fue reutilizada con otro CAF.")
        authorization_id = existing.response_body.get("authorization_id")
        return FolioAuthorization.objects.get(pk=authorization_id), False

    parsed = parse_and_validate_caf(caf_bytes, company=company)
    if FolioAuthorization.objects.filter(
        company=company,
        type_code=parsed["type_code"],
        start_folio__lte=parsed["end_folio"],
        end_folio__gte=parsed["start_folio"],
    ).exists():
        raise DTEValidationError("El rango CAF se superpone con una autorizacion existente.")

    authorization = FolioAuthorization.objects.create(
        company=company,
        type_code=parsed["type_code"],
        start_folio=parsed["start_folio"],
        end_folio=parsed["end_folio"],
        next_folio=parsed["start_folio"],
        status=FolioAuthorization.Status.ACTIVE,
        source_label=(source_label or "")[:120],
        caf_hash=parsed["hash"],
        valid_from=parsed["valid_from"],
    )
    nonce, encrypted = _encrypt(caf_bytes)
    FolioAuthorizationSecret.objects.create(
        authorization=authorization, nonce=nonce, encrypted_caf=encrypted
    )
    FolioAuthorizationEvent.objects.create(
        authorization=authorization,
        company=company,
        event_type=FolioAuthorizationEvent.EventType.CAF_IMPORTED,
        actor=actor,
        metadata={
            "type_code": authorization.type_code,
            "start_folio": authorization.start_folio,
            "end_folio": authorization.end_folio,
            "caf_hash": authorization.caf_hash,
            "idk": parsed["idk"],
        },
    )
    IdempotencyRecord.objects.create(
        company=company,
        operation="IMPORT_CAF",
        key=key,
        request_hash=request_hash,
        response_status=201,
        response_body={"authorization_id": authorization.id},
    )
    return authorization, True


def _certificate_material():
    path = Path(getattr(settings, "SII_CERTIFICATE_PFX_PATH", ""))
    password_env = getattr(settings, "SII_CERTIFICATE_PASSWORD_ENV", "SII_CERTIFICATE_PASSWORD")
    password = os.getenv(password_env, "")
    if not path.is_file() or not password:
        raise DTEProviderNotConfiguredError(
            "Falta certificado PFX o su password en el entorno para operar con SII."
        )
    try:
        key, cert, chain = pkcs12.load_key_and_certificates(path.read_bytes(), password.encode())
    except Exception as error:
        raise DTEProviderNotConfiguredError("No fue posible abrir el certificado PFX configurado.") from error
    if key is None or cert is None:
        raise DTEProviderNotConfiguredError("El PFX no contiene llave privada y certificado.")
    now = timezone.now()
    if cert.not_valid_before_utc > now or cert.not_valid_after_utc <= now:
        raise DTEProviderNotConfiguredError("El certificado digital SII no esta vigente.")
    return key, cert, chain


def _certificate_b64(cert):
    return base64.b64encode(cert.public_bytes(serialization.Encoding.DER)).decode("ascii")


def _c14n(element):
    return etree.tostring(element, method="c14n", exclusive=False, with_comments=False)


def _xml_signature(parent, *, reference_element, reference_uri, private_key, certificate):
    digest = base64.b64encode(hashlib.sha1(_c14n(reference_element)).digest()).decode("ascii")
    sig = etree.SubElement(parent, etree.QName(DS_NS, "Signature"), nsmap={None: DS_NS})
    signed_info = etree.SubElement(sig, etree.QName(DS_NS, "SignedInfo"))
    etree.SubElement(
        signed_info,
        etree.QName(DS_NS, "CanonicalizationMethod"),
        Algorithm="http://www.w3.org/TR/2001/REC-xml-c14n-20010315",
    )
    etree.SubElement(
        signed_info,
        etree.QName(DS_NS, "SignatureMethod"),
        Algorithm="http://www.w3.org/2000/09/xmldsig#rsa-sha1",
    )
    ref = etree.SubElement(signed_info, etree.QName(DS_NS, "Reference"), URI=reference_uri)
    transforms = etree.SubElement(ref, etree.QName(DS_NS, "Transforms"))
    etree.SubElement(
        transforms,
        etree.QName(DS_NS, "Transform"),
        Algorithm="http://www.w3.org/2000/09/xmldsig#enveloped-signature",
    )
    etree.SubElement(
        ref,
        etree.QName(DS_NS, "DigestMethod"),
        Algorithm="http://www.w3.org/2000/09/xmldsig#sha1",
    )
    etree.SubElement(ref, etree.QName(DS_NS, "DigestValue")).text = digest
    signature_bytes = private_key.sign(_c14n(signed_info), padding.PKCS1v15(), hashes.SHA1())
    etree.SubElement(sig, etree.QName(DS_NS, "SignatureValue")).text = base64.b64encode(signature_bytes).decode("ascii")
    key_info = etree.SubElement(sig, etree.QName(DS_NS, "KeyInfo"))
    key_value = etree.SubElement(key_info, etree.QName(DS_NS, "KeyValue"))
    rsa_value = etree.SubElement(key_value, etree.QName(DS_NS, "RSAKeyValue"))
    numbers = private_key.public_key().public_numbers()
    etree.SubElement(rsa_value, etree.QName(DS_NS, "Modulus")).text = base64.b64encode(
        numbers.n.to_bytes((numbers.n.bit_length() + 7) // 8, "big")
    ).decode("ascii")
    etree.SubElement(rsa_value, etree.QName(DS_NS, "Exponent")).text = base64.b64encode(
        numbers.e.to_bytes((numbers.e.bit_length() + 7) // 8, "big")
    ).decode("ascii")
    x509_data = etree.SubElement(key_info, etree.QName(DS_NS, "X509Data"))
    etree.SubElement(x509_data, etree.QName(DS_NS, "X509Certificate")).text = _certificate_b64(certificate)
    return sig


def _seed_xml(seed, *, private_key, certificate):
    root = etree.Element("getToken")
    item = etree.SubElement(root, "item")
    etree.SubElement(item, "Semilla").text = seed
    _xml_signature(
        root,
        reference_element=root,
        reference_uri="",
        private_key=private_key,
        certificate=certificate,
    )
    return etree.tostring(root, encoding="UTF-8", xml_declaration=True)


def _load_caf_for_document(document):
    try:
        secret = document.folio_authorization.secret_material
    except Exception as error:
        raise DTEValidationError("La autorizacion de folios no contiene CAF cifrado.") from error
    raw = _decrypt(bytes(secret.nonce), bytes(secret.encrypted_caf))
    return etree.fromstring(raw, parser=_safe_xml_parser())


def _text(parent, name, value):
    child = etree.SubElement(parent, etree.QName(SII_NS, name))
    child.text = str(value)
    return child


def _build_ted(document, caf_root, timestamp):
    caf = caf_root.find("CAF")
    private_key = _load_caf_private_key(caf_root)
    dd = etree.Element("DD")
    etree.SubElement(dd, "RE").text = document.issuer_rut
    etree.SubElement(dd, "TD").text = str(document.type_code)
    etree.SubElement(dd, "F").text = str(document.folio)
    etree.SubElement(dd, "FE").text = document.issue_date.isoformat()
    etree.SubElement(dd, "RR").text = document.receiver_rut
    etree.SubElement(dd, "RSR").text = document.receiver_legal_name[:40]
    etree.SubElement(dd, "MNT").text = str(document.total_amount)
    first = document.lines.order_by("line_number").first()
    etree.SubElement(dd, "IT1").text = (first.description if first else "DTE")[:40]
    dd.append(copy.deepcopy(caf))
    etree.SubElement(dd, "TSTED").text = timestamp
    raw_dd = etree.tostring(dd, encoding=XML_ENCODING, with_tail=False)
    signature = private_key.sign(raw_dd, padding.PKCS1v15(), hashes.SHA1())
    ted = etree.Element(etree.QName(SII_NS, "TED"), version="1.0")
    ted.append(dd)
    frmt = etree.SubElement(ted, etree.QName(SII_NS, "FRMT"), algoritmo="SHA1withRSA")
    frmt.text = base64.b64encode(signature).decode("ascii")
    return ted


def _document_xml(document, *, private_key, certificate):
    profile = TaxCompanyProfile.objects.get(company=document.company)
    missing = []
    if not profile.economic_activity_code:
        missing.append("economic_activity_code")
    if not profile.sii_resolution_number:
        missing.append("sii_resolution_number")
    if not profile.sii_resolution_date:
        missing.append("sii_resolution_date")
    if missing:
        raise DTEValidationError("Faltan datos SII del emisor: " + ", ".join(missing))

    root = etree.Element(etree.QName(SII_NS, "DTE"), nsmap={None: SII_NS}, version="1.0")
    document_id = f"T{document.type_code}F{document.folio}"
    doc = etree.SubElement(root, etree.QName(SII_NS, "Documento"), ID=document_id)
    header = etree.SubElement(doc, etree.QName(SII_NS, "Encabezado"))
    iddoc = etree.SubElement(header, etree.QName(SII_NS, "IdDoc"))
    _text(iddoc, "TipoDTE", document.type_code)
    _text(iddoc, "Folio", document.folio)
    _text(iddoc, "FchEmis", document.issue_date.isoformat())
    if document.type_code == 33:
        _text(iddoc, "MntBruto", 1)

    issuer = etree.SubElement(header, etree.QName(SII_NS, "Emisor"))
    _text(issuer, "RUTEmisor", document.issuer_rut)
    _text(issuer, "RznSoc", document.issuer_legal_name[:100])
    _text(issuer, "GiroEmis", document.issuer_business_activity[:80])
    _text(issuer, "Acteco", profile.economic_activity_code)
    if profile.sii_branch_code:
        _text(issuer, "CdgSIISucur", profile.sii_branch_code)
    _text(issuer, "DirOrigen", document.issuer_address[:70])
    _text(issuer, "CmnaOrigen", document.issuer_commune[:20])
    if document.issuer_city:
        _text(issuer, "CiudadOrigen", document.issuer_city[:20])

    receiver = etree.SubElement(header, etree.QName(SII_NS, "Receptor"))
    _text(receiver, "RUTRecep", document.receiver_rut)
    _text(receiver, "RznSocRecep", document.receiver_legal_name[:100])
    _text(receiver, "GiroRecep", document.receiver_business_activity[:40])
    _text(receiver, "DirRecep", document.receiver_address[:70])
    _text(receiver, "CmnaRecep", document.receiver_commune[:20])
    if document.receiver_city:
        _text(receiver, "CiudadRecep", document.receiver_city[:20])

    totals = etree.SubElement(header, etree.QName(SII_NS, "Totales"))
    if document.type_code != 34 and document.net_amount:
        _text(totals, "MntNeto", document.net_amount)
    if document.exempt_amount:
        _text(totals, "MntExe", document.exempt_amount)
    if document.type_code != 34 and document.vat_amount:
        _text(totals, "TasaIVA", int(document.vat_rate))
        _text(totals, "IVA", document.vat_amount)
    _text(totals, "MntTotal", document.total_amount)

    for line in document.lines.order_by("line_number"):
        detail = etree.SubElement(doc, etree.QName(SII_NS, "Detalle"))
        _text(detail, "NroLinDet", line.line_number)
        if line.tax_category == "EXEMPT":
            _text(detail, "IndExe", 1)
        _text(detail, "NmbItem", line.description[:80])
        _text(detail, "QtyItem", format(line.quantity, "f").rstrip("0").rstrip(".") or "0")
        _text(detail, "PrcItem", format(line.unit_price, "f").rstrip("0").rstrip(".") or "0")
        _text(detail, "MontoItem", line.total_amount)

    for number, reference in enumerate(document.references.order_by("id"), start=1):
        ref = etree.SubElement(doc, etree.QName(SII_NS, "Referencia"))
        _text(ref, "NroLinRef", number)
        _text(ref, "TpoDocRef", reference.referenced_type_code)
        _text(ref, "FolioRef", reference.referenced_folio)
        _text(ref, "FchRef", reference.reference_date.isoformat())
        cod_ref = 2 if reference.reason == ElectronicTaxReference.Reason.CORRECT_TEXT else 3 if reference.reason == ElectronicTaxReference.Reason.CORRECT_AMOUNTS else 1
        _text(ref, "CodRef", cod_ref)
        _text(ref, "RazonRef", reference.description[:90])

    timestamp = timezone.localtime().strftime("%Y-%m-%dT%H:%M:%S")
    doc.append(_build_ted(document, _load_caf_for_document(document), timestamp))
    _text(doc, "TmstFirma", timestamp)
    _xml_signature(
        root,
        reference_element=doc,
        reference_uri=f"#{document_id}",
        private_key=private_key,
        certificate=certificate,
    )
    return root, profile


def build_signed_envelope(document):
    private_key, certificate, _ = _certificate_material()
    dte, profile = _document_xml(document, private_key=private_key, certificate=certificate)
    envelope = etree.Element(
        etree.QName(SII_NS, "EnvioDTE"),
        nsmap={None: SII_NS, "xsi": XSI_NS},
        version="1.0",
    )
    envelope.set(etree.QName(XSI_NS, "schemaLocation"), f"{SII_NS} EnvioDTE_v10.xsd")
    set_dte = etree.SubElement(envelope, etree.QName(SII_NS, "SetDTE"), ID="SetDoc")
    caratula = etree.SubElement(set_dte, etree.QName(SII_NS, "Caratula"), version="1.0")
    sender_rut = getattr(settings, "SII_SENDER_RUT", "")
    if not sender_rut:
        raise DTEProviderNotConfiguredError("Falta SII_SENDER_RUT.")
    _text(caratula, "RutEmisor", document.issuer_rut)
    _text(caratula, "RutEnvia", normalize_rut(sender_rut))
    _text(caratula, "RutReceptor", SII_RUT)
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
        reference_uri="#SetDoc",
        private_key=private_key,
        certificate=certificate,
    )
    payload = etree.tostring(envelope, encoding=XML_ENCODING, xml_declaration=True, pretty_print=False)
    _validate_xsd(payload)
    return payload


def _validate_xsd(payload):
    directory = Path(getattr(settings, "SII_XSD_DIR", ""))
    required = ["EnvioDTE_v10.xsd", "DTE_v10.xsd", "SiiTypes_v10.xsd", "xmldsignature_v10.xsd"]
    if not directory.is_dir() or any(not (directory / name).is_file() for name in required):
        raise DTEProviderNotConfiguredError(
            "SII_XSD_DIR debe contener EnvioDTE_v10.xsd, DTE_v10.xsd, SiiTypes_v10.xsd y xmldsignature_v10.xsd."
        )
    try:
        schema = etree.XMLSchema(etree.parse(str(directory / "EnvioDTE_v10.xsd"), parser=_safe_xml_parser()))
        document = etree.fromstring(payload, parser=_safe_xml_parser())
        schema.assertValid(document)
    except etree.DocumentInvalid as error:
        raise DTEValidationError("El EnvioDTE generado no cumple los XSD oficiales del SII.") from error


_TOKEN_CACHE = {}
_TOKEN_LOCK = threading.Lock()


def _soap_rpc(url, namespace, operation, params):
    envelope = etree.Element(etree.QName("http://schemas.xmlsoap.org/soap/envelope/", "Envelope"), nsmap={"soapenv": "http://schemas.xmlsoap.org/soap/envelope/", "xsi": "http://www.w3.org/2001/XMLSchema-instance", "xsd": "http://www.w3.org/2001/XMLSchema"})
    body = etree.SubElement(envelope, etree.QName("http://schemas.xmlsoap.org/soap/envelope/", "Body"))
    op = etree.SubElement(body, etree.QName(namespace, operation))
    for name, value in params:
        element = etree.SubElement(op, name)
        element.set(etree.QName("http://www.w3.org/2001/XMLSchema-instance", "type"), "xsd:string")
        element.text = str(value)
    try:
        response = requests.post(url, data=etree.tostring(envelope, encoding="UTF-8", xml_declaration=True), headers={"Content-Type": "text/xml; charset=utf-8"}, timeout=settings.SII_HTTP_TIMEOUT)
        response.raise_for_status()
    except (requests.Timeout, requests.ConnectionError) as error:
        raise ProviderSendUncertain(str(error)) from error
    except requests.RequestException as error:
        raise DTEValidationError(f"SII HTTP error: {error}") from error
    root = etree.fromstring(response.content, parser=_safe_xml_parser())
    returns = root.xpath("//*[local-name()='Body']//*[contains(local-name(), 'Return')]")
    if not returns:
        raise DTEValidationError("La respuesta SOAP del SII no contiene valor de retorno.")
    return returns[0].text or ""


def _parse_sii_response(xml_text):
    try:
        root = etree.fromstring(html.unescape(xml_text).encode("utf-8"), parser=_safe_xml_parser())
    except Exception as error:
        raise DTEValidationError("El SII devolvio XML de respuesta invalido.") from error
    def first(name):
        values = root.xpath(f"//*[local-name()='{name}']/text()")
        return values[0].strip() if values else ""
    return root, first


def _get_token():
    private_key, certificate, _ = _certificate_material()
    fingerprint = certificate.fingerprint(hashes.SHA256()).hex()
    cache_key = (_endpoints().base_host, fingerprint)
    with _TOKEN_LOCK:
        cached = _TOKEN_CACHE.get(cache_key)
        if cached and cached[1] > timezone.now():
            return cached[0]
    endpoints = _endpoints()
    seed_return = _soap_rpc(endpoints.seed, f"https://{endpoints.base_host}/DTEWS/CrSeed.jws", "getSeed", [])
    _, seed_first = _parse_sii_response(seed_return)
    if seed_first("ESTADO") != "00" or not seed_first("SEMILLA"):
        raise DTEValidationError("El SII no entrego una semilla valida.")
    signed_seed = _seed_xml(seed_first("SEMILLA"), private_key=private_key, certificate=certificate).decode("utf-8")
    token_return = _soap_rpc(endpoints.token, f"https://{endpoints.base_host}/DTEWS/GetTokenFromSeed.jws", "getToken", [("pszXml", signed_seed)])
    _, token_first = _parse_sii_response(token_return)
    if token_first("ESTADO") != "00" or not token_first("TOKEN"):
        raise DTEValidationError("El SII rechazo la autenticacion automatica.")
    token = token_first("TOKEN")
    with _TOKEN_LOCK:
        _TOKEN_CACHE[cache_key] = (token, timezone.now() + timedelta(minutes=50))
    return token


def _save_artifact(document, payload):
    digest = hashlib.sha256(payload).hexdigest()
    nonce, encrypted = _encrypt(payload)
    ElectronicTaxArtifact.objects.update_or_create(
        document=document,
        kind=ElectronicTaxArtifact.Kind.SIGNED_ENVELOPE,
        defaults={"content_hash": digest, "nonce": nonce, "encrypted_payload": encrypted},
    )
    return digest


def _load_artifact(document):
    try:
        artifact = document.artifacts.get(kind=ElectronicTaxArtifact.Kind.SIGNED_ENVELOPE)
    except ElectronicTaxArtifact.DoesNotExist as error:
        raise DTEValidationError("No existe EnvioDTE firmado persistido para el documento.") from error
    return _decrypt(bytes(artifact.nonce), bytes(artifact.encrypted_payload))


def _map_document_status(code, message):
    if code in {"DOK", "TMD", "TMC", "MMD", "MMC"}:
        return ElectronicTaxDocument.State.ACCEPTED
    if code in {"FAN"}:
        return ElectronicTaxDocument.State.ACCEPTED_WITH_REPAIR
    if code in {"DNK", "FAU", "FNA", "EMP"}:
        return ElectronicTaxDocument.State.REJECTED
    return ElectronicTaxDocument.State.PROCESSING


class SIIElectronicTaxProvider(ElectronicTaxProviderPort):
    configured = True

    def __init__(self):
        if not getattr(settings, "SII_ADAPTER_ENABLED", False):
            raise DTEProviderNotConfiguredError("SII_ADAPTER_ENABLED no esta habilitado.")
        _endpoints()
        _require_secret_key()

    def sign(self, *, document):
        payload = build_signed_envelope(document)
        return {"xml_hash": _save_artifact(document, payload)}

    def submit(self, *, document):
        payload = _load_artifact(document)
        token = _get_token()
        sender_body, sender_dv = _split_rut(settings.SII_SENDER_RUT)
        company_body, company_dv = _split_rut(document.issuer_rut)
        files = {"archivo": (f"DTE_{document.type_code}_{document.folio}.xml", payload, "text/xml")}
        data = {"rutSender": sender_body, "dvSender": sender_dv, "rutCompany": company_body, "dvCompany": company_dv}
        try:
            response = requests.post(_endpoints().upload, data=data, files=files, headers={"Cookie": f"TOKEN={token}"}, timeout=settings.SII_HTTP_TIMEOUT)
            response.raise_for_status()
        except (requests.Timeout, requests.ConnectionError) as error:
            raise ProviderSendUncertain(str(error)) from error
        except requests.RequestException as error:
            raise DTEValidationError(f"SII upload HTTP error: {error}") from error
        root, first = _parse_sii_response(response.text)
        status = first("STATUS")
        if status != "0":
            raise DTEValidationError(f"SII rechazo upload con STATUS {status or 'desconocido'}.")
        track_id = first("TRACKID")
        if not track_id:
            raise DTEValidationError("SII acepto upload pero no devolvio TRACKID.")
        return {"track_id": track_id}

    def refresh_status(self, *, document):
        token = _get_token()
        company_body, company_dv = _split_rut(document.issuer_rut)
        if document.provider_track_id:
            value = _soap_rpc(
                _endpoints().query_upload,
                f"https://{_endpoints().base_host}/DTEWS/QueryEstUp.jws",
                "getEstUp",
                [("RutCompania", company_body), ("DvCompania", company_dv), ("TrackId", document.provider_track_id), ("Token", token)],
            )
            _, first = _parse_sii_response(value)
            upload_code = first("ESTADO")
            if upload_code in {"RSC", "RFR", "RCT"}:
                return {"state": ElectronicTaxDocument.State.REJECTED, "code": upload_code, "message": first("GLOSA")}
            if upload_code != "EPR":
                return {"state": ElectronicTaxDocument.State.PROCESSING, "code": upload_code or "PROCESSING", "message": first("GLOSA") or "Envio en proceso"}
        sender_body, sender_dv = _split_rut(settings.SII_SENDER_RUT)
        receiver_body, receiver_dv = _split_rut(document.receiver_rut)
        value = _soap_rpc(
            _endpoints().query_dte,
            f"https://{_endpoints().base_host}/DTEWS/QueryEstDte.jws",
            "getEstDte",
            [
                ("RutConsultante", sender_body), ("DvConsultante", sender_dv),
                ("RutCompania", company_body), ("DvCompania", company_dv),
                ("RutReceptor", receiver_body), ("DvReceptor", receiver_dv),
                ("TipoDte", document.type_code), ("FolioDte", document.folio),
                ("FechaEmisionDte", document.issue_date.strftime("%d-%m-%Y")),
                ("MontoDte", document.total_amount), ("Token", token),
            ],
        )
        _, first = _parse_sii_response(value)
        code = first("ESTADO") or first("ERR_CODE") or "UNKNOWN"
        message = first("GLOSA_ERR") or first("GLOSA_ESTADO") or first("GLOSA")
        return {"state": _map_document_status(code, message), "code": code, "message": message}


def get_sii_provider():
    return SIIElectronicTaxProvider()
