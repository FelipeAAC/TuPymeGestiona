from django.conf import settings
from django.db import migrations, models
from django.db.models.deletion import PROTECT


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="DestructiveActionChallenge",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("company_id_snapshot", models.PositiveBigIntegerField(blank=True, null=True)),
                ("resource_type", models.CharField(max_length=80)),
                ("resource_id", models.CharField(max_length=64)),
                ("confirmation_phrase", models.CharField(max_length=200)),
                ("token_hash", models.CharField(max_length=64)),
                ("expires_at", models.DateTimeField()),
                ("used_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "actor",
                    models.ForeignKey(
                        on_delete=PROTECT,
                        related_name="destructive_action_challenges",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at", "-id"],
                "indexes": [
                    models.Index(
                        fields=["actor", "resource_type", "resource_id"],
                        name="maint_challenge_lookup_idx",
                    )
                ],
            },
        ),
        migrations.CreateModel(
            name="MaintainerAuditEvent",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("company_id_snapshot", models.PositiveBigIntegerField(blank=True, null=True)),
                ("event_type", models.CharField(max_length=80)),
                ("resource_type", models.CharField(max_length=80)),
                ("resource_id", models.CharField(blank=True, default="", max_length=64)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "actor",
                    models.ForeignKey(
                        on_delete=PROTECT,
                        related_name="maintainer_audit_events",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at", "-id"],
                "indexes": [
                    models.Index(
                        fields=["company_id_snapshot", "-created_at"],
                        name="maint_audit_company_idx",
                    ),
                    models.Index(
                        fields=["resource_type", "resource_id"],
                        name="maint_audit_resource_idx",
                    ),
                ],
            },
        ),
    ]
