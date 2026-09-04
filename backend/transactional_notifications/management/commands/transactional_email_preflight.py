from django.core.management.base import BaseCommand, CommandError

from transactional_notifications.services import preflight_errors


class Command(BaseCommand):
    help = "Valida la configuración SMTP sin abrir conexiones externas."

    def handle(self, *args, **options):
        errors = preflight_errors()
        if errors:
            raise CommandError("Preflight SMTP incompleto:\n- " + "\n- ".join(errors))
        self.stdout.write(self.style.SUCCESS("Preflight SMTP OK. No se realizó tráfico externo."))
