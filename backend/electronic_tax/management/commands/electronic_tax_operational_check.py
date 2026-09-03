import json

from django.core.management.base import BaseCommand, CommandError

from organizations.models import Company

from electronic_tax.models import ElectronicTaxOperationalAlert
from electronic_tax.operations import scan_all_operations


class Command(BaseCommand):
    help = "Recalcula alertas operativas de Facturacion Electronica sin realizar llamadas externas."

    def add_arguments(self, parser):
        parser.add_argument("--company-id", type=int)
        parser.add_argument("--fail-on-critical", action="store_true")

    def handle(self, *args, **options):
        company = None
        if options.get("company_id"):
            company = Company.objects.filter(pk=options["company_id"]).first()
            if company is None:
                raise CommandError("La empresa indicada no existe.")
        results = scan_all_operations(company=company)
        self.stdout.write(json.dumps(results, ensure_ascii=False, indent=2, default=str))
        if options.get("fail_on_critical"):
            alerts = ElectronicTaxOperationalAlert.objects.filter(
                status=ElectronicTaxOperationalAlert.Status.OPEN,
                severity=ElectronicTaxOperationalAlert.Severity.CRITICAL,
            )
            if company is not None:
                alerts = alerts.filter(company=company)
            if alerts.exists():
                raise CommandError("Hay alertas criticas abiertas de Facturacion Electronica.")
