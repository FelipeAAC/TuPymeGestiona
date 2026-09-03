import json

from django.core.management.base import BaseCommand, CommandError

from organizations.models import Company

from electronic_tax.operations import integrity_snapshot


class Command(BaseCommand):
    help = "Verifica invariantes y genera un digest reproducible sin exportar CAF, XML ni secretos."

    def add_arguments(self, parser):
        parser.add_argument("--company-id", type=int)
        parser.add_argument("--fail-on-problem", action="store_true")

    def handle(self, *args, **options):
        company = None
        if options.get("company_id"):
            company = Company.objects.filter(pk=options["company_id"]).first()
            if company is None:
                raise CommandError("La empresa indicada no existe.")
        result = integrity_snapshot(company=company)
        self.stdout.write(json.dumps(result, ensure_ascii=False, indent=2, default=str))
        if options.get("fail_on_problem") and result["problems"]:
            raise CommandError("La verificacion de integridad encontro inconsistencias.")
