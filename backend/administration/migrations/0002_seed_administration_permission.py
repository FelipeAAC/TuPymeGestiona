from django.db import migrations


ADMIN_PERMISSION_CODE = "administration.manage"


def seed_administration_permission(apps, schema_editor):
    Permission = apps.get_model("organizations", "Permission")
    CompanyRole = apps.get_model("organizations", "CompanyRole")
    CompanyRolePermission = apps.get_model("organizations", "CompanyRolePermission")

    permission, _ = Permission.objects.update_or_create(
        code=ADMIN_PERMISSION_CODE,
        defaults={"scope_behavior": "COMPANY_ONLY"},
    )

    admin_names = {"administrador", "admin", "administrator"}
    for role in CompanyRole.objects.filter(status="ACTIVE"):
        normalized = " ".join((role.name_normalized or role.name or "").split()).casefold()
        if normalized in admin_names:
            has_branch_assignments = role.assignments.filter(branch__isnull=False).exists()
            has_company_assignment = role.assignments.filter(branch__isnull=True).exists()
            if has_branch_assignments and not has_company_assignment:
                continue
            CompanyRolePermission.objects.get_or_create(
                role=role,
                permission=permission,
            )


def unseed_administration_permission(apps, schema_editor):
    Permission = apps.get_model("organizations", "Permission")
    Permission.objects.filter(code=ADMIN_PERMISSION_CODE).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("administration", "0001_initial"),
        ("organizations", "0008_branch_address_branch_city_branch_commune_and_more"),
    ]

    operations = [
        migrations.RunPython(
            seed_administration_permission,
            unseed_administration_permission,
        )
    ]
