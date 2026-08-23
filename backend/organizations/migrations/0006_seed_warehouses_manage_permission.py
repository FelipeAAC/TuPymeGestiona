from django.db import migrations


WAREHOUSES_MANAGE_PERMISSION_CODE = "organizations.warehouses.manage"
BRANCH_SCOPED = "BRANCH_SCOPED"


def seed_warehouses_manage_permission(apps, schema_editor):
    Permission = apps.get_model(
        "organizations",
        "Permission",
    )

    Permission.objects.update_or_create(
        code=WAREHOUSES_MANAGE_PERMISSION_CODE,
        defaults={
            "scope_behavior": BRANCH_SCOPED,
        },
    )


class Migration(migrations.Migration):

    dependencies = [
        ("organizations", "0005_roleassignment"),
    ]

    operations = [
        migrations.RunPython(
            seed_warehouses_manage_permission,
            migrations.RunPython.noop,
        ),
    ]
