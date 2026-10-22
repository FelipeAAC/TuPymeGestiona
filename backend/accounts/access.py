"""Resolve the capabilities and destinations available to an authenticated user."""

from organizations.models import CompanyMembership, CompanyRole, RoleAssignment
from portal.models import CustomerPortalAccount


CUSTOMER = "CUSTOMER"
COMPANY_ADMIN = "COMPANY_ADMIN"
PLATFORM_ADMIN = "PLATFORM_ADMIN"
ADMIN_PERMISSION = "administration.manage"


def is_platform_admin(user) -> bool:
    return bool(getattr(user, "is_authenticated", False) and getattr(user, "platform_admin", False))


def has_customer_access(user) -> bool:
    return bool(
        getattr(user, "is_authenticated", False)
        and CustomerPortalAccount.objects.filter(
            user=user,
            status=CustomerPortalAccount.Status.ACTIVE,
        ).exists()
    )


def _company_admin_assignments(user, company_id=None):
    filters = {
        "membership__user": user,
        "membership__status": CompanyMembership.Status.ACTIVE,
        "membership__company__is_active": True,
        "role__status": CompanyRole.Status.ACTIVE,
        "role__permission_links__permission__code": ADMIN_PERMISSION,
    }
    if company_id is not None:
        filters["membership__company_id"] = company_id
    return RoleAssignment.objects.filter(**filters)


def has_company_admin_access(user, company_id=None) -> bool:
    if not getattr(user, "is_authenticated", False):
        return False
    return _company_admin_assignments(user, company_id).exists()


def get_access_context(user) -> dict:
    """Return the complete, cumulative access context for ``user``.

    Company lists contain only tenant records the user can access and expose no
    credentials or unrelated company data.
    """
    if not getattr(user, "is_authenticated", False):
        return {
            "access_modes": [],
            "default_app": None,
            "managed_companies": [],
            "portal_companies": [],
        }

    # Build the company projection directly because the assignment queryset
    # exposes membership fields rather than a Company queryset.
    managed_companies = [
        {"id": company_id, "name": name}
        for company_id, name in _company_admin_assignments(user)
        .values_list("membership__company_id", "membership__company__name")
        .distinct()
        .order_by("membership__company_id")
    ]
    portal_companies = [
        {"id": company_id, "name": name}
        for company_id, name in CustomerPortalAccount.objects.filter(
            user=user,
            status=CustomerPortalAccount.Status.ACTIVE,
        )
        .values_list("company_id", "company__name")
        .distinct()
        .order_by("company_id")
    ]

    modes = []
    if portal_companies:
        modes.append(CUSTOMER)
    if managed_companies:
        modes.append(COMPANY_ADMIN)
    if is_platform_admin(user):
        modes.append(PLATFORM_ADMIN)

    if PLATFORM_ADMIN in modes:
        default_app = "maintainers"
    elif len(modes) > 1:
        default_app = "choose"
    elif COMPANY_ADMIN in modes:
        default_app = "app"
    elif CUSTOMER in modes:
        default_app = "portal"
    else:
        default_app = None

    return {
        "access_modes": modes,
        "default_app": default_app,
        "managed_companies": managed_companies,
        "portal_companies": portal_companies,
    }
