from django.db import migrations


INVENTORY_STOCKS_MANAGE_PERMISSION_CODE = (
    "inventory.stocks.manage"
)

BRANCH_SCOPED = "BRANCH_SCOPED"


def seed_inventory_permission(apps, schema_editor):
    Permission = apps.get_model(
        "organizations",
        "Permission",
    )

    Permission.objects.update_or_create(
        code=INVENTORY_STOCKS_MANAGE_PERMISSION_CODE,
        defaults={
            "scope_behavior": BRANCH_SCOPED,
        },
    )


class Migration(migrations.Migration):

    dependencies = [
        (
            "inventory",
            "0001_initial",
        ),
        (
            "organizations",
            "0006_seed_warehouses_manage_permission",
        ),
    ]

    operations = [
        migrations.RunPython(
            seed_inventory_permission,
            migrations.RunPython.noop,
        ),
    ]
