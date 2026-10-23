from django.core.management.base import BaseCommand, CommandError

from accounts.models import User


class Command(BaseCommand):
    help = "Delegates the permanent-deletion capability to one existing platform administrator."

    def add_arguments(self, parser):
        parser.add_argument("--email", required=True)

    def handle(self, *args, **options):
        email = options["email"].strip().lower()
        user = User.objects.filter(email__iexact=email).first()
        if user is None:
            raise CommandError(f"No existe una cuenta con el correo '{email}'.")
        if not user.platform_admin:
            raise CommandError("La cuenta debe ser PLATFORM_ADMIN antes de delegar la capacidad destructiva.")
        if user.destructive_admin:
            self.stdout.write(f"La cuenta {user.email} ya tiene capacidad destructiva.")
            return
        user.destructive_admin = True
        user.save(update_fields=["destructive_admin"])
        self.stdout.write(
            self.style.SUCCESS(
                f"Cuenta {user.email} habilitada como PLATFORM_DATA_DESTRUCTIVE_ADMIN."
            )
        )
