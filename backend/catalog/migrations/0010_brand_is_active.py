from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0009_category_status"),
    ]

    operations = [
        migrations.AddField(
            model_name="brand",
            name="is_active",
            field=models.BooleanField(default=True),
        ),
    ]
