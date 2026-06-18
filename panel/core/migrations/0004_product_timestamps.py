from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0003_activitylog'),
    ]

    operations = [
        migrations.AddField(
            model_name='product',
            name='created_at',
            field=models.DateTimeField(auto_now_add=True, blank=True, null=True),
        ),
        migrations.AddField(
            model_name='product',
            name='updated_at',
            field=models.DateTimeField(auto_now=True, blank=True, null=True),
        ),
    ]
