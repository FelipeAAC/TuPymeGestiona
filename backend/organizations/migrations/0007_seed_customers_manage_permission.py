from django.db import migrations


def create_customers_permission(apps, schema_editor):

    Permission = apps.get_model(
        "organizations",
        "Permission",
    )

    Permission.objects.get_or_create(
        code="customers.manage",
        defaults={
            "scope_behavior": "COMPANY_ONLY",
        },
    )


def remove_customers_permission(apps, schema_editor):

    Permission = apps.get_model(
        "organizations",
        "Permission",
    )

    Permission.objects.filter(
        code="customers.manage",
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        (
            "organizations",
            "0006_seed_warehouses_manage_permission",
        ),
    ]

    operations = [
        migrations.RunPython(
            create_customers_permission,
            remove_customers_permission,
        ),
    ]
