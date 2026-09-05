from django.db import migrations, models
import django.db.models.deletion


LEGACY_CONSTRAINT_NAMES = {
    "uniq_dte_company_type_folio",
    "uniq_dte_active_base_per_sale",
}


def remove_legacy_partial_constraints(apps, schema_editor):
    if not schema_editor.connection.features.supports_partial_indexes:
        return
    document = apps.get_model("electronic_tax", "ElectronicTaxDocument")
    by_name = {constraint.name: constraint for constraint in document._meta.constraints}
    for name in LEGACY_CONSTRAINT_NAMES:
        constraint = by_name.get(name)
        if constraint is not None:
            schema_editor.remove_constraint(document, constraint)


def restore_legacy_partial_constraints(apps, schema_editor):
    if not schema_editor.connection.features.supports_partial_indexes:
        return
    document = apps.get_model("electronic_tax", "ElectronicTaxDocument")
    constraints = [
        models.UniqueConstraint(
            fields=("company", "type_code", "folio"),
            condition=models.Q(folio__isnull=False),
            name="uniq_dte_company_type_folio",
        ),
        models.UniqueConstraint(
            fields=("company", "sale"),
            condition=models.Q(is_active_base=True),
            name="uniq_dte_active_base_per_sale",
        ),
    ]
    for constraint in constraints:
        schema_editor.add_constraint(document, constraint)


def populate_active_base_guard(apps, schema_editor):
    document = apps.get_model("electronic_tax", "ElectronicTaxDocument")
    duplicate = (
        document.objects.filter(is_active_base=True)
        .values("sale_id")
        .annotate(total=models.Count("id"))
        .filter(total__gt=1)
        .order_by("sale_id")
        .first()
    )
    if duplicate is not None:
        raise RuntimeError(
            "No se puede activar el guard MySQL: la venta "
            f"{duplicate['sale_id']} tiene {duplicate['total']} DTE base activos."
        )

    for row in document.objects.filter(is_active_base=True).only(
        "id", "sale_id", "active_base_sale_id"
    ).iterator():
        row.active_base_sale_id = row.sale_id
        row.save(update_fields=("active_base_sale",))


class Migration(migrations.Migration):

    dependencies = [
        ("electronic_tax", "0005_electronictaxoperationalalert_and_more"),
    ]

    operations = [
        migrations.RunPython(
            remove_legacy_partial_constraints,
            restore_legacy_partial_constraints,
        ),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RemoveConstraint(
                    model_name="electronictaxdocument",
                    name="uniq_dte_company_type_folio",
                ),
                migrations.RemoveConstraint(
                    model_name="electronictaxdocument",
                    name="uniq_dte_active_base_per_sale",
                ),
            ],
            database_operations=[],
        ),
        migrations.AddField(
            model_name="electronictaxdocument",
            name="active_base_sale",
            field=models.OneToOneField(
                blank=True,
                editable=False,
                help_text=(
                    "Guard técnico: solo se informa para la factura base activa de una venta."
                ),
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="+",
                to="sales.sale",
            ),
        ),
        migrations.RunPython(
            populate_active_base_guard,
            migrations.RunPython.noop,
        ),
        migrations.AddConstraint(
            model_name="electronictaxdocument",
            constraint=models.UniqueConstraint(
                fields=("company", "type_code", "folio"),
                name="uniq_dte_company_type_folio",
            ),
        ),
        migrations.AddConstraint(
            model_name="electronictaxdocument",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(
                        active_base_sale=models.F("sale"),
                        is_active_base=True,
                    )
                    | models.Q(
                        active_base_sale__isnull=True,
                        is_active_base=False,
                    )
                ),
                name="dte_active_base_guard_consistent",
            ),
        ),
    ]
