import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("electronic_tax", "0002_seed_electronic_tax_permissions"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="taxcompanyprofile",
            name="economic_activity_code",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="taxcompanyprofile",
            name="sii_branch_code",
            field=models.CharField(blank=True, default="", max_length=20),
        ),
        migrations.AddField(
            model_name="taxcompanyprofile",
            name="sii_resolution_date",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="taxcompanyprofile",
            name="sii_resolution_number",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.CreateModel(
            name="FolioAuthorizationSecret",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("nonce", models.BinaryField()),
                ("encrypted_caf", models.BinaryField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("authorization", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="secret_material", to="electronic_tax.folioauthorization")),
            ],
        ),
        migrations.CreateModel(
            name="ElectronicTaxArtifact",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("kind", models.CharField(choices=[("SIGNED_ENVELOPE", "EnvioDTE firmado")], max_length=32)),
                ("content_hash", models.CharField(max_length=64)),
                ("nonce", models.BinaryField()),
                ("encrypted_payload", models.BinaryField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("document", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="artifacts", to="electronic_tax.electronictaxdocument")),
            ],
        ),
        migrations.CreateModel(
            name="FolioAuthorizationEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("event_type", models.CharField(choices=[("CAF_IMPORTED", "CAF importado"), ("CAF_DISABLED", "CAF deshabilitado")], max_length=32)),
                ("correlation_id", models.UUIDField(default=uuid.uuid4)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("actor", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
                ("authorization", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="audit_events", to="electronic_tax.folioauthorization")),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="folio_authorization_events", to="organizations.company")),
            ],
            options={"ordering": ["authorization_id", "created_at", "id"]},
        ),
        migrations.AddConstraint(
            model_name="electronictaxartifact",
            constraint=models.UniqueConstraint(fields=("document", "kind"), name="uniq_dte_artifact_kind"),
        ),
    ]
