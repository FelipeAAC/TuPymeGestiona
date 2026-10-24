from django.db import migrations


def import_events(apps, schema_editor):
    Event = apps.get_model("administration", "AdministrationEvent")
    Audit = apps.get_model("maintainers", "MaintainerAuditEvent")
    database = schema_editor.connection.alias
    for event in Event.objects.using(database).select_related("company").iterator(chunk_size=500):
        audit = Audit.objects.using(database).create(
            actor_id=event.actor_id,
            company_id_snapshot=event.company_id,
            event_type=event.event_type,
            resource_type=event.resource_type,
            resource_id=event.resource_id,
            metadata={**(event.metadata or {}), "company_label": event.company.name, "administration_event_id": event.pk},
        )
        Audit.objects.using(database).filter(pk=audit.pk).update(created_at=event.created_at)


class Migration(migrations.Migration):
    dependencies = [
        ("maintainers", "0002_challenge_reason"),
        ("administration", "0001_initial"),
    ]
    operations = [migrations.RunPython(import_events, migrations.RunPython.noop)]
