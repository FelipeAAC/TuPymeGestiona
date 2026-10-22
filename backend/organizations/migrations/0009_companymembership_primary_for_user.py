from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("organizations", "0008_branch_address_branch_city_branch_commune_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="companymembership",
            name="primary_for_user",
            field=models.OneToOneField(
                blank=True,
                null=True,
                on_delete=models.PROTECT,
                related_name="self_service_company_membership",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
