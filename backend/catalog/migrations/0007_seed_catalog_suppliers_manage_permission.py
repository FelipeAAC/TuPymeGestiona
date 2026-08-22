from django.db import migrations


CATALOG_SUPPLIERS_MANAGE_PERMISSION_CODE = "catalog.suppliers.manage"
COMPANY_ONLY = "COMPANY_ONLY"


def seed_catalog_suppliers_manage_permission(apps, schema_editor):
    Permission = apps.get_model(
        "organizations",
        "Permission",
    )

    Permission.objects.update_or_create(
        code=CATALOG_SUPPLIERS_MANAGE_PERMISSION_CODE,
        defaults={
            "scope_behavior": COMPANY_ONLY,
        },
    )


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0006_supplier"),
    ]

    operations = [
        migrations.RunPython(
            seed_catalog_suppliers_manage_permission,
            migrations.RunPython.noop,
        ),
    ]
