import base64
import os
import tempfile
from datetime import datetime, timedelta, timezone as dt_timezone
from pathlib import Path
from unittest.mock import patch

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.x509.oid import NameOID
from django.test import override_settings
from lxml import etree

from .models import ElectronicTaxArtifact, FolioAuthorizationSecret
from .services import DTEValidationError, reserve_folio, validate_document
from .sii_adapter import SIIElectronicTaxProvider, import_caf
from .tests import ElectronicTaxFixtureMixin
from django.test import TestCase


class SIIAdapterTests(ElectronicTaxFixtureMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.secret_key = base64.urlsafe_b64encode(os.urandom(32)).decode("ascii")
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.authority_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        public_pem = self.authority_key.public_key().public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        Path(self.tempdir.name, "100.pem").write_bytes(public_pem)

    def _caf_bytes(self, *, valid_signature=True):
        caf_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        numbers = caf_key.public_key().public_numbers()
        root = etree.Element("AUTORIZACION")
        caf = etree.SubElement(root, "CAF", version="1.0")
        da = etree.SubElement(caf, "DA")
        etree.SubElement(da, "RE").text = "76123456-0"
        etree.SubElement(da, "RS").text = "Empresa Uno SpA"
        etree.SubElement(da, "TD").text = "33"
        rng = etree.SubElement(da, "RNG")
        etree.SubElement(rng, "D").text = "100"
        etree.SubElement(rng, "H").text = "110"
        etree.SubElement(da, "FA").text = "2026-09-03"
        rsapk = etree.SubElement(da, "RSAPK")
        etree.SubElement(rsapk, "M").text = base64.b64encode(
            numbers.n.to_bytes((numbers.n.bit_length() + 7) // 8, "big")
        ).decode("ascii")
        etree.SubElement(rsapk, "E").text = base64.b64encode(
            numbers.e.to_bytes((numbers.e.bit_length() + 7) // 8, "big")
        ).decode("ascii")
        etree.SubElement(da, "IDK").text = "100"
        signature = self.authority_key.sign(
            etree.tostring(da, encoding="ISO-8859-1", with_tail=False),
            padding.PKCS1v15(),
            hashes.SHA1(),
        )
        if not valid_signature:
            signature = b"x" * len(signature)
        etree.SubElement(caf, "FRMA", algoritmo="SHA1withRSA").text = base64.b64encode(signature).decode("ascii")
        etree.SubElement(root, "RSASK").text = caf_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.TraditionalOpenSSL,
            serialization.NoEncryption(),
        ).decode("ascii")
        etree.SubElement(root, "RSAPUBK").text = caf_key.public_key().public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode("ascii")
        return etree.tostring(root, encoding="ISO-8859-1", xml_declaration=True)

    def _certificate_material(self):
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        subject = issuer = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "SII test signer")])
        cert = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(issuer)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(datetime.now(dt_timezone.utc) - timedelta(days=1))
            .not_valid_after(datetime.now(dt_timezone.utc) + timedelta(days=30))
            .sign(key, hashes.SHA256())
        )
        return key, cert, None

    @override_settings(SII_CAF_TRUSTED_PUBLIC_KEYS_DIR="")
    def test_import_caf_verifies_frma_encrypts_and_is_idempotent(self):
        with override_settings(
            SII_SECRET_KEY=self.secret_key,
            SII_CAF_TRUSTED_PUBLIC_KEYS_DIR=self.tempdir.name,
        ):
            caf_bytes = self._caf_bytes()
            authorization, created = import_caf(
                company=self.company,
                caf_bytes=caf_bytes,
                idempotency_key="caf-1",
                actor=self.user,
                source_label="caf.xml",
            )
            self.assertTrue(created)
            self.assertEqual(authorization.start_folio, 100)
            secret = FolioAuthorizationSecret.objects.get(authorization=authorization)
            self.assertNotIn(b"BEGIN RSA PRIVATE KEY", bytes(secret.encrypted_caf))
            replay, created = import_caf(
                company=self.company,
                caf_bytes=caf_bytes,
                idempotency_key="caf-1",
                actor=self.user,
                source_label="caf.xml",
            )
            self.assertFalse(created)
            self.assertEqual(replay.id, authorization.id)

    def test_import_caf_rejects_invalid_sii_signature(self):
        with override_settings(
            SII_SECRET_KEY=self.secret_key,
            SII_CAF_TRUSTED_PUBLIC_KEYS_DIR=self.tempdir.name,
        ):
            with self.assertRaises(DTEValidationError):
                import_caf(
                    company=self.company,
                    caf_bytes=self._caf_bytes(valid_signature=False),
                    idempotency_key="caf-bad",
                    actor=self.user,
                )

    def test_sign_builds_encrypted_envelope_without_network(self):
        with override_settings(
            SII_ADAPTER_ENABLED=True,
            SII_ENVIRONMENT="certification",
            SII_SECRET_KEY=self.secret_key,
            SII_SENDER_RUT="12345678-5",
            SII_CAF_TRUSTED_PUBLIC_KEYS_DIR=self.tempdir.name,
        ):
            profile = self.company.electronic_tax_profile
            profile.economic_activity_code = 620200
            profile.sii_resolution_number = 80
            profile.sii_resolution_date = datetime(2014, 8, 22).date()
            profile.save()
            import_caf(
                company=self.company,
                caf_bytes=self._caf_bytes(),
                idempotency_key="caf-sign",
                actor=self.user,
            )
            document = self.create_document()
            document = validate_document(
                document=document,
                expected_version=document.version,
                idempotency_key="validate-sign",
                actor=self.user,
            )[0]
            reserve_folio(document=document, actor=self.user)
            document.refresh_from_db()
            with patch("electronic_tax.sii_adapter._certificate_material", return_value=self._certificate_material()), patch(
                "electronic_tax.sii_adapter._validate_xsd", return_value=None
            ):
                result = SIIElectronicTaxProvider().sign(document=document)
            self.assertEqual(len(result["xml_hash"]), 64)
            artifact = ElectronicTaxArtifact.objects.get(document=document)
            self.assertNotIn(b"<EnvioDTE", bytes(artifact.encrypted_payload))
