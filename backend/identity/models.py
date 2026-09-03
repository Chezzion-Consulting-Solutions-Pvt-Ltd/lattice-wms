from __future__ import annotations

import hashlib
import secrets
import uuid

from django.conf import settings
from django.db import models


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Permission(TimeStampedModel):
    code = models.CharField(max_length=120, unique=True)
    description = models.CharField(max_length=240, blank=True)

    def __str__(self) -> str:
        return self.code


class Role(TimeStampedModel):
    class Scope(models.TextChoices):
        PLATFORM = "PLATFORM", "Platform"
        TENANT = "TENANT", "Tenant"

    code = models.CharField(max_length=80, unique=True)
    name = models.CharField(max_length=120)
    scope = models.CharField(max_length=24, choices=Scope.choices)
    requires_mfa = models.BooleanField(default=False)
    permissions = models.ManyToManyField(Permission, through="RolePermission", related_name="roles")

    def __str__(self) -> str:
        return self.code


class RolePermission(TimeStampedModel):
    role = models.ForeignKey(Role, on_delete=models.CASCADE)
    permission = models.ForeignKey(Permission, on_delete=models.CASCADE)

    class Meta:
        unique_together = [("role", "permission")]


class MembershipRole(TimeStampedModel):
    membership = models.ForeignKey("control.TenantMembership", on_delete=models.CASCADE, related_name="role_assignments")
    role = models.ForeignKey(Role, on_delete=models.PROTECT)

    class Meta:
        unique_together = [("membership", "role")]


class WarehouseAssignment(TimeStampedModel):
    membership = models.ForeignKey("control.TenantMembership", on_delete=models.CASCADE, related_name="warehouse_assignments")
    warehouse_code = models.CharField(max_length=40)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = [("membership", "warehouse_code")]


class PlatformTenantAccessGrant(TimeStampedModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="platform_tenant_access_grants")
    tenant = models.ForeignKey("control.Tenant", on_delete=models.CASCADE, related_name="platform_access_grants")
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="approved_platform_tenant_access_grants",
    )
    reason = models.CharField(max_length=240)
    expires_at = models.DateTimeField()
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=["user", "tenant", "expires_at"])]


class SecuritySession(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session_key_hash = models.CharField(max_length=128, unique=True)
    jwt_token_hash = models.CharField(max_length=128, unique=True, null=True, blank=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="security_sessions")
    tenant = models.ForeignKey("control.Tenant", on_delete=models.CASCADE, related_name="security_sessions", null=True, blank=True)
    last_seen_at = models.DateTimeField(auto_now=True)
    expires_at = models.DateTimeField()
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    revoke_reason = models.CharField(max_length=160, blank=True)

    @classmethod
    def hash_session_key(cls, session_key: str) -> str:
        return hashlib.sha256(session_key.encode("utf-8")).hexdigest()


class PasswordResetToken(TimeStampedModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="password_reset_tokens")
    token_hash = models.CharField(max_length=128, unique=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=["user", "expires_at", "used_at"])]

    @classmethod
    def issue_token(cls) -> str:
        return secrets.token_urlsafe(32)

    @classmethod
    def hash_token(cls, token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()


class MfaDevice(TimeStampedModel):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="mfa_device")
    secret_reference = models.CharField(max_length=255)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    enabled = models.BooleanField(default=False)


class RecoveryCode(TimeStampedModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="identity_recovery_codes")
    code_hash = models.CharField(max_length=256)
    used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=["user", "used_at"])]
