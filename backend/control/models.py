from __future__ import annotations

import uuid

from django.conf import settings
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone


def generate_license_number() -> str:
    return f"LIC-{uuid.uuid4().hex[:8].upper()}-{uuid.uuid4().hex[:4].upper()}"


class GlobalUserManager(BaseUserManager):
    def normalize_email_login(self, email: str) -> str:
        return self.normalize_email(email).strip().lower()

    def create_user(self, email: str, password: str | None = None, **extra_fields):
        if not email:
            raise ValueError("Email is required.")
        user = self.model(email=self.normalize_email_login(email), **extra_fields)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, email: str, password: str | None = None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_platform_admin", True)
        return self.create_user(email, password, **extra_fields)


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Tenant(TimeStampedModel):
    class Status(models.TextChoices):
        PROVISIONING = "PROVISIONING", "Provisioning"
        ACTIVE = "ACTIVE", "Active"
        SUSPENDED = "SUSPENDED", "Suspended"
        DECOMMISSIONED = "DECOMMISSIONED", "Decommissioned"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant_code = models.SlugField(max_length=80, unique=True)
    license_number = models.CharField(max_length=32, unique=True, default=generate_license_number, editable=False)
    display_name = models.CharField(max_length=160)
    legal_name = models.CharField(max_length=240, blank=True)
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.PROVISIONING)
    region = models.CharField(max_length=64, blank=True)
    timezone = models.CharField(max_length=64, default="UTC")
    default_language = models.CharField(max_length=16, default="en")
    subscription_plan = models.CharField(max_length=80, blank=True)
    activated_at = models.DateTimeField(null=True, blank=True)
    suspended_at = models.DateTimeField(null=True, blank=True)

    def __str__(self) -> str:
        return self.tenant_code


class TenantDomain(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="domains")
    hostname = models.CharField(max_length=253, unique=True)
    is_primary = models.BooleanField(default=False)
    verified = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["tenant", "is_primary"], condition=models.Q(is_primary=True), name="one_primary_domain_per_tenant"),
        ]


class TenantDatabase(TimeStampedModel):
    class ProvisioningStatus(models.TextChoices):
        PENDING = "PENDING", "Pending"
        PROVISIONING = "PROVISIONING", "Provisioning"
        READY = "READY", "Ready"
        FAILED = "FAILED", "Failed"

    class HealthStatus(models.TextChoices):
        UNKNOWN = "UNKNOWN", "Unknown"
        HEALTHY = "HEALTHY", "Healthy"
        DEGRADED = "DEGRADED", "Degraded"
        UNAVAILABLE = "UNAVAILABLE", "Unavailable"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.OneToOneField(Tenant, on_delete=models.PROTECT, related_name="database")
    database_alias = models.SlugField(max_length=80, unique=True)
    database_host_reference = models.CharField(max_length=180)
    port = models.PositiveIntegerField(default=5432)
    database_name = models.CharField(max_length=80, unique=True)
    runtime_role_name = models.CharField(max_length=80, unique=True)
    secret_reference = models.CharField(max_length=255)
    sslmode = models.CharField(max_length=20, default="require")
    migration_version = models.CharField(max_length=80, blank=True)
    provisioning_status = models.CharField(max_length=32, choices=ProvisioningStatus.choices, default=ProvisioningStatus.PENDING)
    health_status = models.CharField(max_length=32, choices=HealthStatus.choices, default=HealthStatus.UNKNOWN)
    last_health_check = models.DateTimeField(null=True, blank=True)


class Plan(TimeStampedModel):
    code = models.SlugField(max_length=80, unique=True)
    name = models.CharField(max_length=120)
    is_active = models.BooleanField(default=True)


class PlanModule(TimeStampedModel):
    plan = models.ForeignKey(Plan, on_delete=models.CASCADE, related_name="modules")
    module_code = models.SlugField(max_length=80)

    class Meta:
        unique_together = [("plan", "module_code")]


class Subscription(TimeStampedModel):
    tenant = models.OneToOneField(Tenant, on_delete=models.PROTECT, related_name="subscription")
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT)
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)


class TenantModule(TimeStampedModel):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="modules")
    module_code = models.SlugField(max_length=80)
    enabled = models.BooleanField(default=True)

    class Meta:
        unique_together = [("tenant", "module_code")]


class FeatureFlag(TimeStampedModel):
    code = models.SlugField(max_length=120, unique=True)
    description = models.TextField(blank=True)
    enabled_by_default = models.BooleanField(default=False)


class TenantFeatureFlag(TimeStampedModel):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="feature_flags")
    feature_flag = models.ForeignKey(FeatureFlag, on_delete=models.CASCADE)
    enabled = models.BooleanField(default=False)

    class Meta:
        unique_together = [("tenant", "feature_flag")]


class GlobalUser(AbstractBaseUser, PermissionsMixin, TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=120, blank=True)
    last_name = models.CharField(max_length=120, blank=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_platform_admin = models.BooleanField(default=False)
    password_changed_at = models.DateTimeField(null=True, blank=True)
    failed_login_count = models.PositiveIntegerField(default=0)
    locked_until = models.DateTimeField(null=True, blank=True)
    mfa_required = models.BooleanField(default=False)
    mfa_totp_secret_reference = models.CharField(max_length=255, blank=True)

    objects = GlobalUserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS: list[str] = []

    def save(self, *args, **kwargs):
        self.email = GlobalUser.objects.normalize_email_login(self.email)
        super().save(*args, **kwargs)

    def set_password(self, raw_password):
        super().set_password(raw_password)
        self.password_changed_at = timezone.now()

    def __str__(self) -> str:
        return self.email


class TenantMembership(TimeStampedModel):
    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        SUSPENDED = "SUSPENDED", "Suspended"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="memberships")
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="memberships")
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.ACTIVE)
    is_primary = models.BooleanField(default=False)

    class Meta:
        unique_together = [("user", "tenant")]


class RecoveryCode(TimeStampedModel):
    user = models.ForeignKey(GlobalUser, on_delete=models.CASCADE, related_name="recovery_codes")
    code_hash = models.CharField(max_length=256)
    used_at = models.DateTimeField(null=True, blank=True)

    @classmethod
    def hash_code(cls, code: str) -> str:
        return make_password(code)
