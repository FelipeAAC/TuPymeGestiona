from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0003_user_platform_admin"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="destructive_admin",
            field=models.BooleanField(
                default=False,
                help_text=(
                    "Allows permanent deletion of records from the protected "
                    "maintainer workspace. Assign manually and sparingly."
                ),
            ),
        ),
    ]
