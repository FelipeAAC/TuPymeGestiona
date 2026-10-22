import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("transactional_notifications", "0002_mysql_table_name_compatibility"),
    ]

    operations = [
        migrations.AlterField(
            model_name="transactionalnotification",
            name="company",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.deletion.PROTECT,
                related_name="transactional_notifications",
                to="organizations.company",
            ),
        ),
        migrations.AlterField(
            model_name="transactionalnotification",
            name="kind",
            field=models.CharField(
                choices=[
                    ("ORDER_CONFIRMED", "Pedido confirmado"),
                    ("ORDER_PREPARED", "Pedido preparado"),
                    ("ORDER_DELIVERED", "Pedido entregado"),
                    ("ORDER_CANCELLED", "Pedido cancelado"),
                    ("PAYMENT_APPROVED", "Pago aprobado"),
                    ("PAYMENT_PENDING", "Pago pendiente"),
                    ("PAYMENT_REJECTED", "Pago rechazado"),
                    ("PAYMENT_CANCELLED", "Pago cancelado"),
                    ("PAYMENT_REFUNDED", "Pago devuelto"),
                    ("PASSWORD_RESET", "Restablecimiento de contraseña"),
                ],
                max_length=40,
            ),
        ),
    ]
