from django.db import migrations


PRODUCTS_VIEW_PERMISSION_CODE = "catalog.products.view"
TENANT_GLOBAL = "TENANT_GLOBAL"


def seed_catalog_permissions(apps, schema_editor):
    Permission = apps.get_model(
        "organizations",
        "Permission",
    )

    Permission.objects.update_or_create(
        code=PRODUCTS_VIEW_PERMISSION_CODE,
        defaults={
            "scope_behavior": TENANT_GLOBAL,
        },
    )


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(
            seed_catalog_permissions,
            migrations.RunPython.noop,
        ),
    ]
