from dataclasses import dataclass

from organizations.models import (
    CompanyMembership,
    CompanyRole,
    MembershipBranch,
    Permission,
    RoleAssignment,
)


ADMIN_PERMISSION_CODE = "administration.manage"


@dataclass(frozen=True)
class BranchPermissionScope:
    allowed: bool
    all_branches: bool
    branch_ids: frozenset[int]


def get_branch_scope(*, user, company, permission_code):
    """Resolve the branch scope for a branch-scoped permission.

    A null assignment is legacy data: it inherits only the branches attached
    to the user's active company membership. Company-wide administration is
    the explicit exception that keeps global branch access.
    """
    if not getattr(user, "is_authenticated", False):
        return BranchPermissionScope(False, False, frozenset())

    if not company or not company.pk:
        return BranchPermissionScope(False, False, frozenset())

    if getattr(user, "is_superuser", False):
        return BranchPermissionScope(True, True, frozenset())

    permission = Permission.objects.filter(code=permission_code).first()
    if permission is None:
        return BranchPermissionScope(False, False, frozenset())

    assignments = RoleAssignment.objects.filter(
        membership__user=user,
        membership__company=company,
        membership__status=CompanyMembership.Status.ACTIVE,
        role__company=company,
        role__status=CompanyRole.Status.ACTIVE,
        role__permission_links__permission=permission,
    ).distinct()
    if not assignments.exists():
        return BranchPermissionScope(False, False, frozenset())

    if permission.scope_behavior != Permission.ScopeBehavior.BRANCH_SCOPED:
        return BranchPermissionScope(True, True, frozenset())

    company_admin = RoleAssignment.objects.filter(
        membership__user=user,
        membership__company=company,
        membership__status=CompanyMembership.Status.ACTIVE,
        role__company=company,
        role__status=CompanyRole.Status.ACTIVE,
        role__permission_links__permission__code=ADMIN_PERMISSION_CODE,
        branch__isnull=True,
    ).exists()
    if company_admin:
        return BranchPermissionScope(True, True, frozenset())

    branch_ids = set(
        assignments.filter(branch__isnull=False).values_list(
            "branch_id",
            flat=True,
        )
    )
    inherited_membership_ids = assignments.filter(
        branch__isnull=True,
    ).values_list("membership_id", flat=True)
    branch_ids.update(
        MembershipBranch.objects.filter(
            membership_id__in=inherited_membership_ids,
            branch__company=company,
        ).values_list("branch_id", flat=True)
    )
    return BranchPermissionScope(
        bool(branch_ids),
        False,
        frozenset(branch_ids),
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
            return False

        scope = get_branch_scope(
            user=user,
            company=company,
            permission_code=permission_code,
        )
        return scope.all_branches or branch.pk in scope.branch_ids

    return False
