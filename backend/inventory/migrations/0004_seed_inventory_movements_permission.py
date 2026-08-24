from django.db import migrations


INVENTORY_MOVEMENTS_MANAGE_PERMISSION_CODE = (
    "inventory.movements.manage"
)

BRANCH_SCOPED = "BRANCH_SCOPED"


def seed_inventory_movements_permission(apps, schema_editor):
    Permission = apps.get_model(
        "organizations",
        "Permission",
    )

    Permission.objects.update_or_create(
        code=INVENTORY_MOVEMENTS_MANAGE_PERMISSION_CODE,
        defaults={
            "scope_behavior": BRANCH_SCOPED,
        },
    )


class Migration(migrations.Migration):

    dependencies = [
        (
            "inventory",
            "0003_inventorymovement",
        ),
        (
            "organizations",
            "0006_seed_warehouses_manage_permission",
        ),
    ]

    operations = [
        migrations.RunPython(
            seed_inventory_movements_permission,
            migrations.RunPython.noop,
        ),
    ]
