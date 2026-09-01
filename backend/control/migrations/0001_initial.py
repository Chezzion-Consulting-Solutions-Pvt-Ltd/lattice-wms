# Generated for Lattice secure core.
import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="FeatureFlag",
            fields=[
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.SlugField(max_length=120, unique=True)),
                ("description", models.TextField(blank=True)),
                ("enabled_by_default", models.BooleanField(default=False)),
            ],
            options={"abstract": False},
        ),
        migrations.CreateModel(
            name="GlobalUser",
            fields=[
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("email", models.EmailField(max_length=254, unique=True)),
                ("password_hash", models.CharField(blank=True, max_length=256)),
                ("is_active", models.BooleanField(default=True)),
                ("mfa_required", models.BooleanField(default=False)),
                ("mfa_totp_secret_reference", models.CharField(blank=True, max_length=255)),
            ],
            options={"abstract": False},
        ),
        migrations.CreateModel(
            name="Plan",
            fields=[
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.SlugField(max_length=80, unique=True)),
                ("name", models.CharField(max_length=120)),
                ("is_active", models.BooleanField(default=True)),
            ],
            options={"abstract": False},
        ),
        migrations.CreateModel(
            name="Tenant",
            fields=[
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("tenant_code", models.SlugField(max_length=80, unique=True)),
                ("display_name", models.CharField(max_length=160)),
                ("legal_name", models.CharField(blank=True, max_length=240)),
                ("status", models.CharField(choices=[("PROVISIONING", "Provisioning"), ("ACTIVE", "Active"), ("SUSPENDED", "Suspended"), ("DECOMMISSIONED", "Decommissioned")], default="PROVISIONING", max_length=32)),
                ("region", models.CharField(blank=True, max_length=64)),
                ("timezone", models.CharField(default="UTC", max_length=64)),
                ("default_language", models.CharField(default="en", max_length=16)),
                ("subscription_plan", models.CharField(blank=True, max_length=80)),
                ("activated_at", models.DateTimeField(blank=True, null=True)),
                ("suspended_at", models.DateTimeField(blank=True, null=True)),
            ],
            options={"abstract": False},
        ),
        migrations.CreateModel(
            name="PlanModule",
            fields=[
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("module_code", models.SlugField(max_length=80)),
                ("plan", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="modules", to="control.plan")),
            ],
            options={"unique_together": {("plan", "module_code")}},
        ),
        migrations.CreateModel(
            name="RecoveryCode",
            fields=[
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code_hash", models.CharField(max_length=256)),
                ("used_at", models.DateTimeField(blank=True, null=True)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="recovery_codes", to="control.globaluser")),
            ],
            options={"abstract": False},
        ),
        migrations.CreateModel(
            name="Subscription",
            fields=[
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("starts_at", models.DateTimeField()),
                ("ends_at", models.DateTimeField(blank=True, null=True)),
                ("is_active", models.BooleanField(default=True)),
                ("plan", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="control.plan")),
                ("tenant", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name="subscription", to="control.tenant")),
            ],
            options={"abstract": False},
        ),
        migrations.CreateModel(
            name="TenantDatabase",
            fields=[
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("database_alias", models.SlugField(max_length=80, unique=True)),
                ("database_host_reference", models.CharField(max_length=180)),
                ("port", models.PositiveIntegerField(default=5432)),
                ("database_name", models.CharField(max_length=80, unique=True)),
                ("runtime_role_name", models.CharField(max_length=80, unique=True)),
                ("secret_reference", models.CharField(max_length=255)),
                ("sslmode", models.CharField(default="require", max_length=20)),
                ("migration_version", models.CharField(blank=True, max_length=80)),
                ("provisioning_status", models.CharField(choices=[("PENDING", "Pending"), ("PROVISIONING", "Provisioning"), ("READY", "Ready"), ("FAILED", "Failed")], default="PENDING", max_length=32)),
                ("health_status", models.CharField(choices=[("UNKNOWN", "Unknown"), ("HEALTHY", "Healthy"), ("DEGRADED", "Degraded"), ("UNAVAILABLE", "Unavailable")], default="UNKNOWN", max_length=32)),
                ("last_health_check", models.DateTimeField(blank=True, null=True)),
                ("tenant", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name="database", to="control.tenant")),
            ],
            options={"abstract": False},
        ),
        migrations.CreateModel(
            name="TenantDomain",
            fields=[
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("hostname", models.CharField(max_length=253, unique=True)),
                ("is_primary", models.BooleanField(default=False)),
                ("verified", models.BooleanField(default=False)),
                ("tenant", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="domains", to="control.tenant")),
            ],
        ),
        migrations.CreateModel(
            name="TenantFeatureFlag",
            fields=[
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("enabled", models.BooleanField(default=False)),
                ("feature_flag", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="control.featureflag")),
                ("tenant", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="feature_flags", to="control.tenant")),
            ],
            options={"unique_together": {("tenant", "feature_flag")}},
        ),
        migrations.CreateModel(
            name="TenantMembership",
            fields=[
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("status", models.CharField(choices=[("ACTIVE", "Active"), ("SUSPENDED", "Suspended")], default="ACTIVE", max_length=32)),
                ("is_primary", models.BooleanField(default=False)),
                ("tenant", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="memberships", to="control.tenant")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="memberships", to="control.globaluser")),
            ],
            options={"unique_together": {("user", "tenant")}},
        ),
        migrations.CreateModel(
            name="TenantModule",
            fields=[
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("module_code", models.SlugField(max_length=80)),
                ("enabled", models.BooleanField(default=True)),
                ("tenant", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="modules", to="control.tenant")),
            ],
            options={"unique_together": {("tenant", "module_code")}},
        ),
        migrations.AddConstraint(
            model_name="tenantdomain",
            constraint=models.UniqueConstraint(condition=models.Q(is_primary=True), fields=("tenant", "is_primary"), name="one_primary_domain_per_tenant"),
        ),
    ]
