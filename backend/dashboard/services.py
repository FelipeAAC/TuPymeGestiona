from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from django.db.models import Count, QuerySet, Sum
from django.utils import timezone

from customers.models import Customer
from inventory.models import InventoryMovement, InventoryStock
from orders.models import Order
from organizations.authorization import has_permission
from organizations.models import Company, CompanyMembership, RoleAssignment
from sales.models import Sale, SaleEvent


ADMIN_PERMISSION_CODE = "administration.manage"
SALES_PERMISSION_CODE = "sales.manage"
ORDERS_PERMISSION_CODE = "orders.manage"
INVENTORY_PERMISSION_CODE = "inventory.stocks.manage"
CUSTOMERS_PERMISSION_CODE = "customers.manage"
CRITICAL_STOCK_THRESHOLD = Decimal("5.000")


class DashboardPermissionError(Exception):
    pass


@dataclass(frozen=True)
class BranchScope:
    allowed: bool
    all_branches: bool
    branch_ids: frozenset[int]


@dataclass(frozen=True)
class DashboardContext:
    membership: CompanyMembership
    company: Company
    is_admin: bool
    sales_scope: BranchScope
    orders_scope: BranchScope
    inventory_scope: BranchScope
    can_customers: bool


def _active_assignments(*, user, company, permission_code):
    return RoleAssignment.objects.filter(
        membership__user=user,
        membership__company=company,
        membership__status=CompanyMembership.Status.ACTIVE,
        role__company=company,
        role__permission_links__permission__code=permission_code,
        role__status="ACTIVE",
    ).distinct()


def _full_scope() -> BranchScope:
    return BranchScope(True, True, frozenset())


def _branch_scope(*, user, company, permission_code, is_admin) -> BranchScope:
    if getattr(user, "is_superuser", False) or is_admin:
        return _full_scope()

    assignments = _active_assignments(
        user=user,
        company=company,
        permission_code=permission_code,
    )
    if not assignments.exists():
        return BranchScope(False, False, frozenset())
    if assignments.filter(branch__isnull=True).exists():
        return _full_scope()

    return BranchScope(
        True,
        False,
        frozenset(assignments.values_list("branch_id", flat=True)),
    )


def resolve_dashboard_context(*, user, company_id: int) -> DashboardContext:
    membership = (
        CompanyMembership.objects.filter(
            user=user,
            company_id=company_id,
            status=CompanyMembership.Status.ACTIVE,
        )
        .select_related("company")
        .first()
    )
    if membership is None:
        raise DashboardPermissionError("No tienes acceso a esta empresa.")

    company = membership.company
    is_admin = getattr(user, "is_superuser", False) or _active_assignments(
        user=user,
        company=company,
        permission_code=ADMIN_PERMISSION_CODE,
    ).filter(branch__isnull=True).exists()

    return DashboardContext(
        membership=membership,
        company=company,
        is_admin=is_admin,
        sales_scope=_branch_scope(
            user=user,
            company=company,
            permission_code=SALES_PERMISSION_CODE,
            is_admin=is_admin,
        ),
        orders_scope=_branch_scope(
            user=user,
            company=company,
            permission_code=ORDERS_PERMISSION_CODE,
            is_admin=is_admin,
        ),
        inventory_scope=_branch_scope(
            user=user,
            company=company,
            permission_code=INVENTORY_PERMISSION_CODE,
            is_admin=is_admin,
        ),
        can_customers=(
            is_admin
            or has_permission(
                user=user,
                company=company,
                permission_code=CUSTOMERS_PERMISSION_CODE,
            )
        ),
    )


def _scope_queryset(queryset: QuerySet, scope: BranchScope, *, field: str) -> QuerySet:
    if not scope.allowed:
        return queryset.none()
    if scope.all_branches:
        return queryset
    return queryset.filter(**{f"{field}__in": scope.branch_ids})


def _sales_queryset(context: DashboardContext) -> QuerySet[Sale]:
    return _scope_queryset(
        Sale.objects.filter(company=context.company),
        context.sales_scope,
        field="branch_id",
    )


def _orders_queryset(context: DashboardContext) -> QuerySet[Order]:
    return _scope_queryset(
        Order.objects.filter(company=context.company),
        context.orders_scope,
        field="branch_id",
    )


def _stocks_queryset(context: DashboardContext) -> QuerySet[InventoryStock]:
    return _scope_queryset(
        InventoryStock.objects.filter(warehouse__company=context.company),
        context.inventory_scope,
        field="warehouse__branch_id",
    )


def _movements_queryset(context: DashboardContext) -> QuerySet[InventoryMovement]:
    return _scope_queryset(
        InventoryMovement.objects.filter(warehouse__company=context.company),
        context.inventory_scope,
        field="warehouse__branch_id",
    )


def _money(value: Decimal | None) -> str:
    return str((value or Decimal("0.00")).quantize(Decimal("0.01")))


def _metrics(context: DashboardContext) -> tuple[dict, dict]:
    sales = _sales_queryset(context)
    active_sales = sales.exclude(status=Sale.Status.CANCELLED)
    if context.sales_scope.allowed:
        today_sales = active_sales.filter(created_at__date=timezone.localdate())
        today = today_sales.aggregate(
            count=Count("id"),
            amount=Sum("total_amount"),
        )
        outstanding_sales = active_sales.filter(
            status__in=[Sale.Status.PENDING, Sale.Status.PARTIAL]
        ).count()
        sales_today_count = today["count"]
        sales_today_amount = _money(today["amount"])
    else:
        outstanding_sales = None
        sales_today_count = None
        sales_today_amount = None

    orders = _orders_queryset(context)
    pending_orders = (
        orders.filter(
            status__in=[
                Order.Status.DRAFT,
                Order.Status.CONFIRMED,
                Order.Status.PREPARED,
            ]
        ).count()
        if context.orders_scope.allowed
        else None
    )

    stocks = _stocks_queryset(context)
    if context.inventory_scope.allowed:
        critical_stock = stocks.filter(
            quantity__gt=0,
            quantity__lte=CRITICAL_STOCK_THRESHOLD,
        ).count()
        out_of_stock = stocks.filter(quantity=0).count()
        low_stock = critical_stock + out_of_stock
    else:
        critical_stock = None
        out_of_stock = None
        low_stock = None

    active_customers = (
        Customer.objects.filter(
            company=context.company,
            status=Customer.Status.ACTIVE,
        ).count()
        if context.can_customers
        else None
    )

    return (
        {
            "sales_today_amount": sales_today_amount,
            "sales_today_count": sales_today_count,
            "pending_orders": pending_orders,
            "low_stock": low_stock,
            "critical_stock": critical_stock,
            "out_of_stock": out_of_stock,
            "active_customers": active_customers,
        },
        {
            "outstanding_sales": outstanding_sales,
        },
    )


def _alerts(metrics: dict, extras: dict) -> list[dict]:
    alerts = []

    if metrics["out_of_stock"]:
        alerts.append(
            {
                "code": "inventory-out",
                "severity": "danger",
                "title": "Productos sin stock",
                "detail": f"{metrics['out_of_stock']} existencia(s) requieren reposición.",
                "count": metrics["out_of_stock"],
                "route": "/app/inventory",
            }
        )
    if metrics["critical_stock"]:
        alerts.append(
            {
                "code": "inventory-critical",
                "severity": "warning",
                "title": "Stock crítico",
                "detail": (
                    f"{metrics['critical_stock']} existencia(s) están entre 0 y "
                    f"{CRITICAL_STOCK_THRESHOLD} unidades."
                ),
                "count": metrics["critical_stock"],
                "route": "/app/inventory",
            }
        )
    if metrics["pending_orders"]:
        alerts.append(
            {
                "code": "orders-pending",
                "severity": "info",
                "title": "Pedidos pendientes",
                "detail": f"{metrics['pending_orders']} pedido(s) siguen en proceso.",
                "count": metrics["pending_orders"],
                "route": "/app/orders",
            }
        )
    if extras["outstanding_sales"]:
        alerts.append(
            {
                "code": "sales-outstanding",
                "severity": "warning",
                "title": "Ventas con saldo pendiente",
                "detail": f"{extras['outstanding_sales']} venta(s) aún no están pagadas por completo.",
                "count": extras["outstanding_sales"],
                "route": "/app/sales",
            }
        )

    return alerts


def _activity(context: DashboardContext) -> list[dict]:
    items = []

    if context.sales_scope.allowed:
        sale_events = SaleEvent.objects.filter(sale__company=context.company)
        sale_events = _scope_queryset(
            sale_events,
            context.sales_scope,
            field="sale__branch_id",
        ).select_related("sale", "sale__branch", "performed_by")
        for event in sale_events.order_by("-created_at", "-id")[:6]:
            label = {
                SaleEvent.EventType.CREATED: "Venta creada",
                SaleEvent.EventType.PAYMENT_RECORDED: "Pago registrado",
                SaleEvent.EventType.CANCELLED: "Venta anulada",
            }.get(event.event_type, event.get_event_type_display())
            detail = f"Venta #{event.sale.number} · {event.sale.branch.name}"
            if event.amount is not None:
                detail += f" · {_money(event.amount)}"
            items.append(
                {
                    "kind": "sale",
                    "title": label,
                    "detail": detail,
                    "occurred_at": event.created_at,
                    "route": "/app/sales",
                }
            )

    if context.inventory_scope.allowed:
        movements = _movements_queryset(context).select_related(
            "warehouse",
            "variant__product",
            "created_by",
        )
        for movement in movements.order_by("-created_at", "-id")[:6]:
            items.append(
                {
                    "kind": "inventory",
                    "title": f"Inventario · {movement.get_movement_type_display()}",
                    "detail": (
                        f"{movement.variant.product.name} · {movement.warehouse.name} · "
                        f"{movement.quantity_delta}"
                    ),
                    "occurred_at": movement.created_at,
                    "route": "/app/inventory",
                }
            )

    if context.orders_scope.allowed:
        orders = _orders_queryset(context).select_related("branch", "customer")
        for order in orders.order_by("-created_at", "-id")[:6]:
            items.append(
                {
                    "kind": "order",
                    "title": f"Pedido #{order.number}",
                    "detail": (
                        f"{order.customer.name} · {order.branch.name} · "
                        f"{order.get_status_display()}"
                    ),
                    "occurred_at": order.created_at,
                    "route": "/app/orders",
                }
            )

    items.sort(key=lambda item: item["occurred_at"], reverse=True)
    for item in items:
        item["occurred_at"] = timezone.localtime(item["occurred_at"]).isoformat()
    return items[:8]


def _modules(context: DashboardContext) -> list[dict]:
    modules = [
        ("orders", "Pedidos", context.orders_scope.allowed, "/app/orders"),
        ("sales", "Ventas", context.sales_scope.allowed, "/app/sales"),
        ("inventory", "Inventario", context.inventory_scope.allowed, "/app/inventory"),
        ("customers", "Clientes", context.can_customers, "/app/customers"),
        (
            "reports",
            "Reportes",
            context.is_admin or context.inventory_scope.allowed,
            "/app/reports",
        ),
        ("administration", "Administración", context.is_admin, "/app/administration"),
    ]
    return [
        {
            "code": code,
            "label": label,
            "available": available,
            "status": "OPERATIVE" if available else "RESTRICTED",
            "route": route,
        }
        for code, label, available, route in modules
    ]


def dashboard_overview(*, user, company_id: int) -> dict:
    context = resolve_dashboard_context(user=user, company_id=company_id)
    metrics, extras = _metrics(context)
    return {
        "company": {
            "id": context.company.id,
            "name": context.company.name,
        },
        "generated_at": timezone.now().isoformat(),
        "permissions": {
            "sales": context.sales_scope.allowed,
            "orders": context.orders_scope.allowed,
            "inventory": context.inventory_scope.allowed,
            "customers": context.can_customers,
            "reports": context.is_admin or context.inventory_scope.allowed,
            "administration": context.is_admin,
        },
        "metrics": metrics,
        "alerts": _alerts(metrics, extras),
        "activity": _activity(context),
        "modules": _modules(context),
    }
