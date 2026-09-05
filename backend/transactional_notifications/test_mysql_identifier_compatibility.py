import importlib

from django.db import connection
from django.db.migrations.operations.models import CreateModel
from django.test import TestCase

from transactional_notifications.models import TransactionalNotificationAttempt


MYSQL_IDENTIFIER_LIMIT = 64
SHORT_TABLE = "tx_notification_attempt"
LONG_TABLE = "transactional_notifications_transactionalnotificationattempt"


class TransactionalNotificationMySQLIdentifierTests(TestCase):
    def test_attempt_table_name_avoids_mysql_implicit_check_identifier_overflow(self):
        self.assertEqual(
            TransactionalNotificationAttempt._meta.db_table,
            SHORT_TABLE,
        )
        # MySQL auto-names an anonymous field CHECK as <table>_chk_N.
        self.assertLessEqual(
            len(f"{SHORT_TABLE}_chk_1"),
            MYSQL_IDENTIFIER_LIMIT,
        )
        self.assertGreater(
            len(f"{LONG_TABLE}_chk_1"),
            MYSQL_IDENTIFIER_LIMIT,
        )

        tables = set(connection.introspection.table_names())
        self.assertIn(SHORT_TABLE, tables)
        self.assertNotIn(LONG_TABLE, tables)

    def test_initial_migration_creates_attempt_table_with_safe_name(self):
        migration_module = importlib.import_module(
            "transactional_notifications.migrations.0001_initial"
        )
        operation = next(
            operation
            for operation in migration_module.Migration.operations
            if isinstance(operation, CreateModel)
            and operation.name == "TransactionalNotificationAttempt"
        )
        self.assertEqual(
            operation.options.get("db_table"),
            SHORT_TABLE,
        )
