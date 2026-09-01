from __future__ import annotations

import django.db.models.deletion
from django.db import migrations, models

import control.models


def populate_license_numbers(apps, schema_editor):
    Tenant = apps.get_model("control", "Tenant")
    for tenant in Tenant.objects.filter(license_number__isnull=True):
        while True:
            license_number = control.models.generate_license_number()
            if not Tenant.objects.filter(license_number=license_number).exists():
                break
        tenant.license_number = license_number
        tenant.save(update_fields=["license_number"])


class Migration(migrations.Migration):
    dependencies = [
        ("control", "0001_initial"),
        ("auth", "0012_alter_user_first_name_max_length"),
    ]

    operations = [
        migrations.AddField(
            model_name="tenant",
            name="license_number",
            field=models.CharField(blank=True, editable=False, max_length=32, null=True),
        ),
        migrations.RunPython(populate_license_numbers, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="tenant",
            name="license_number",
            field=models.CharField(default=control.models.generate_license_number, editable=False, max_length=32, unique=True),
        ),
        migrations.RenameField(model_name="globaluser", old_name="password_hash", new_name="password"),
        migrations.AddField(model_name="globaluser", name="first_name", field=models.CharField(blank=True, max_length=120)),
        migrations.AddField(model_name="globaluser", name="last_name", field=models.CharField(blank=True, max_length=120)),
        migrations.AddField(model_name="globaluser", name="is_staff", field=models.BooleanField(default=False)),
        migrations.AddField(model_name="globaluser", name="is_superuser", field=models.BooleanField(default=False)),
        migrations.AddField(model_name="globaluser", name="is_platform_admin", field=models.BooleanField(default=False)),
        migrations.AddField(model_name="globaluser", name="password_changed_at", field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name="globaluser", name="last_login", field=models.DateTimeField(blank=True, null=True, verbose_name="last login")),
        migrations.AddField(model_name="globaluser", name="failed_login_count", field=models.PositiveIntegerField(default=0)),
        migrations.AddField(model_name="globaluser", name="locked_until", field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(
            model_name="globaluser",
            name="groups",
            field=models.ManyToManyField(blank=True, related_name="globaluser_set", related_query_name="globaluser", to="auth.group"),
        ),
        migrations.AddField(
            model_name="globaluser",
            name="user_permissions",
            field=models.ManyToManyField(blank=True, related_name="globaluser_set", related_query_name="globaluser", to="auth.permission"),
        ),
        migrations.AlterField(
            model_name="tenantmembership",
            name="user",
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="memberships", to="control.globaluser"),
        ),
    ]
