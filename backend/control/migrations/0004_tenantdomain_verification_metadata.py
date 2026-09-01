from django.db import migrations, models
from django.utils import timezone


def populate_verified_at(apps, schema_editor):
    TenantDomain = apps.get_model("control", "TenantDomain")
    TenantDomain.objects.filter(verified=True, verified_at__isnull=True).update(verified_at=timezone.now())


class Migration(migrations.Migration):
    dependencies = [
        ("control", "0003_alter_globaluser_groups_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="tenantdomain",
            name="is_active",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="tenantdomain",
            name="verification_method",
            field=models.CharField(
                choices=[("DNS_TXT", "DNS TXT"), ("HTTP_FILE", "HTTP file"), ("LOCAL_DEVELOPMENT", "Local development")],
                default="DNS_TXT",
                max_length=32,
            ),
        ),
        migrations.AddField(
            model_name="tenantdomain",
            name="verified_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.RunPython(populate_verified_at, migrations.RunPython.noop),
    ]
