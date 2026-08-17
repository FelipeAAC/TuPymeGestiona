import unicodedata

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class Company(models.Model):
    name = models.CharField(max_length=150)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Branch(models.Model):
    company = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="branches",
    )
    code = models.CharField(max_length=50)
    name = models.CharField(max_length=150)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["company_id", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "code"],
                name="uniq_branch_company_code",
            ),
        ]

    def __str__(self):
        return f"{self.company} - {self.name}"


class Warehouse(models.Model):
    company = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="warehouses",
    )
    branch = models.ForeignKey(
        Branch,
        on_delete=models.PROTECT,
        related_name="warehouses",
        null=True,
        blank=True,
    )
    code = models.CharField(max_length=50)
    name = models.CharField(max_length=150)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["company_id", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "code"],
                name="uniq_warehouse_company_code",
            ),
        ]

    def clean(self):
        super().clean()

        if self.branch_id and self.branch.company_id != self.company_id:
            raise ValidationError(
                {
                    "branch": (
                        "La sucursal debe pertenecer a la misma empresa que la bodega."
                    )
                }
            )

    def __str__(self):
        return f"{self.company} - {self.name}"


class CompanyMembership(models.Model):
    class Status(models.TextChoices):
        INVITED = "INVITED", "Invitado"
        ACTIVE = "ACTIVE", "Activo"
        SUSPENDED = "SUSPENDED", "Suspendido"
        LEFT = "LEFT", "Desvinculado"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="company_memberships",
    )
    company = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="memberships",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.INVITED,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["company_id", "user_id"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "company"],
                name="uniq_membership_user_company",
            ),
        ]

    def __str__(self):
        return f"{self.user} - {self.company}"


class MembershipBranch(models.Model):
    membership = models.ForeignKey(
        CompanyMembership,
        on_delete=models.PROTECT,
        related_name="branch_memberships",
    )
    branch = models.ForeignKey(
        Branch,
        on_delete=models.PROTECT,
        related_name="membership_branches",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["membership_id", "branch_id"]
        constraints = [
            models.UniqueConstraint(
                fields=["membership", "branch"],
                name="uniq_membership_branch",
            ),
        ]

    def clean(self):
        super().clean()

        if (
            self.membership_id
            and self.branch_id
            and self.membership.company_id != self.branch.company_id
        ):
            raise ValidationError(
                {
                    "branch": (
                        "La sucursal debe pertenecer a la misma empresa que la membresia."
                    )
                }
            )

    def __str__(self):
        return f"{self.membership} - {self.branch}"


def normalize_role_name(value):
    normalized = unicodedata.normalize("NFKC", value)
    normalized = " ".join(normalized.split())
    return normalized.casefold()


class Permission(models.Model):
    class ScopeBehavior(models.TextChoices):
        COMPANY_ONLY = "COMPANY_ONLY", "Solo empresa"
        TENANT_GLOBAL = "TENANT_GLOBAL", "Global de empresa"
        BRANCH_SCOPED = "BRANCH_SCOPED", "Por sucursal"

    code = models.CharField(
        max_length=100,
        unique=True,
    )
    scope_behavior = models.CharField(
        max_length=20,
        choices=ScopeBehavior.choices,
    )

    class Meta:
        ordering = ["code"]

    def __str__(self):
        return self.code


class CompanyRole(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Activo"
        INACTIVE = "INACTIVE", "Inactivo"

    company = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="roles",
    )
    name = models.CharField(max_length=150)
    name_normalized = models.CharField(
        max_length=150,
        editable=False,
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
    )

    class Meta:
        ordering = ["company_id", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "name_normalized"],
                name="uniq_role_company_name_normalized",
            ),
        ]

    def clean_fields(self, exclude=None):
        self.name_normalized = normalize_role_name(self.name)
        super().clean_fields(exclude=exclude)

    def clean(self):
        super().clean()

        self.name_normalized = normalize_role_name(self.name)

        if not self.name_normalized:
            raise ValidationError(
                {
                    "name": "El nombre del rol no puede estar vacio.",
                }
            )

    def save(self, *args, **kwargs):
        self.name_normalized = normalize_role_name(self.name)

        if not self.name_normalized:
            raise ValidationError(
                {
                    "name": "El nombre del rol no puede estar vacio.",
                }
            )

        update_fields = kwargs.get("update_fields")
        if update_fields is not None and "name" in update_fields:
            kwargs["update_fields"] = set(update_fields) | {"name_normalized"}

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.company} - {self.name}"


class CompanyRolePermission(models.Model):
    role = models.ForeignKey(
        CompanyRole,
        on_delete=models.PROTECT,
        related_name="permission_links",
    )
    permission = models.ForeignKey(
        Permission,
        on_delete=models.PROTECT,
        related_name="role_links",
    )

    class Meta:
        ordering = ["role_id", "permission_id"]
        constraints = [
            models.UniqueConstraint(
                fields=["role", "permission"],
                name="uniq_company_role_permission",
            ),
        ]

    def clean(self):
        super().clean()

        if (
            self.role_id
            and self.permission_id
            and self.permission.scope_behavior
            == Permission.ScopeBehavior.COMPANY_ONLY
            and self.role.assignments.filter(branch__isnull=False).exists()
        ):
            raise ValidationError(
                {
                    "permission": (
                        "No se puede agregar un permiso COMPANY_ONLY "
                        "a un rol con asignaciones por sucursal."
                    )
                }
            )

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.role} - {self.permission}"


class RoleAssignment(models.Model):
    membership = models.ForeignKey(
        CompanyMembership,
        on_delete=models.PROTECT,
        related_name="role_assignments",
    )
    role = models.ForeignKey(
        CompanyRole,
        on_delete=models.PROTECT,
        related_name="assignments",
    )
    branch = models.ForeignKey(
        Branch,
        on_delete=models.PROTECT,
        related_name="role_assignments",
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ["membership_id", "role_id", "branch_id"]
        constraints = [
            models.UniqueConstraint(
                fields=["membership", "role", "branch"],
                name="uniq_role_assignment_scope",
            ),
        ]

    def clean(self):
        super().clean()

        if (
            self.membership_id
            and self.role_id
            and self.membership.company_id != self.role.company_id
        ):
            raise ValidationError(
                {
                    "role": (
                        "El rol debe pertenecer a la misma empresa que la membresia."
                    )
                }
            )

        if self.branch_id:
            if (
                self.membership_id
                and self.branch.company_id != self.membership.company_id
            ):
                raise ValidationError(
                    {
                        "branch": (
                            "La sucursal debe pertenecer a la misma empresa que la membresia."
                        )
                    }
                )

            if (
                self.role_id
                and self.branch.company_id != self.role.company_id
            ):
                raise ValidationError(
                    {
                        "branch": (
                            "La sucursal debe pertenecer a la misma empresa que el rol."
                        )
                    }
                )

            if self.membership_id and not MembershipBranch.objects.filter(
                membership=self.membership,
                branch=self.branch,
            ).exists():
                raise ValidationError(
                    {
                        "branch": (
                            "La membresia debe estar adscrita a la sucursal antes de asignar un rol en ella."
                        )
                    }
                )

            if self.role_id and CompanyRolePermission.objects.filter(
                role=self.role,
                permission__scope_behavior=Permission.ScopeBehavior.COMPANY_ONLY,
            ).exists():
                raise ValidationError(
                    {
                        "branch": (
                            "Un rol con permisos COMPANY_ONLY no puede asignarse a una sucursal."
                        )
                    }
                )

        if self.membership_id and self.role_id:
            assignments = RoleAssignment.objects.filter(
                membership=self.membership,
                role=self.role,
            )

            if self.pk:
                assignments = assignments.exclude(pk=self.pk)

            if self.branch_id:
                if assignments.filter(branch__isnull=True).exists():
                    raise ValidationError(
                        {
                            "branch": (
                                "No se pueden mezclar asignaciones de empresa y de sucursal para la misma membresia y rol."
                            )
                        }
                    )
            elif assignments.exists():
                raise ValidationError(
                    {
                        "branch": (
                            "No se puede crear una asignacion de empresa si ya existen asignaciones para este rol."
                        )
                    }
                )

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        scope = self.branch if self.branch_id else "Toda la empresa"
        return f"{self.membership} - {self.role} - {scope}"
