from django.core.management.base import BaseCommand, CommandError

from external_payments.provider import MercadoPagoNotConfigured, validate_public_configuration


class Command(BaseCommand):
    help = "Valida la configuración de Mercado Pago sin realizar tráfico externo."

    def handle(self, *args, **options):
        try:
            _, return_base, webhook_url = validate_public_configuration()
        except MercadoPagoNotConfigured as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(self.style.SUCCESS("Mercado Pago configurado para pruebas."))
        self.stdout.write(f"Return base: {return_base}")
        self.stdout.write(f"Webhook: {webhook_url}")
        self.stdout.write("No se realizó ninguna llamada externa.")
