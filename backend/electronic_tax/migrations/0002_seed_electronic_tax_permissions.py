from django.db import migrations


PERMISSIONS = (
    ("electronic_tax_document.view", "BRANCH_SCOPED"),
    ("electronic_tax_document.create", "BRANCH_SCOPED"),
    ("electronic_tax_document.validate", "BRANCH_SCOPED"),
    ("electronic_tax_document.issue", "BRANCH_SCOPED"),
    ("electronic_tax_document.adjust", "BRANCH_SCOPED"),
    ("electronic_tax_folio.manage", "COMPANY_ONLY"),
)


def seed_permissions(apps, schema_editor):
    Permission = apps.get_model("organizations", "Permission")
    for code, scope_behavior in PERMISSIONS:
        Permission.objects.update_or_create(
            code=code,
            defaults={"scope_behavior": scope_behavior},
        )


class Migration(migrations.Migration):
    dependencies = [
        ("electronic_tax", "0001_initial"),
        ("organizations", "0007_seed_customers_manage_permission"),
    ]

    operations = [
        migrations.RunPython(seed_permissions, migrations.RunPython.noop),
    ]
