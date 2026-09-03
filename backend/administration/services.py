from django.db import transaction

from orders.models import Order
from organizations.authorization import has_permission
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


def user_can_manage_company(*, user, company):
    if getattr(user, "is_superuser", False):
        return True
    return has_permission(
        user=user,
        company=company,
        permission_code=ADMIN_PERMISSION_CODE,
    )


def user_can_create_company(*, user):
    if not getattr(user, "is_authenticated", False):
        return False
    if getattr(user, "is_superuser", False):
        return True
    return CompanyMembership.objects.filter(
        user=user,
        status=CompanyMembership.Status.ACTIVE,
        role_assignments__role__status=CompanyRole.Status.ACTIVE,
        role_assignments__role__permission_links__permission__code=ADMIN_PERMISSION_CODE,
    ).exists()


def get_managed_company(*, user, company_id):
    company = Company.objects.filter(pk=company_id).first()
    if company is None:
        return None
    if not user_can_manage_company(user=user, company=company):
        return None
    return company


def log_admin_event(*, company, actor, event_type, resource_type, resource_id="", metadata=None):
    return AdministrationEvent.objects.create(
        company=company,
        actor=actor,
        event_type=event_type,
        resource_type=resource_type,
        resource_id=str(resource_id or ""),
        metadata=metadata or {},
    )


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

    MembershipBranch.objects.filter(membership=membership).delete()
    MembershipBranch.objects.bulk_create(
        [MembershipBranch(membership=membership, branch=branch) for branch in branches]
    )

    RoleAssignment.objects.filter(membership=membership).delete()
    for role in roles:
        if role_has_company_only_permissions(role) or not branches:
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
def create_company_for_user(*, user, company_data):
    company = Company.objects.create(**company_data)
    membership = CompanyMembership.objects.create(
        user=user,
        company=company,
        status=CompanyMembership.Status.ACTIVE,
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
