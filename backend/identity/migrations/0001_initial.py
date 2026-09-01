from __future__ import annotations

import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("control", "0002_license_and_auth_user"),
    ]

    operations = [
        migrations.CreateModel(
            name="Permission",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("code", models.CharField(max_length=120, unique=True)),
                ("description", models.CharField(blank=True, max_length=240)),
            ],
        ),
        migrations.CreateModel(
            name="Role",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("code", models.CharField(max_length=80, unique=True)),
                ("name", models.CharField(max_length=120)),
                ("scope", models.CharField(choices=[("PLATFORM", "Platform"), ("TENANT", "Tenant")], max_length=24)),
                ("requires_mfa", models.BooleanField(default=False)),
            ],
        ),
        migrations.CreateModel(
            name="MfaDevice",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("secret_reference", models.CharField(max_length=255)),
                ("confirmed_at", models.DateTimeField(blank=True, null=True)),
                ("enabled", models.BooleanField(default=False)),
                ("user", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="mfa_device", to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name="RecoveryCode",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("code_hash", models.CharField(max_length=256)),
                ("used_at", models.DateTimeField(blank=True, null=True)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="identity_recovery_codes", to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name="RolePermission",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("permission", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="identity.permission")),
                ("role", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="identity.role")),
            ],
            options={"unique_together": {("role", "permission")}},
        ),
        migrations.AddField(
            model_name="role",
            name="permissions",
            field=models.ManyToManyField(related_name="roles", through="identity.RolePermission", to="identity.permission"),
        ),
        migrations.CreateModel(
            name="SecuritySession",
            fields=[
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("session_key_hash", models.CharField(max_length=128, unique=True)),
                ("last_seen_at", models.DateTimeField(auto_now=True)),
                ("expires_at", models.DateTimeField()),
                ("ip_address", models.GenericIPAddressField(blank=True, null=True)),
                ("user_agent", models.TextField(blank=True)),
                ("revoked_at", models.DateTimeField(blank=True, null=True)),
                ("revoke_reason", models.CharField(blank=True, max_length=160)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="security_sessions", to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name="MembershipRole",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("membership", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="role_assignments", to="control.tenantmembership")),
                ("role", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="identity.role")),
            ],
            options={"unique_together": {("membership", "role")}},
        ),
        migrations.CreateModel(
            name="WarehouseAssignment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("warehouse_code", models.CharField(max_length=40)),
                ("is_active", models.BooleanField(default=True)),
                ("membership", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="warehouse_assignments", to="control.tenantmembership")),
            ],
            options={"unique_together": {("membership", "warehouse_code")}},
        ),
        migrations.AddIndex(
            model_name="recoverycode",
            index=models.Index(fields=["user", "used_at"], name="identity_re_user_id_9bb5ef_idx"),
        ),
    ]
