import json

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from accounts.access import get_access_context


User = get_user_model()


def _user_row(user):
    context = get_access_context(user)
    access_modes = list(context["access_modes"])
    return {
        "access_modes": access_modes,
        "ambiguous": len(access_modes) > 1,
        "default_app": context["default_app"],
        "destructive_admin": bool(user.destructive_admin),
        "email": user.email,
        "id": user.pk,
        "is_active": bool(user.is_active),
        "is_superuser": bool(user.is_superuser),
        "managed_companies": context["managed_companies"],
        "platform_admin": bool(user.platform_admin),
        "portal_companies": context["portal_companies"],
        "superuser_without_platform_admin": bool(
            user.is_superuser and not user.platform_admin
        ),
        "unclassified": not access_modes,
        "username": user.get_username(),
    }


def _build_report():
    rows = [_user_row(user) for user in User.objects.order_by("email", "pk")]
    summary = {
        "ambiguous": sum(1 for row in rows if row["ambiguous"]),
        "company_admin": sum("COMPANY_ADMIN" in row["access_modes"] for row in rows),
        "customer": sum("CUSTOMER" in row["access_modes"] for row in rows),
        "destructive_admin": sum(row["destructive_admin"] for row in rows),
        "platform_admin": sum("PLATFORM_ADMIN" in row["access_modes"] for row in rows),
        "superusers": sum(row["is_superuser"] for row in rows),
        "superusers_without_platform_admin": sum(
            row["superuser_without_platform_admin"] for row in rows
        ),
        "total_users": len(rows),
        "unclassified": sum(1 for row in rows if row["unclassified"]),
    }
    return {"summary": summary, "users": rows}


class Command(BaseCommand):
    help = "Emite un informe determinista de capacidades acumulables sin modificar cuentas."

    def add_arguments(self, parser):
        parser.add_argument(
            "--format",
            choices=("text", "json"),
            default="text",
            help="Formato de salida (por defecto: text).",
        )

    def handle(self, *args, **options):
        report = _build_report()
        if options.get("format") == "json":
            self.stdout.write(
                json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
            )
            return

        summary = report["summary"]
        self.stdout.write("Auditoría de capacidades de acceso (solo lectura)")
        self.stdout.write(
            "Resumen: "
            f"usuarios={summary['total_users']} "
            f"CUSTOMER={summary['customer']} "
            f"COMPANY_ADMIN={summary['company_admin']} "
            f"PLATFORM_ADMIN={summary['platform_admin']} "
            f"DESTRUCTIVE_ADMIN={summary['destructive_admin']} "
            f"ambiguos={summary['ambiguous']} "
            f"sin_capacidad={summary['unclassified']} "
            f"superusuarios_sin_platform_admin={summary['superusers_without_platform_admin']}"
        )
        for row in report["users"]:
            modes = ",".join(row["access_modes"]) or "-"
            flags = []
            if row["ambiguous"]:
                flags.append("AMBIGUO")
            if row["unclassified"]:
                flags.append("SIN_CAPACIDAD")
            if row["superuser_without_platform_admin"]:
                flags.append("SUPERUSER_SIN_PLATFORM_ADMIN")
            suffix = f" [{' | '.join(flags)}]" if flags else ""
            self.stdout.write(
                f"{row['id']}\t{row['email']}\t{row['username']}\t{modes}{suffix}"
            )
