from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError


User = get_user_model()


class Command(BaseCommand):
    help = "Promueve explícitamente una cuenta existente a administrador general."

    def add_arguments(self, parser):
        parser.add_argument(
            "--email",
            help="Correo exacto de la cuenta que se habilitará.",
        )

    def handle(self, *args, **options):
        raw_email = options.get("email")
        email = str(raw_email or "").strip()
        if not email:
            raise CommandError("Debes indicar --email con el correo de una cuenta existente.")

        users = list(
            User.objects.filter(email__iexact=email).order_by("pk")
        )
        if not users:
            raise CommandError(f"No existe una cuenta con el correo {email!r}.")
        if len(users) > 1:
            raise CommandError(
                f"El correo {email!r} coincide con varias cuentas; no se realizó ningún cambio."
            )

        user = users[0]
        if user.platform_admin:
            self.stdout.write(
                self.style.WARNING(
                    f"La cuenta {user.email} ya es administrador general. No se realizó ningún cambio."
                )
            )
            return

        user.platform_admin = True
        user.save(update_fields=["platform_admin"])
        self.stdout.write(
            self.style.SUCCESS(
                f"Cuenta {user.email} habilitada como administrador general."
            )
        )
