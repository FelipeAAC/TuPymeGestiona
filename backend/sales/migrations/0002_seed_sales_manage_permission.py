from django.db import migrations


SALES_MANAGE_PERMISSION_CODE = "sales.manage"
BRANCH_SCOPED = "BRANCH_SCOPED"


def seed_sales_manage_permission(apps, schema_editor):
    Permission = apps.get_model("organizations", "Permission")

    Permission.objects.update_or_create(
        code=SALES_MANAGE_PERMISSION_CODE,
        defaults={"scope_behavior": BRANCH_SCOPED},
    )


class Migration(migrations.Migration):

    dependencies = [
        ("sales", "0001_initial"),
        ("organizations", "0007_seed_customers_manage_permission"),
    ]

    operations = [
        migrations.RunPython(
            seed_sales_manage_permission,
            migrations.RunPython.noop,
        ),
    ]
