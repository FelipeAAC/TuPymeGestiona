from django.db import migrations


INVENTORY_TRANSFERS_MANAGE_PERMISSION_CODE = (
    "inventory.transfers.manage"
)

BRANCH_SCOPED = "BRANCH_SCOPED"


def seed_inventory_transfers_permission(apps, schema_editor):

    Permission = apps.get_model(
        "organizations",
        "Permission",
    )

    Permission.objects.update_or_create(
        code=INVENTORY_TRANSFERS_MANAGE_PERMISSION_CODE,
        defaults={
            "scope_behavior": BRANCH_SCOPED,
        },
    )


class Migration(migrations.Migration):

    dependencies = [
        (
            "inventory",
            "0005_inventorytransfer_inventorytransferitem",
        ),
        (
            "organizations",
            "0006_seed_warehouses_manage_permission",
        ),
    ]

    operations = [
        migrations.RunPython(
            seed_inventory_transfers_permission,
            migrations.RunPython.noop,
        ),
    ]
