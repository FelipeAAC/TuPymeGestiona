import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from organizations.models import Company

from electronic_tax.operations import integrity_snapshot


class Command(BaseCommand):
    help = "Escribe un manifiesto de control para contrastar respaldos MySQL; no crea ni reemplaza el backup."

    def add_arguments(self, parser):
        parser.add_argument("--output", required=True)
        parser.add_argument("--company-id", type=int)

    def handle(self, *args, **options):
        company = None
        if options.get("company_id"):
            company = Company.objects.filter(pk=options["company_id"]).first()
            if company is None:
                raise CommandError("La empresa indicada no existe.")
        output = Path(options["output"]).expanduser().resolve()
        if output.exists() and output.is_dir():
            raise CommandError("--output debe apuntar a un archivo JSON.")
        output.parent.mkdir(parents=True, exist_ok=True)
        manifest = integrity_snapshot(company=company)
        manifest["purpose"] = (
            "Control de integridad para un respaldo externo de MySQL. "
            "No contiene CAF, llaves, passwords, XML, RIDE ni payloads cifrados."
        )
        output.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True, default=str) + "\n",
            encoding="utf-8",
        )
        self.stdout.write(str(output))
