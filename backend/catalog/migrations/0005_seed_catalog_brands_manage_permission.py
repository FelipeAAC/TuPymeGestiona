from django.db import migrations


CATALOG_BRANDS_MANAGE_PERMISSION_CODE = "catalog.brands.manage"
COMPANY_ONLY = "COMPANY_ONLY"


def seed_catalog_brands_manage_permission(apps, schema_editor):
    Permission = apps.get_model(
        "organizations",
        "Permission",
    )

    Permission.objects.update_or_create(
        code=CATALOG_BRANDS_MANAGE_PERMISSION_CODE,
        defaults={
            "scope_behavior": COMPANY_ONLY,
        },
    )


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0004_seed_catalog_categories_manage_permission"),
    ]

    operations = [
        migrations.RunPython(
            seed_catalog_brands_manage_permission,
            migrations.RunPython.noop,
        ),
    ]
