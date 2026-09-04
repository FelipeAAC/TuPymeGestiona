from django.core.management.base import BaseCommand

from transactional_notifications.services import mark_stale_sending_uncertain


class Command(BaseCommand):
    help = "Marca como inciertos los envíos SMTP que quedaron SENDING demasiado tiempo; no los reenvía."

    def handle(self, *args, **options):
        count = mark_stale_sending_uncertain()
        self.stdout.write(self.style.SUCCESS(f"Marcados UNCERTAIN: {count}"))
