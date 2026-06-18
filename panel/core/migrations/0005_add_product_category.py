from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0004_product_timestamps'),
    ]

    operations = [
        migrations.AddField(
            model_name='product',
            name='category',
            field=models.CharField(max_length=50, null=True, blank=True),
        ),
    ]
