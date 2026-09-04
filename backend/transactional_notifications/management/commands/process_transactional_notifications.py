from django.core.management.base import BaseCommand, CommandError

from transactional_notifications.services import (
    TransactionalEmailConfigurationError,
    process_pending_notifications,
)


class Command(BaseCommand):
    help = "Procesa la cola persistente de notificaciones transaccionales."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=100)

    def handle(self, *args, **options):
        try:
            results = process_pending_notifications(limit=max(1, options["limit"]))
        except TransactionalEmailConfigurationError as exc:
            raise CommandError(str(exc)) from exc
        sent = sum(1 for _, ok in results if ok)
        self.stdout.write(self.style.SUCCESS(f"Procesadas: {len(results)} | enviadas: {sent}"))
