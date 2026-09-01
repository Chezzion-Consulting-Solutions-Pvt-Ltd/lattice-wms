# Generated for Lattice secure core.
import uuid

from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="AuditEvent",
            fields=[
                ("event_id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("timestamp", models.DateTimeField(auto_now_add=True)),
                ("request_id", models.CharField(db_index=True, max_length=80)),
                ("tenant_id", models.UUIDField(blank=True, db_index=True, null=True)),
                ("global_user_id", models.UUIDField(blank=True, db_index=True, null=True)),
                ("tenant_user_id", models.UUIDField(blank=True, null=True)),
                ("warehouse_id", models.UUIDField(blank=True, null=True)),
                ("device_id", models.CharField(blank=True, max_length=120)),
                ("source_ip", models.GenericIPAddressField(blank=True, null=True)),
                ("user_agent", models.TextField(blank=True)),
                ("action", models.CharField(max_length=120)),
                ("resource_type", models.CharField(blank=True, max_length=120)),
                ("resource_id", models.CharField(blank=True, max_length=120)),
                ("before_summary", models.JSONField(blank=True, default=dict)),
                ("after_summary", models.JSONField(blank=True, default=dict)),
                ("result", models.CharField(choices=[("SUCCESS", "Success"), ("DENIED", "Denied"), ("FAILURE", "Failure")], max_length=24)),
                ("failure_reason", models.CharField(blank=True, max_length=240)),
                ("correlation_id", models.CharField(blank=True, db_index=True, max_length=80)),
            ],
            options={"ordering": ["-timestamp"]},
        ),
    ]
