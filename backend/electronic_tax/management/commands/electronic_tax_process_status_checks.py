import json

from django.core.management.base import BaseCommand, CommandError

from electronic_tax.operations import process_status_check_tasks


class Command(BaseCommand):
    help = "Lista o ejecuta consultas SII encoladas. Por defecto es dry-run y no realiza red."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=20)
        parser.add_argument(
            "--execute",
            action="store_true",
            help="Ejecuta consultas remotas. Sin esta bandera el comando solo informa tareas vencidas.",
        )

    def handle(self, *args, **options):
        limit = options["limit"]
        if limit < 1 or limit > 500:
            raise CommandError("--limit debe estar entre 1 y 500.")
        try:
            result = process_status_check_tasks(limit=limit, execute=options["execute"])
        except RuntimeError as error:
            raise CommandError(str(error)) from error
        self.stdout.write(json.dumps(result, ensure_ascii=False, indent=2, default=str))
