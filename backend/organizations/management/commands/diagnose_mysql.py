from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.db.models import Count, F
from django.db.models.functions import Lower

from catalog.models import Product, ProductVariant
from customers.models import Customer
from inventory.models import InventoryStock
from orders.models import Order, OrderItem
from organizations.models import Branch, Company, Warehouse
from portal.models import CustomerPortalAccount
from sales.models import Sale


class Command(BaseCommand):
    help = "Audita de forma read-only la instancia MySQL y la integridad multiempresa."

    def add_arguments(self, parser):
        parser.add_argument(
            "--strict",
            action="store_true",
            help="Devuelve error si hay migraciones pendientes o inconsistencias críticas.",
        )
        parser.add_argument(
            "--allow-non-mysql",
            action="store_true",
            help="Permite ejecutar las comprobaciones ORM sobre SQLite durante QA.",
        )

    def handle(self, *args, **options):
        connection.ensure_connection()
        is_mysql = connection.vendor == "mysql"
        if not is_mysql and not options["allow_non_mysql"]:
            raise CommandError(
                f"La conexión activa es {connection.vendor!r}; esta auditoría debe ejecutarse contra MySQL."
            )

        errors: list[str] = []
        warnings: list[str] = []

        self.stdout.write(self.style.MIGRATE_HEADING("TuPymeGestiona — diagnóstico de base de datos"))
        self.stdout.write(f"Motor Django: {connection.vendor}")
        self.stdout.write(f"DEBUG: {settings.DEBUG}")

        executor = MigrationExecutor(connection)
        pending = executor.migration_plan(executor.loader.graph.leaf_nodes())
        if pending:
            pending_names = [
                f"{migration.app_label}.{migration.name}"
                for migration, _ in pending
            ]
            errors.append("Migraciones pendientes: " + ", ".join(pending_names))
            self.stdout.write(
                self.style.WARNING(
                    f"Migraciones pendientes ({len(pending_names)}):"
                )
            )
            for name in pending_names:
                self.stdout.write(f"  - {name}")
        else:
            self.stdout.write(self.style.SUCCESS("Migraciones: al día"))

        if is_mysql:
            self._mysql_runtime_checks(errors, warnings)

        if pending:
            self.stdout.write(
                self.style.WARNING(
                    "\nIntegridad de dominio omitida: el esquema aún no está completamente migrado."
                )
            )
            if warnings:
                self.stdout.write("\nAdvertencias:")
                for warning in warnings:
                    self.stdout.write(self.style.WARNING(f"  - {warning}"))
            self.stdout.write("\nProblemas críticos:")
            for error in errors:
                self.stdout.write(self.style.ERROR(f"  - {error}"))
            if options["strict"]:
                raise CommandError(
                    f"Diagnóstico detenido: hay {len(pending_names)} migración(es) pendiente(s)."
                )
            return

        checks = {
            "Bodegas con sucursal de otra empresa": Warehouse.objects.filter(branch__isnull=False)
            .exclude(company_id=F("branch__company_id"))
            .count(),
            "Productos con categoría de otra empresa": Product.objects.exclude(
                company_id=F("category__company_id")
            ).count(),
            "Productos con marca de otra empresa": Product.objects.filter(brand__isnull=False)
            .exclude(company_id=F("brand__company_id"))
            .count(),
            "Stock cruzado entre empresas": InventoryStock.objects.exclude(
                warehouse__company_id=F("variant__product__company_id")
            ).count(),
            "Stock negativo": InventoryStock.objects.filter(quantity__lt=0).count(),
            "Pedidos con sucursal de otra empresa": Order.objects.exclude(
                company_id=F("branch__company_id")
            ).count(),
            "Pedidos con bodega de otra empresa": Order.objects.exclude(
                company_id=F("warehouse__company_id")
            ).count(),
            "Pedidos con cliente de otra empresa": Order.objects.exclude(
                company_id=F("customer__company_id")
            ).count(),
            "Items de pedido con producto de otra empresa": OrderItem.objects.exclude(
                order__company_id=F("variant__product__company_id")
            ).count(),
            "Ventas con pedido de otra empresa": Sale.objects.exclude(
                company_id=F("order__company_id")
            ).count(),
            "Ventas con sucursal de otra empresa": Sale.objects.exclude(
                company_id=F("branch__company_id")
            ).count(),
            "Ventas con pago superior al total": Sale.objects.filter(
                paid_amount__gt=F("total_amount")
            ).count(),
            "Cuentas portal con cliente de otra empresa": CustomerPortalAccount.objects.exclude(
                company_id=F("customer__company_id")
            ).count(),
        }

        duplicate_skus = (
            ProductVariant.objects.values("product__company_id", "sku")
            .annotate(total=Count("id"))
            .filter(total__gt=1)
            .count()
        )
        checks["SKU duplicados dentro de una empresa"] = duplicate_skus

        duplicate_customer_codes = (
            Customer.objects.values("company_id", "code")
            .annotate(total=Count("id"))
            .filter(total__gt=1)
            .count()
        )
        checks["Códigos de cliente duplicados por empresa"] = duplicate_customer_codes

        duplicate_ruts = (
            Company.objects.exclude(rut="")
            .annotate(rut_normalized=Lower("rut"))
            .values("rut_normalized")
            .annotate(total=Count("id"))
            .filter(total__gt=1)
            .count()
        )
        checks["RUT de empresa duplicados"] = duplicate_ruts

        self.stdout.write("\nIntegridad de dominio:")
        for label, count in checks.items():
            if count:
                errors.append(f"{label}: {count}")
                self.stdout.write(self.style.ERROR(f"  [ERROR] {label}: {count}"))
            else:
                self.stdout.write(self.style.SUCCESS(f"  [OK] {label}: 0"))

        self.stdout.write("\nVolumen actual:")
        counts = {
            "empresas": Company.objects.count(),
            "sucursales": Branch.objects.count(),
            "bodegas": Warehouse.objects.count(),
            "productos": Product.objects.count(),
            "variantes": ProductVariant.objects.count(),
            "clientes": Customer.objects.count(),
            "pedidos": Order.objects.count(),
            "ventas": Sale.objects.count(),
        }
        self.stdout.write("  " + " | ".join(f"{key}={value}" for key, value in counts.items()))

        if settings.DEBUG:
            warnings.append("DJANGO_DEBUG está activo; es correcto para desarrollo local, no para producción.")

        if warnings:
            self.stdout.write("\nAdvertencias:")
            for warning in warnings:
                self.stdout.write(self.style.WARNING(f"  - {warning}"))

        if errors:
            self.stdout.write("\nProblemas críticos:")
            for error in errors:
                self.stdout.write(self.style.ERROR(f"  - {error}"))
            if options["strict"]:
                raise CommandError(f"Diagnóstico fallido con {len(errors)} problema(s) crítico(s).")
        else:
            self.stdout.write(self.style.SUCCESS("\nDiagnóstico crítico: OK"))

    def _mysql_runtime_checks(self, errors, warnings):
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT VERSION(), @@GLOBAL.sql_mode, @@SESSION.sql_mode, "
                "@@character_set_database, @@collation_database"
            )
            version, global_sql_mode, session_sql_mode, charset, collation = cursor.fetchone()
            cursor.execute(
                """
                SELECT table_name, engine
                FROM information_schema.tables
                WHERE table_schema = DATABASE()
                  AND table_type = 'BASE TABLE'
                  AND (engine IS NULL OR engine <> 'InnoDB')
                ORDER BY table_name
                """
            )
            non_innodb = cursor.fetchall()

        self.stdout.write(f"MySQL: {version}")
        self.stdout.write(f"sql_mode global: {global_sql_mode}")
        self.stdout.write(f"sql_mode sesión Django: {session_sql_mode}")
        self.stdout.write(f"charset/collation: {charset}/{collation}")

        session_modes = {item.strip().upper() for item in (session_sql_mode or "").split(",")}
        global_modes = {item.strip().upper() for item in (global_sql_mode or "").split(",")}
        if "STRICT_TRANS_TABLES" not in session_modes and "STRICT_ALL_TABLES" not in session_modes:
            errors.append("La sesión Django no tiene un modo STRICT activo.")
        if "STRICT_TRANS_TABLES" not in global_modes and "STRICT_ALL_TABLES" not in global_modes:
            warnings.append(
                "El sql_mode global de MySQL no es STRICT; Django lo endurece por conexión, "
                "pero conviene corregir la configuración del servidor."
            )
        if str(charset).lower() != "utf8mb4":
            warnings.append(f"La base usa charset {charset}; se recomienda utf8mb4.")
        if non_innodb:
            errors.append(
                "Tablas que no usan InnoDB: "
                + ", ".join(f"{name}({engine})" for name, engine in non_innodb)
            )
