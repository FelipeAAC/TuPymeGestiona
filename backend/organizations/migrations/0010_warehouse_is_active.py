from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("organizations", "0009_companymembership_primary_for_user"),
    ]

    operations = [
        migrations.AddField(
            model_name="warehouse",
            name="is_active",
            field=models.BooleanField(default=True),
        ),
    ]
