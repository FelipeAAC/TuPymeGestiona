import random
import re
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.utils import timezone

from administration.services import create_company_for_user
from catalog.models import Brand, Category, Product, ProductVariant, Supplier
from customers.models import Customer
from inventory.models import InventoryStock
from orders.models import Order
from orders.services import cancel_order, confirm_order, create_draft_order, deliver_order, prepare_order
from organizations.models import (
    Branch,
    Company,
    CompanyMembership,
    CompanyRole,
    CompanyRolePermission,
    MembershipBranch,
    Permission,
    RoleAssignment,
    Warehouse,
)
from portal.models import CustomerPortalAccount
from sales.models import Payment, Sale, SaleEvent
from sales.services import create_sale, record_payment

User = get_user_model()

COMPANY_NAMES = [
    ("Mercado Aurora", "Alimentos y productos gourmet"),
    ("Casa Nativa", "Hogar, decoración y bienestar"),
    ("TecnoSur", "Tecnología y accesorios"),
    ("Verde Vivo", "Productos sustentables y jardinería"),
    ("Taller Andino", "Diseño, vestuario y manufactura local"),
    ("Ruta Café", "Café, té y equipamiento"),
    ("Mundo Mascota", "Alimentos y accesorios para mascotas"),
    ("Bazar Central", "Comercio minorista multiproducto"),
]

CATEGORY_NAMES = [
    "Destacados",
    "Novedades",
    "Uso diario",
    "Premium",
    "Ofertas",
    "Temporada",
]

BRAND_NAMES = ["Luma", "Norte", "Küyen", "Brava", "Origen", "Punto", "Nova", "Raíz"]
PRODUCT_BASES = [
    "Set artesanal", "Pack esencial", "Edición clásica", "Selección premium",
    "Kit urbano", "Línea natural", "Colección hogar", "Serie profesional",
    "Pack familiar", "Edición compacta", "Modelo activo", "Selección local",
]
FIRST_NAMES = ["Sofía", "Martín", "Valentina", "Tomás", "Camila", "Diego", "Antonia", "Lucas", "Isidora", "Benjamín"]
LAST_NAMES = ["Rojas", "Muñoz", "Soto", "Contreras", "Silva", "Martínez", "Sepúlveda", "Pérez", "González", "Torres"]
COMMUNES = ["Providencia", "Ñuñoa", "Las Condes", "Santiago", "Maipú", "La Florida"]


def _slug(value: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")
    return cleaned or "demo"


def _rut(number: int) -> str:
    body = str(number)
    total = 0
    factor = 2
    for digit in reversed(body):
        total += int(digit) * factor
        factor = 2 if factor == 7 else factor + 1
    result = 11 - (total % 11)
    dv = "0" if result == 11 else "K" if result == 10 else str(result)
    return f"{body}-{dv}"


class Command(BaseCommand):
    help = "Genera un dataset local, poblado y determinista para explorar TuPymeGestiona."

    def add_arguments(self, parser):
        parser.add_argument("--seed", default="local-2026")
        parser.add_argument("--companies", type=int, default=5)
        parser.add_argument("--products", type=int, default=48)
        parser.add_argument("--customers", type=int, default=70)
        parser.add_argument("--orders", type=int, default=36)
        parser.add_argument("--password", default="")
        parser.add_argument("--allow-sqlite", action="store_true")
        parser.add_argument("--force-production", action="store_true")

    def handle(self, *args, **options):
        if connection.vendor != "mysql" and not options["allow_sqlite"]:
            raise CommandError(
                f"La conexión activa es {connection.vendor!r}. El cargador demo normal exige MySQL."
            )
        if not settings.DEBUG and not options["force_production"]:
            raise CommandError("El seed demo está bloqueado con DEBUG=False salvo --force-production.")

        executor = MigrationExecutor(connection)
        pending = executor.migration_plan(executor.loader.graph.leaf_nodes())
        if pending:
            names = ", ".join(f"{m.app_label}.{m.name}" for m, _ in pending)
            raise CommandError(f"Hay migraciones pendientes. Aplica primero: {names}")
        if not Permission.objects.exists():
            raise CommandError("No existen permisos base. Revisa/aplica las migraciones de seeds.")

        companies_count = max(1, min(options["companies"], len(COMPANY_NAMES)))
        products_count = max(4, min(options["products"], 120))
        customers_count = max(5, min(options["customers"], 250))
        orders_count = max(4, min(options["orders"], 120))
        seed = _slug(options["seed"])
        password = options["password"].strip() or "DemoLocal2026!"
        marker_domain = f"demo-{seed}.tupyme.local"

        existing = Company.objects.filter(contact_email__endswith=f"@{marker_domain}").count()
        if existing:
            if existing == companies_count:
                self.stdout.write(self.style.SUCCESS(
                    f"Dataset {seed!r} ya existe con {existing} empresa(s). No se duplicó información."
                ))
                self._print_credentials(seed, password)
                return
            raise CommandError(
                f"Existe un dataset parcial para {seed!r}: {existing}/{companies_count} empresas. "
                "Usa otro --seed o limpia ese dataset manualmente."
            )

        rng = random.Random(seed)
        with transaction.atomic():
            owner = self._user(
                email=f"owner@{marker_domain}",
                password=password,
                first_name="Demo",
                last_name="Propietario",
            )
            client = self._user(
                email=f"cliente@{marker_domain}",
                password=password,
                first_name="Demo",
                last_name="Cliente",
            )

            for index in range(companies_count):
                name, activity = COMPANY_NAMES[index]
                company = create_company_for_user(
                    user=owner,
                    company_data={
                        "name": name,
                        "rut": _rut(76000000 + index * 137),
                        "legal_name": f"{name} SpA",
                        "business_activity": activity,
                        "contact_email": f"empresa{index + 1}@{marker_domain}",
                        "phone": f"+56 9 {7000 + index:04d} {1200 + index:04d}",
                        "address": f"Av. Demo {100 + index * 25}",
                        "commune": COMMUNES[index % len(COMMUNES)],
                        "city": "Santiago",
                        "is_active": True,
                    },
                )
                branches = self._branches(company, index)
                warehouses = self._warehouses(company, branches)
                self._staff(company, branches, seed, index, password)
                categories = self._categories(company)
                brands = self._brands(company)
                variants = self._catalog(
                    company,
                    categories,
                    brands,
                    products_count,
                    index,
                    rng,
                )
                self._suppliers(company, index)
                self._stock(warehouses, variants, rng)
                customers = self._customers(company, customers_count, index, rng)

                portal_customer = customers[0]
                portal_customer.name = "Demo Cliente"
                portal_customer.email = client.email
                portal_customer.save(update_fields=("name", "email", "updated_at"))
                CustomerPortalAccount.objects.create(
                    user=client,
                    company=company,
                    customer=portal_customer,
                    status=CustomerPortalAccount.Status.ACTIVE,
                )

                self._orders_and_sales(
                    company=company,
                    branches=branches,
                    warehouses=warehouses,
                    variants=variants,
                    customers=customers,
                    owner=owner,
                    order_count=orders_count,
                    rng=rng,
                )
                self._low_stock_examples(warehouses, variants)

        self.stdout.write(self.style.SUCCESS(
            f"Dataset {seed!r} creado: {companies_count} empresas, "
            f"{companies_count * products_count} productos, "
            f"{companies_count * customers_count} clientes y hasta "
            f"{companies_count * orders_count} pedidos."
        ))
        self._print_credentials(seed, password)

    def _user(self, *, email, password, first_name, last_name):
        user = User.objects.create_user(
            username=email,
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
        )
        return user

    def _branches(self, company, company_index):
        names = ["Casa Matriz", "Sucursal Centro", "Sucursal Oriente"]
        branches = []
        for idx, name in enumerate(names, start=1):
            branches.append(
                Branch.objects.create(
                    company=company,
                    code=f"S{idx}",
                    name=name,
                    address=f"Calle Demo {company_index + 1}{idx}0",
                    commune=COMMUNES[(company_index + idx) % len(COMMUNES)],
                    city="Santiago",
                    phone=f"+56 2 24{company_index:02d}{idx:02d}00",
                    is_active=True,
                )
            )
        return branches

    def _warehouses(self, company, branches):
        warehouses = [
            Warehouse.objects.create(
                company=company,
                branch=branch,
                code=f"BOD-{index}",
                name=f"Bodega {branch.name}",
            )
            for index, branch in enumerate(branches, start=1)
        ]
        warehouses.append(
            Warehouse.objects.create(
                company=company,
                branch=None,
                code="BOD-GLOBAL",
                name="Bodega Ecommerce",
            )
        )
        return warehouses

    def _staff(self, company, branches, seed, company_index, password):
        admin_role = company.roles.get(name_normalized="administrador")
        sales_role = CompanyRole.objects.create(
            company=company,
            name="Ventas",
            status=CompanyRole.Status.ACTIVE,
        )
        stock_role = CompanyRole.objects.create(
            company=company,
            name="Bodega",
            status=CompanyRole.Status.ACTIVE,
        )
        sales_permissions = Permission.objects.filter(
            code__in=["orders.manage", "sales.manage", "customers.manage"]
        )
        stock_permissions = Permission.objects.filter(
            code__in=[
                "inventory.stocks.manage",
                "inventory.movements.manage",
                "inventory.transfers.manage",
                "organizations.warehouses.manage",
                "catalog.products.manage",
                "catalog.categories.manage",
                "catalog.brands.manage",
                "catalog.suppliers.manage",
            ]
        )
        CompanyRolePermission.objects.bulk_create(
            [CompanyRolePermission(role=sales_role, permission=p) for p in sales_permissions]
            + [CompanyRolePermission(role=stock_role, permission=p) for p in stock_permissions],
            ignore_conflicts=True,
        )

        roles = [sales_role, stock_role, admin_role]
        for idx in range(3):
            email = f"staff{company_index + 1}-{idx + 1}@demo-{seed}.tupyme.local"
            user = self._user(
                email=email,
                password=password,
                first_name=FIRST_NAMES[(company_index + idx) % len(FIRST_NAMES)],
                last_name=LAST_NAMES[(company_index * 2 + idx) % len(LAST_NAMES)],
            )
            membership = CompanyMembership.objects.create(
                user=user,
                company=company,
                status=CompanyMembership.Status.ACTIVE,
            )
            branch = branches[idx % len(branches)]
            MembershipBranch.objects.create(membership=membership, branch=branch)
            # Ventas/Bodega incluyen permisos COMPANY_ONLY (por ejemplo customers/catalog),
            # por lo que el rol se asigna a nivel empresa. MembershipBranch conserva
            # una sucursal preferente para contexto/navegación sin violar RBAC.
            RoleAssignment.objects.create(
                membership=membership,
                role=roles[idx],
                branch=None,
            )

    def _categories(self, company):
        return [
            Category.objects.create(
                company=company,
                name=name,
                status=Category.Status.ACTIVE,
            )
            for name in CATEGORY_NAMES
        ]

    def _brands(self, company):
        return [Brand.objects.create(company=company, name=name) for name in BRAND_NAMES]

    def _catalog(self, company, categories, brands, count, company_index, rng):
        variants = []
        for idx in range(count):
            product = Product.objects.create(
                company=company,
                category=categories[idx % len(categories)],
                brand=brands[idx % len(brands)],
                name=f"{PRODUCT_BASES[idx % len(PRODUCT_BASES)]} {idx + 1:02d}",
                description=(
                    "Producto demo con información comercial completa para probar catálogo, "
                    "inventario, pedidos, ventas y reportes dentro de TuPymeGestiona."
                ),
                image_url=f"https://picsum.photos/seed/tupyme-{company_index}-{idx}/640/420",
                status=Product.Status.ACTIVE,
            )
            base = Decimal(str(3990 + (idx % 12) * 1750 + company_index * 220)).quantize(Decimal("0.01"))
            for variant_index, suffix in enumerate(("STD", "PLUS"), start=1):
                variants.append(
                    ProductVariant.objects.create(
                        product=product,
                        sku=f"D{company_index + 1:02d}-{idx + 1:03d}-{suffix}",
                        gtin=f"780{company_index + 1:02d}{idx + 1:05d}{variant_index}",
                        base_price=base + Decimal((variant_index - 1) * 2500),
                        status=ProductVariant.Status.ACTIVE,
                    )
                )
        rng.shuffle(variants)
        return variants

    def _suppliers(self, company, company_index):
        for idx in range(10):
            Supplier.objects.create(
                company=company,
                name=f"Proveedor {company_index + 1}-{idx + 1:02d}",
                contact_name=f"Contacto {FIRST_NAMES[idx % len(FIRST_NAMES)]}",
                email=f"proveedor{company_index + 1}-{idx + 1}@example.test",
                phone=f"+56 9 81{company_index:02d}{idx:04d}",
                status=Supplier.Status.ACTIVE,
            )

    def _stock(self, warehouses, variants, rng):
        rows = []
        for warehouse in warehouses:
            for variant in variants:
                rows.append(
                    InventoryStock(
                        warehouse=warehouse,
                        variant=variant,
                        quantity=Decimal(rng.randint(20, 140)),
                    )
                )
        InventoryStock.objects.bulk_create(rows)

    def _customers(self, company, count, company_index, rng):
        customers = []
        for idx in range(count):
            first = FIRST_NAMES[(idx + company_index) % len(FIRST_NAMES)]
            last = LAST_NAMES[(idx * 3 + company_index) % len(LAST_NAMES)]
            customers.append(
                Customer.objects.create(
                    company=company,
                    code=f"CLI-{idx + 1:04d}",
                    name=f"{first} {last}",
                    tax_id="",
                    email=f"cliente{company_index + 1}-{idx + 1}@example.test",
                    phone=f"+56 9 {rng.randint(5000, 9999)} {rng.randint(1000, 9999)}",
                    address=f"Calle {rng.randint(100, 999)} #{rng.randint(10, 999)}",
                    commune=COMMUNES[idx % len(COMMUNES)],
                    city="Santiago",
                    status=Customer.Status.ACTIVE,
                )
            )
        return customers

    def _orders_and_sales(
        self,
        *,
        company,
        branches,
        warehouses,
        variants,
        customers,
        owner,
        order_count,
        rng,
    ):
        usable_variants = variants[4:] if len(variants) > 8 else variants
        for idx in range(order_count):
            branch = branches[idx % len(branches)]
            warehouse = next(item for item in warehouses if item.branch_id == branch.id)
            # Los primeros seis pedidos de cada PYME pertenecen al cliente demo,
            # cubriendo borrador, confirmado, preparado, entregado/pagado,
            # entregado/parcial y cancelado. Así /portal/account queda poblado
            # desde la primera ejecución del seed.
            customer = customers[0] if idx < min(6, order_count) else customers[idx % len(customers)]
            selected = rng.sample(usable_variants, k=min(2, len(usable_variants)))
            items = [
                {
                    "variant": variant,
                    "quantity": Decimal("1.000") if position == 0 else Decimal("2.000"),
                    "unit_price": variant.base_price,
                }
                for position, variant in enumerate(selected)
            ]
            order = create_draft_order(
                company=company,
                branch=branch,
                warehouse=warehouse,
                customer=customer,
                notes="Pedido demo generado automáticamente.",
                items=items,
                created_by=owner,
            )
            order.delivery_address = customer.address
            order.delivery_commune = customer.commune
            order.delivery_city = customer.city
            order.save(update_fields=("delivery_address", "delivery_commune", "delivery_city", "updated_at"))

            mode = idx % 6
            if mode in {1, 2, 3, 4, 5}:
                order = confirm_order(order=order, performed_by=owner)
            if mode in {2, 3, 4}:
                order = prepare_order(order=order, performed_by=owner)
            if mode in {3, 4}:
                order = deliver_order(order=order, performed_by=owner)
            elif mode == 5:
                order = cancel_order(order=order, performed_by=owner)

            if mode in {3, 4}:
                sale, _ = create_sale(
                    company=company,
                    order=order,
                    idempotency_key=f"demo-sale-{company.id}-{order.id}",
                    created_by=owner,
                )
                if mode == 3:
                    record_payment(
                        sale=sale,
                        amount=sale.total_amount,
                        reference=f"DEMO-PAGO-{sale.number}",
                        idempotency_key=f"demo-payment-{sale.id}",
                        performed_by=owner,
                    )
                elif sale.total_amount > Decimal("1.00"):
                    partial = (sale.total_amount / Decimal("2")).quantize(Decimal("0.01"))
                    record_payment(
                        sale=sale,
                        amount=partial,
                        reference=f"DEMO-ABONO-{sale.number}",
                        idempotency_key=f"demo-partial-{sale.id}",
                        performed_by=owner,
                    )

            days_ago = 0 if idx >= order_count - 4 else rng.randint(1, 45)
            occurred_at = timezone.now() - timedelta(days=days_ago, hours=rng.randint(0, 18))
            Order.objects.filter(pk=order.pk).update(created_at=occurred_at, updated_at=occurred_at)
            if hasattr(order, "sale"):
                Sale.objects.filter(pk=order.sale.pk).update(created_at=occurred_at, updated_at=occurred_at)
                Payment.objects.filter(sale=order.sale).update(created_at=occurred_at)
                SaleEvent.objects.filter(sale=order.sale).update(created_at=occurred_at)

    def _low_stock_examples(self, warehouses, variants):
        if len(variants) < 2:
            return
        InventoryStock.objects.filter(warehouse=warehouses[0], variant=variants[0]).update(quantity=0)
        InventoryStock.objects.filter(warehouse=warehouses[0], variant=variants[1]).update(quantity=Decimal("3.000"))

    def _print_credentials(self, seed, password):
        marker_domain = f"demo-{seed}.tupyme.local"
        self.stdout.write("\nCredenciales DEMO locales:")
        self.stdout.write(f"  Propietario: owner@{marker_domain}")
        self.stdout.write(f"  Cliente:     cliente@{marker_domain}")
        self.stdout.write(f"  Contraseña:  {password}")
        self.stdout.write("Estas credenciales son únicamente para desarrollo local.")
