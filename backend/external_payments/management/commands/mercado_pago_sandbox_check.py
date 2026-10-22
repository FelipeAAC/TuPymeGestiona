from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from external_payments.provider import MercadoPagoNotConfigured, validate_public_configuration


class Command(BaseCommand):
    help = "Valida la configuración local de Mercado Pago Sandbox sin mostrar secretos ni realizar cobros."

    def handle(self, *args, **options):
        try:
            _token, return_base, webhook_url = validate_public_configuration()
        except MercadoPagoNotConfigured as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(self.style.SUCCESS("Configuración de Mercado Pago Sandbox válida."))
        self.stdout.write(f"Retorno frontend: {return_base}")
        self.stdout.write(f"Webhook backend: {webhook_url}")
        self.stdout.write(f"Modo live aceptado: {settings.MERCADO_PAGO_ACCEPT_LIVE_MODE}")
        self.stdout.write("No se realizó ninguna solicitud de pago.")
