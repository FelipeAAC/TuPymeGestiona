from django.conf import settings
from django.db import models


class MaintainerAuditEvent(models.Model):
    """Global audit trail for actions that can outlive a company record."""

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="maintainer_audit_events",
    )
    company_id_snapshot = models.PositiveBigIntegerField(null=True, blank=True)
    event_type = models.CharField(max_length=80)
    resource_type = models.CharField(max_length=80)
    resource_id = models.CharField(max_length=64, blank=True, default="")
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(
                fields=["company_id_snapshot", "-created_at"],
                name="maint_audit_company_idx",
            ),
            models.Index(
                fields=["resource_type", "resource_id"],
                name="maint_audit_resource_idx",
            ),
        ]


class DestructiveActionChallenge(models.Model):
    """One-time server-side challenge for permanent deletion."""

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="destructive_action_challenges",
    )
    company_id_snapshot = models.PositiveBigIntegerField(null=True, blank=True)
    resource_type = models.CharField(max_length=80)
    resource_id = models.CharField(max_length=64)
    confirmation_phrase = models.CharField(max_length=200)
    reason = models.CharField(max_length=500, blank=True, default="")
    token_hash = models.CharField(max_length=64)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(
                fields=["actor", "resource_type", "resource_id"],
                name="maint_challenge_lookup_idx",
            ),
        ]
