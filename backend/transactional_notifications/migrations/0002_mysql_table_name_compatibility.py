from django.db import migrations


LONG_TABLE = "transactional_notifications_transactionalnotificationattempt"
SHORT_TABLE = "tx_notification_attempt"


def ensure_short_attempt_table(apps, schema_editor):
    tables = set(schema_editor.connection.introspection.table_names())
    model = apps.get_model(
        "transactional_notifications",
        "TransactionalNotificationAttempt",
    )

    if SHORT_TABLE in tables and LONG_TABLE not in tables:
        return

    if LONG_TABLE in tables and SHORT_TABLE not in tables:
        schema_editor.alter_db_table(model, LONG_TABLE, SHORT_TABLE)
        return

    if SHORT_TABLE in tables and LONG_TABLE in tables:
        raise RuntimeError(
            "Existen simultáneamente las tablas de intentos corta y legacy."
        )

    raise RuntimeError(
        "No existe ninguna tabla de intentos transaccionales para normalizar."
    )


class Migration(migrations.Migration):

    dependencies = [
        ("transactional_notifications", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(
            ensure_short_attempt_table,
            migrations.RunPython.noop,
        ),
    ]
