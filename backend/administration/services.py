from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction

from accounts.access import has_company_admin_access, has_customer_access
from orders.models import Order
from organizations.models import (
    Company,
    CompanyMembership,
    CompanyRole,
    CompanyRolePermission,
    MembershipBranch,
    Permission,
    RoleAssignment,
)

from administration.models import (
    AdministrationEvent,
    CompanySettings,
    OrderStatusConfiguration,
    PaymentMethod,
)


ADMIN_PERMISSION_CODE = "administration.manage"
User = get_user_model()


class SelfServiceAccessError(Exception):
    pass


class SelfServiceConflictError(Exception):
    pass


def user_can_manage_company(*, user, company):
    if getattr(user, "is_superuser", False):
        return True
    return has_company_admin_access(user, company.id if company is not None else None)


def user_can_create_company(*, user):
    return bool(
        getattr(user, "is_superuser", False)
        or has_company_admin_access(user)
    )


def user_can_self_service_company(*, user):
    """Return whether ``user`` may create their primary self-service company.

    Self-service is available to active portal customers.  The primary marker
    is independent from administrator-assigned memberships, so a customer who
    manages another company can still create their own primary company.
    """
    if not has_customer_access(user):
        return False
    return not CompanyMembership.objects.filter(primary_for_user=user).exists()


def get_managed_company(*, user, company_id):
    company = Company.objects.filter(pk=company_id, is_active=True).first()
    if company is None:
        return None
    if not user_can_manage_company(user=user, company=company):
        return None
    return company


@transaction.atomic
def log_admin_event(*, company, actor, event_type, resource_type, resource_id="", metadata=None):
    from maintainers.models import MaintainerAuditEvent

    event = AdministrationEvent.objects.create(
        company=company,
        actor=actor,
        event_type=event_type,
        resource_type=resource_type,
        resource_id=str(resource_id or ""),
        metadata=metadata or {},
    )

    MaintainerAuditEvent.objects.create(
        actor=actor,
        company_id_snapshot=company.pk,
        event_type=event_type,
        resource_type=resource_type,
        resource_id=str(resource_id or ""),
        metadata={**(metadata or {}), "company_label": company.name, "administration_event_id": event.pk},
    )
    return event


def ensure_company_configuration(company):
    CompanySettings.objects.get_or_create(company=company)

    defaults = (
        ("CASH", "Efectivo", PaymentMethod.Kind.CASH, 10),
        ("TRANSFER", "Transferencia", PaymentMethod.Kind.TRANSFER, 20),
        ("ONLINE", "Pago en linea", PaymentMethod.Kind.ONLINE, 30),
    )
    for code, name, kind, sort_order in defaults:
        PaymentMethod.objects.get_or_create(
            company=company,
            code=code,
            defaults={
                "name": name,
                "kind": kind,
                "sort_order": sort_order,
                "is_active": True,
            },
        )

    for index, (code, label) in enumerate(Order.Status.choices, start=1):
        OrderStatusConfiguration.objects.get_or_create(
            company=company,
            code=code,
            defaults={
                "display_name": label,
                "sort_order": index * 10,
                "is_active": True,
                "is_system": True,
            },
        )


def role_has_company_only_permissions(role):
    return role.permission_links.filter(
        permission__scope_behavior=Permission.ScopeBehavior.COMPANY_ONLY,
    ).exists()


def role_has_branch_scoped_permissions(role):
    return role.permission_links.filter(
        permission__scope_behavior=Permission.ScopeBehavior.BRANCH_SCOPED,
    ).exists()


def replace_membership_access(*, membership, branch_ids, role_ids):
    branches = list(
        membership.company.branches.filter(id__in=branch_ids).order_by("id")
    )
    if len(branches) != len(set(branch_ids)):
        raise ValueError("Una o mas sucursales no pertenecen a la empresa.")

    roles = list(
        membership.company.roles.filter(id__in=role_ids).order_by("id")
    )
    if len(roles) != len(set(role_ids)):
        raise ValueError("Uno o mas roles no pertenecen a la empresa.")

    role_scopes = []
    for role in roles:
        has_company_scope = role_has_company_only_permissions(role)
        has_branch_scope = role_has_branch_scoped_permissions(role)
        if has_branch_scope and not branches:
            raise ValueError(
                "Los roles con permisos por sucursal requieren al menos una sucursal."
            )
        # A role may legitimately combine company-only and branch-scoped
        # permissions.  Demo roles such as Ventas, Bodega and Administrador
        # use this shape.  Assigning the mixed role at company level keeps
        # company permissions valid while branch-scoped permissions inherit
        # the membership's selected branches (see get_branch_scope()).
        role_scopes.append((role, has_company_scope, has_branch_scope))

    MembershipBranch.objects.filter(membership=membership).delete()
    MembershipBranch.objects.bulk_create(
        [MembershipBranch(membership=membership, branch=branch) for branch in branches]
    )

    RoleAssignment.objects.filter(membership=membership).delete()
    for role, has_company_scope, has_branch_scope in role_scopes:
        if has_company_scope or not has_branch_scope:
            RoleAssignment.objects.create(
                membership=membership,
                role=role,
                branch=None,
            )
            continue
        for branch in branches:
            RoleAssignment.objects.create(
                membership=membership,
                role=role,
                branch=branch,
            )


def membership_has_admin_access(membership):
    return membership.status == CompanyMembership.Status.ACTIVE and membership.role_assignments.filter(
        role__status=CompanyRole.Status.ACTIVE,
        role__permission_links__permission__code=ADMIN_PERMISSION_CODE,
    ).exists()


@transaction.atomic
def create_company_for_user(*, user, company_data, primary_for_user=None):
    company = Company.objects.create(**company_data)
    membership = CompanyMembership.objects.create(
        user=user,
        company=company,
        status=CompanyMembership.Status.ACTIVE,
        primary_for_user=primary_for_user,
    )
    role = CompanyRole.objects.create(
        company=company,
        name="Administrador",
        status=CompanyRole.Status.ACTIVE,
    )
    permission_links = [
        CompanyRolePermission(role=role, permission=permission)
        for permission in Permission.objects.all()
    ]
    CompanyRolePermission.objects.bulk_create(permission_links, ignore_conflicts=True)
    RoleAssignment.objects.create(
        membership=membership,
        role=role,
        branch=None,
    )
    ensure_company_configuration(company)
    log_admin_event(
        company=company,
        actor=user,
        event_type="COMPANY_CREATED",
        resource_type="company",
        resource_id=company.id,
        metadata={"name": company.name},
    )
    return company


@transaction.atomic
def create_self_service_company_for_user(*, user, company_data):
    """Create the user's primary company, branch and admin access atomically."""
    locked_user = User.objects.select_for_update().get(pk=user.pk)
    if not has_customer_access(locked_user):
        raise SelfServiceAccessError(
            "Debes tener una cuenta de cliente activa para crear una PYME."
        )
    if CompanyMembership.objects.filter(primary_for_user=locked_user).exists():
        raise SelfServiceConflictError(
            "Ya tienes una PYME principal asociada a esta cuenta."
        )

    try:
        company = create_company_for_user(
            user=locked_user,
            company_data=company_data,
            primary_for_user=locked_user,
        )
    except IntegrityError as exc:
        if CompanyMembership.objects.filter(primary_for_user=locked_user).exists():
            raise SelfServiceConflictError(
                "Ya tienes una PYME principal asociada a esta cuenta."
            ) from exc
        raise
    from organizations.models import Branch

    Branch.objects.create(
        company=company,
        code="CASA",
        name="Casa Matriz",
        address=company.address,
        commune=company.commune,
        city=company.city,
        phone=company.phone,
        is_active=True,
    )
    return company
