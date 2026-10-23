from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("maintainers", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="destructiveactionchallenge",
            name="reason",
            field=models.CharField(blank=True, default="", max_length=500),
        ),
    ]
