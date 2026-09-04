from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0008_product_description_product_image_url"),
    ]

    operations = [
        migrations.AddField(
            model_name="category",
            name="status",
            field=models.CharField(
                choices=[("ACTIVE", "Activo"), ("INACTIVE", "Inactivo")],
                default="ACTIVE",
                max_length=20,
            ),
        ),
    ]
