from io import StringIO
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from electronic_tax.models import ElectronicTaxDocument


class MySQLCompatibilityTests(TestCase):
    def test_folio_uniqueness_is_portable_without_partial_condition(self):
        constraint = next(
            item
            for item in ElectronicTaxDocument._meta.constraints
            if item.name == "uniq_dte_company_type_folio"
        )
        self.assertIsNone(constraint.condition)
        self.assertEqual(
            tuple(constraint.fields),
            ("company", "type_code", "folio"),
        )

    def test_active_base_guard_uses_unique_nullable_one_to_one(self):
        field = ElectronicTaxDocument._meta.get_field("active_base_sale")
        self.assertTrue(field.one_to_one)
        self.assertTrue(field.null)
        self.assertFalse(field.editable)

    def test_active_base_guard_syncs_from_sale_and_flag(self):
        document = ElectronicTaxDocument(sale_id=123, is_active_base=True)
        document._sync_active_base_sale()
        self.assertEqual(document.active_base_sale_id, 123)

        document.is_active_base = False
        document._sync_active_base_sale()
        self.assertIsNone(document.active_base_sale_id)

    @patch("organizations.management.commands.diagnose_mysql.MigrationExecutor")
    def test_diagnose_stops_cleanly_before_domain_queries_when_migrations_pending(
        self,
        executor_class,
    ):
        migration = SimpleNamespace(app_label="orders", name="0001_initial")
        executor = MagicMock()
        executor.loader.graph.leaf_nodes.return_value = [("orders", "0004")]
        executor.migration_plan.return_value = [(migration, False)]
        executor_class.return_value = executor

        out = StringIO()
        with patch(
            "organizations.management.commands.diagnose_mysql.Warehouse.objects.filter"
        ) as warehouse_filter:
            call_command(
                "diagnose_mysql",
                "--allow-non-mysql",
                stdout=out,
            )

        warehouse_filter.assert_not_called()
        rendered = out.getvalue()
        self.assertIn("orders.0001_initial", rendered)
        self.assertIn("Integridad de dominio omitida", rendered)

        with self.assertRaises(CommandError):
            call_command(
                "diagnose_mysql",
                "--allow-non-mysql",
                "--strict",
                stdout=StringIO(),
            )
