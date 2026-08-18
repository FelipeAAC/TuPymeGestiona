from django.db import migrations


CATALOG_PRODUCTS_MANAGE_PERMISSION_CODE = "catalog.products.manage"
COMPANY_ONLY = "COMPANY_ONLY"


def seed_catalog_manage_permission(apps, schema_editor):
    Permission = apps.get_model("organizations", "Permission")

    Permission.objects.update_or_create(
        code=CATALOG_PRODUCTS_MANAGE_PERMISSION_CODE,
        defaults={
            "scope_behavior": COMPANY_ONLY,
        },
    )


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0002_seed_catalog_permissions"),
    ]

    operations = [
        migrations.RunPython(
            seed_catalog_manage_permission,
            migrations.RunPython.noop,
        ),
    ]
