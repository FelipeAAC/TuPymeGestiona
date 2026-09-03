import base64
import importlib.util
import os
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db.models import F

from electronic_tax.models import FolioAuthorization, TaxCompanyProfile
from organizations.models import Company


class Command(BaseCommand):
    help = "Valida configuracion local para certificacion SII sin realizar llamadas de red."

    def add_arguments(self, parser):
        parser.add_argument("--company", type=int, required=True)
        parser.add_argument(
            "--type-code",
            type=int,
            action="append",
            dest="type_codes",
            default=[],
            help="Tipo DTE a validar (repetible). Por defecto: 33,34,56,61.",
        )

    def handle(self, *args, **options):
        company = Company.objects.filter(pk=options["company"]).first()
        if company is None:
            raise CommandError("La empresa indicada no existe.")
        type_codes = options["type_codes"] or [33, 34, 56, 61]
        failures = []
        warnings = []

        def require(label, condition, detail):
            if condition:
                self.stdout.write(self.style.SUCCESS(f"OK   {label}"))
            else:
                failures.append(f"{label}: {detail}")
                self.stdout.write(self.style.ERROR(f"FAIL {label}: {detail}"))

        require(
            "SII_ENVIRONMENT",
            settings.SII_ENVIRONMENT in {"certification", "production"},
            "debe ser certification o production",
        )
        require("SII_ADAPTER_ENABLED", settings.SII_ADAPTER_ENABLED, "debe estar true para operar")
        require("SII_SENDER_RUT", bool(settings.SII_SENDER_RUT), "RUT de firmante no configurado")

        secret_ok = False
        if settings.SII_SECRET_KEY:
            try:
                secret_ok = len(base64.urlsafe_b64decode(settings.SII_SECRET_KEY.encode("ascii"))) == 32
            except Exception:
                secret_ok = False
        require("SII_SECRET_KEY", secret_ok, "debe ser base64 URL-safe de 32 bytes")

        pfx = Path(settings.SII_CERTIFICATE_PFX_PATH)
        password_env = settings.SII_CERTIFICATE_PASSWORD_ENV
        require("Certificado PFX", pfx.is_file(), "ruta PFX inexistente")
        require("Password PFX", bool(os.getenv(password_env, "")), f"falta variable de entorno {password_env}")

        xsd_dir = Path(settings.SII_XSD_DIR)
        dte_xsds = ["EnvioDTE_v10.xsd", "DTE_v10.xsd", "SiiTypes_v10.xsd", "xmldsignature_v10.xsd"]
        require(
            "Schemas DTE",
            xsd_dir.is_dir() and all((xsd_dir / name).is_file() for name in dte_xsds),
            "faltan schemas oficiales DTE",
        )
        exchange_dir = Path(settings.SII_EXCHANGE_XSD_DIR)
        require(
            "Schema intercambio",
            exchange_dir.is_dir() and (exchange_dir / "RespuestaEnvioDTE_v10.xsd").is_file(),
            "falta RespuestaEnvioDTE_v10.xsd",
        )
        trusted_dir = Path(settings.SII_CAF_TRUSTED_PUBLIC_KEYS_DIR)
        require("Llaves publicas CAF", trusted_dir.is_dir(), "directorio de llaves confiables inexistente")

        for package in ("cryptography", "lxml", "requests", "reportlab", "pdf417gen", "PIL"):
            require(
                f"Dependencia {package}",
                importlib.util.find_spec(package) is not None,
                "paquete Python no instalado",
            )

        profile = TaxCompanyProfile.objects.filter(company=company, active=True).first()
        require("Perfil tributario", profile is not None, "no existe perfil tributario activo")
        if profile is not None:
            for field, label in (
                ("rut", "RUT emisor"),
                ("legal_name", "Razon social"),
                ("business_activity", "Giro"),
                ("address", "Direccion"),
                ("commune", "Comuna"),
                ("economic_activity_code", "Actividad economica"),
                ("sii_resolution_number", "Numero resolucion SII"),
                ("sii_resolution_date", "Fecha resolucion SII"),
                ("sii_regional_office", "Direccion regional SII"),
                ("tax_email", "Correo tributario emisor"),
            ):
                require(label, bool(getattr(profile, field)), f"TaxCompanyProfile.{field} esta vacio")

        for type_code in type_codes:
            active = FolioAuthorization.objects.filter(
                company=company,
                type_code=type_code,
                status=FolioAuthorization.Status.ACTIVE,
            ).filter(next_folio__lte=F("end_folio")).exists()
            require(f"CAF DTE {type_code}", active, "no hay rango ACTIVE con folios disponibles")

        if not settings.SII_EXCHANGE_ENABLED:
            warnings.append("SII_EXCHANGE_ENABLED esta false; habilitarlo solo al configurar correo real.")
        if not settings.SII_EXCHANGE_FROM_EMAIL and (profile is None or not profile.tax_email):
            failures.append("Correo de intercambio: falta SII_EXCHANGE_FROM_EMAIL y TaxCompanyProfile.tax_email.")

        for warning in warnings:
            self.stdout.write(self.style.WARNING(f"WARN {warning}"))

        if failures:
            raise CommandError(
                "Preflight SII incompleto. Corrige los FAIL antes de usar activos reales; no se realizaron llamadas de red."
            )
        self.stdout.write(self.style.SUCCESS("Preflight SII local completo. No se realizaron llamadas de red."))
