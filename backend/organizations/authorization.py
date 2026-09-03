from django.db.models import Q

from organizations.models import (
    CompanyMembership,
    CompanyRole,
    Permission,
    RoleAssignment,
)


def has_permission(
    *,
    user,
    company,
    permission_code,
    branch=None,
):
    if not getattr(user, "is_authenticated", False):
        return False

    if getattr(user, "is_superuser", False):
        return True

    if not company or not company.pk:
        return False

    if branch is not None:
        if not branch.pk or branch.company_id != company.pk:
            return False

    permission = Permission.objects.filter(
        code=permission_code,
    ).first()

    if permission is None:
        return False

    assignments = RoleAssignment.objects.filter(
        membership__user=user,
        membership__company=company,
        membership__status=CompanyMembership.Status.ACTIVE,
        role__company=company,
        role__status=CompanyRole.Status.ACTIVE,
        role__permission_links__permission=permission,
    )

    if permission.scope_behavior == Permission.ScopeBehavior.COMPANY_ONLY:
        return assignments.filter(
            branch__isnull=True,
        ).exists()

    if permission.scope_behavior == Permission.ScopeBehavior.TENANT_GLOBAL:
        return assignments.exists()

    if permission.scope_behavior == Permission.ScopeBehavior.BRANCH_SCOPED:
        if branch is None:
            return assignments.filter(
                branch__isnull=True,
            ).exists()

        return assignments.filter(
            Q(branch__isnull=True) | Q(branch=branch),
        ).exists()

    return False
