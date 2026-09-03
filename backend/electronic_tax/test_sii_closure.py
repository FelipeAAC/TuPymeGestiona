import base64
import io
import sys
from datetime import date
from types import SimpleNamespace
from unittest.mock import patch

from django.core import mail
from django.test import override_settings
from PIL import Image
from reportlab.lib.units import cm

from .exchange import deliver_to_receiver, ingest_receiver_response
from .models import (
    ElectronicTaxArtifact,
    ElectronicTaxEvent,
    ElectronicTaxExchange,
    TaxCompanyProfile,
)
from .ride import _render_pdf417_png, get_or_create_ride
from .services import DTEProviderNotConfiguredError, DTEValidationError
from .sii_adapter import _decrypt, _encrypt
from .tests import ElectronicTaxFixtureMixin
from django.test import TestCase


SECRET_KEY = base64.urlsafe_b64encode(b"C" * 32).decode("ascii")


class SIIClosureTests(ElectronicTaxFixtureMixin, TestCase):
    def setUp(self):
        super().setUp()
        profile = TaxCompanyProfile.objects.get(company=self.company)
        profile.economic_activity_code = "620200"
        profile.sii_resolution_number = 80
        profile.sii_resolution_date = date(2014, 8, 22)
        profile.sii_regional_office = "DIRECCION REGIONAL SANTIAGO"
        profile.save()

    def signed_document(self, *, folio=100):
        document = self.accept_document(self.create_document(), folio=folio)
        payload = f"""<?xml version='1.0' encoding='ISO-8859-1'?>
<EnvioDTE xmlns='http://www.sii.cl/SiiDte'>
  <SetDTE ID='SetDoc'>
    <DTE version='1.0'>
      <Documento ID='F{document.type_code}T{folio}'>
        <TED version='1.0'>
          <DD><RE>{document.issuer_rut}</RE><TD>{document.type_code}</TD><F>{folio}</F><FE>{document.issue_date.isoformat()}</FE><RR>{document.receiver_rut}</RR><RSR>{document.receiver_legal_name}</RSR><MNT>{int(document.total_amount)}</MNT><IT1>Producto A</IT1><CAF version='1.0'/><TSTED>2026-09-03T12:00:00</TSTED></DD>
          <FRMT algoritmo='SHA1withRSA'>firma</FRMT>
        </TED>
      </Documento>
    </DTE>
  </SetDTE>
</EnvioDTE>""".encode("iso-8859-1")
        nonce, encrypted = _encrypt(payload)
        ElectronicTaxArtifact.objects.create(
            document=document,
            kind=ElectronicTaxArtifact.Kind.SIGNED_ENVELOPE,
            content_hash="0" * 64,
            nonce=nonce,
            encrypted_payload=encrypted,
        )
        return document

    @staticmethod
    def dummy_png(width=900, height=350):
        output = io.BytesIO()
        Image.new("1", (width, height), 1).save(output, format="PNG")
        return output.getvalue()

    def test_pdf417_renderer_uses_sii_parameters(self):
        calls = []

        def encode(payload, *, columns, security_level):
            calls.append((payload, columns, security_level))
            return [[1, 0, 1]]

        def render_image(codes, *, scale, ratio, padding):
            self.assertEqual(scale, 2)
            self.assertEqual(ratio, 3)
            self.assertEqual(padding, 75)
            return Image.new("1", (900, 350), 1)

        fake_module = SimpleNamespace(encode=encode, render_image=render_image)
        with patch.dict(sys.modules, {"pdf417gen": fake_module}):
            png, width, height = _render_pdf417_png(b"<TED>dato</TED>")

        self.assertTrue(png.startswith(b"\x89PNG"))
        self.assertTrue(calls)
        self.assertTrue(all(call[2] == 5 for call in calls))
        self.assertGreaterEqual(width / cm, 4.5)
        self.assertLessEqual(width / cm, 9.0)
        self.assertGreaterEqual(height / cm, 2.0)
        self.assertLessEqual(height / cm, 4.0)

    @override_settings(SII_SECRET_KEY=SECRET_KEY)
    def test_ride_generates_and_caches_encrypted_pdf(self):
        document = self.signed_document()
        barcode = (self.dummy_png(), 8 * cm, 3 * cm)
        with patch("electronic_tax.ride._render_pdf417_png", return_value=barcode):
            payload, created = get_or_create_ride(document=document, actor=self.user)
            cached, created_again = get_or_create_ride(document=document, actor=self.user)

        self.assertTrue(created)
        self.assertFalse(created_again)
        self.assertEqual(cached, payload)
        self.assertTrue(payload.startswith(b"%PDF"))
        # Facturas 33/34 incluyen copia normal y copia CEDIBLE.
        self.assertGreaterEqual(payload.count(b"/Type /Page"), 2)
        artifact = ElectronicTaxArtifact.objects.get(
            document=document, kind=ElectronicTaxArtifact.Kind.RIDE_PDF
        )
        self.assertEqual(
            _decrypt(bytes(artifact.nonce), bytes(artifact.encrypted_payload)), payload
        )
        self.assertTrue(
            ElectronicTaxEvent.objects.filter(
                document=document, event_type=ElectronicTaxEvent.EventType.RIDE_GENERATED
            ).exists()
        )

    @override_settings(
        SII_SECRET_KEY=SECRET_KEY,
        SII_EXCHANGE_ENABLED=True,
        SII_EXCHANGE_FROM_EMAIL="dte@empresa.cl",
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    )
    def test_delivery_uses_snapshot_email_and_is_idempotent(self):
        document = self.signed_document(folio=101)
        with patch(
            "electronic_tax.exchange.get_or_create_receiver_envelope",
            return_value=(b"<EnvioDTE/>", True),
        ), patch(
            "electronic_tax.exchange.get_or_create_ride",
            return_value=(b"%PDF-1.4 fake", True),
        ):
            exchange, changed = deliver_to_receiver(
                document=document,
                expected_version=document.version,
                idempotency_key="receiver-send-101",
                actor=self.user,
            )
            replay, changed_again = deliver_to_receiver(
                document=document,
                expected_version=document.version,
                idempotency_key="receiver-send-101",
                actor=self.user,
            )

        self.assertTrue(changed)
        self.assertFalse(changed_again)
        self.assertEqual(exchange.pk, replay.pk)
        self.assertEqual(exchange.delivery_state, ElectronicTaxExchange.DeliveryState.SENT)
        self.assertEqual(exchange.recipient_email, document.receiver_tax_email)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [document.receiver_tax_email])
        self.assertEqual(len(mail.outbox[0].attachments), 2)
        self.assertEqual(exchange.send_attempts, 1)
        self.assertEqual(
            ElectronicTaxEvent.objects.filter(
                document=document,
                event_type=ElectronicTaxEvent.EventType.RECEIVER_EXCHANGE_SENT,
            ).count(),
            1,
        )

    @override_settings(SII_SECRET_KEY=SECRET_KEY, SII_EXCHANGE_ENABLED=False)
    def test_delivery_refuses_disabled_exchange(self):
        document = self.signed_document(folio=102)
        with self.assertRaises(DTEProviderNotConfiguredError):
            deliver_to_receiver(
                document=document,
                expected_version=document.version,
                idempotency_key="receiver-send-disabled",
                actor=self.user,
            )

    @staticmethod
    def receiver_response_xml(document, *, responder=None, state="2"):
        responder = responder or document.receiver_rut
        return f"""<?xml version='1.0' encoding='ISO-8859-1'?>
<RespuestaEnvioDTE xmlns='http://www.sii.cl/SiiDte'>
  <Resultado ID='Respuesta'>
    <Caratula version='1.0'><RutResponde>{responder}</RutResponde><RutRecibe>{document.issuer_rut}</RutRecibe></Caratula>
    <ResultadoDTE><TipoDTE>{document.type_code}</TipoDTE><Folio>{document.folio}</Folio><EstadoDTE>{state}</EstadoDTE><EstadoDTEGlosa>RECHAZADO POR RECEPTOR</EstadoDTEGlosa></ResultadoDTE>
  </Resultado>
  <Signature xmlns='http://www.w3.org/2000/09/xmldsig#'><SignedInfo/></Signature>
</RespuestaEnvioDTE>""".encode("iso-8859-1")

    @override_settings(SII_SECRET_KEY=SECRET_KEY)
    def test_receiver_response_maps_reject_and_is_idempotent(self):
        document = self.signed_document(folio=103)
        ElectronicTaxExchange.objects.create(
            document=document,
            delivery_state=ElectronicTaxExchange.DeliveryState.SENT,
            recipient_email=document.receiver_tax_email,
        )
        payload = self.receiver_response_xml(document)
        with patch("electronic_tax.exchange._validate_exchange_response_xsd"):
            exchange, changed = ingest_receiver_response(
                document=document,
                payload=payload,
                expected_version=document.version,
                idempotency_key="receiver-response-103",
                actor=self.user,
            )
            replay, changed_again = ingest_receiver_response(
                document=document,
                payload=payload,
                expected_version=document.version,
                idempotency_key="receiver-response-103",
                actor=self.user,
            )

        self.assertTrue(changed)
        self.assertFalse(changed_again)
        self.assertEqual(exchange.pk, replay.pk)
        self.assertEqual(
            exchange.receiver_response_state,
            ElectronicTaxExchange.ReceiverResponseState.REJECTED,
        )
        self.assertEqual(exchange.receiver_response_code, "2")
        artifact = ElectronicTaxArtifact.objects.get(
            document=document, kind=ElectronicTaxArtifact.Kind.RECEIVER_RESPONSE
        )
        self.assertEqual(
            _decrypt(bytes(artifact.nonce), bytes(artifact.encrypted_payload)), payload
        )
        self.assertTrue(
            ElectronicTaxEvent.objects.filter(
                document=document,
                event_type=ElectronicTaxEvent.EventType.RECEIVER_RESPONSE_RECEIVED,
            ).exists()
        )

    @override_settings(SII_SECRET_KEY=SECRET_KEY)
    def test_receiver_response_rejects_wrong_responder(self):
        document = self.signed_document(folio=104)
        ElectronicTaxExchange.objects.create(
            document=document,
            delivery_state=ElectronicTaxExchange.DeliveryState.SENT,
            recipient_email=document.receiver_tax_email,
        )
        payload = self.receiver_response_xml(document, responder="96543210-8")
        with patch("electronic_tax.exchange._validate_exchange_response_xsd"):
            with self.assertRaises(DTEValidationError):
                ingest_receiver_response(
                    document=document,
                    payload=payload,
                    expected_version=document.version,
                    idempotency_key="receiver-response-wrong",
                    actor=self.user,
                )
