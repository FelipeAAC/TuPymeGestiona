from django.db.models import Count
from django.contrib.auth import get_user_model

from administration.services import ensure_company_configuration, log_admin_event
from catalog.models import Brand, Category, Product, Supplier
from orders.models import Order
from organizations.models import Branch, Company, Warehouse


User = get_user_model()


def company_queryset():
    """Return all tenants with bounded summary counts for platform users."""
    return Company.objects.annotate(
        branches_count=Count("branches", distinct=True),
        users_count=Count("memberships__user", distinct=True),
        products_count=Count("products", distinct=True),
        orders_count=Count("orders", distinct=True),
    ).order_by("name", "id")


def get_company(company_id):
    return Company.objects.filter(pk=company_id).first()


def build_context():
    companies = company_queryset()
    summary = {
        "total_companies": Company.objects.count(),
        "active_companies": Company.objects.filter(is_active=True).count(),
        "total_branches": Branch.objects.count(),
        "total_users": User.objects.count(),
        "total_products": Product.objects.count(),
        "total_orders": Order.objects.count(),
        "total_categories": Category.objects.count(),
        "total_brands": Brand.objects.count(),
        "total_suppliers": Supplier.objects.count(),
        "total_warehouses": Warehouse.objects.count(),
    }
    # These aliases make the summary pleasant for lightweight clients while
    # keeping the explicit total_* names used by the API contract.
    summary.update(
        companies=summary["total_companies"],
        companies_total=summary["total_companies"],
        companies_active=summary["active_companies"],
        branches=summary["total_branches"],
        users=summary["total_users"],
        products=summary["total_products"],
        orders=summary["total_orders"],
    )
    return companies, summary


def prepare_company(company):
    """Ensure operational defaults exist before returning overview settings."""
    ensure_company_configuration(company)
    return company


def record_event(*, company, actor, event_type, resource_type, resource_id="", metadata=None):
    return log_admin_event(
        company=company,
        actor=actor,
        event_type=event_type,
        resource_type=resource_type,
        resource_id=resource_id,
        metadata=metadata,
    )
