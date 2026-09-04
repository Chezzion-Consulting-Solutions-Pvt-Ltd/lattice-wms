from __future__ import annotations

import hashlib
import secrets
import uuid

from django.conf import settings
from django.contrib.auth.hashers import make_password
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
    class VerificationMethod(models.TextChoices):
        DNS_TXT = "DNS_TXT", "DNS TXT"
        HTTP_FILE = "HTTP_FILE", "HTTP file"
        LOCAL_DEVELOPMENT = "LOCAL_DEVELOPMENT", "Local development"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="domains")
    hostname = models.CharField(max_length=253, unique=True)
    is_primary = models.BooleanField(default=False)
    verified = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    verification_method = models.CharField(max_length=32, choices=VerificationMethod.choices, default=VerificationMethod.DNS_TXT)
    verified_at = models.DateTimeField(null=True, blank=True)

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

    class ProvisioningStep(models.TextChoices):
        PENDING = "PENDING", "Pending"
        DATABASE_CREATING = "DATABASE_CREATING", "Database creating"
        DATABASE_CREATED = "DATABASE_CREATED", "Database created"
        ROLE_CREATED = "ROLE_CREATED", "Role created"
        MIGRATING = "MIGRATING", "Migrating"
        CONFIGURING = "CONFIGURING", "Configuring"
        ADMIN_INVITING = "ADMIN_INVITING", "Admin inviting"
        HEALTH_CHECKING = "HEALTH_CHECKING", "Health checking"
        READY = "READY", "Ready"
        FAILED = "FAILED", "Failed"

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
    provisioning_step = models.CharField(max_length=40, choices=ProvisioningStep.choices, default=ProvisioningStep.PENDING)
    safe_error_summary = models.CharField(max_length=240, blank=True)
    health_status = models.CharField(max_length=32, choices=HealthStatus.choices, default=HealthStatus.UNKNOWN)
    last_health_check = models.DateTimeField(null=True, blank=True)


class TenantConfiguration(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        READY = "READY", "Ready"
        FAILED = "FAILED", "Failed"

    tenant = models.OneToOneField(Tenant, on_delete=models.CASCADE, related_name="configuration")
    timezone = models.CharField(max_length=64, default="UTC")
    language = models.CharField(max_length=16, default="en")
    enabled_module_defaults = models.JSONField(default=list, blank=True)
    security_policy = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.PENDING)


class TenantAdminInvitation(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        ACCEPTED = "ACCEPTED", "Accepted"
        REVOKED = "REVOKED", "Revoked"
        EXPIRED = "EXPIRED", "Expired"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="admin_invitations")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="tenant_admin_invitations")
    email = models.EmailField()
    first_name = models.CharField(max_length=120, blank=True)
    last_name = models.CharField(max_length=120, blank=True)
    token_hash = models.CharField(max_length=128, unique=True)
    expires_at = models.DateTimeField()
    accepted_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.PENDING)

    class Meta:
        indexes = [models.Index(fields=["tenant", "email", "status"])]

    @classmethod
    def issue_token(cls) -> str:
        return secrets.token_urlsafe(32)

    @classmethod
    def hash_token(cls, token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()


class Plan(TimeStampedModel):
    class BillingInterval(models.TextChoices):
        MONTHLY = "MONTHLY", "Monthly"
        ANNUAL = "ANNUAL", "Annual"
        CUSTOM = "CUSTOM", "Custom"

    code = models.SlugField(max_length=80, unique=True)
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    billing_interval = models.CharField(max_length=24, choices=BillingInterval.choices, default=BillingInterval.MONTHLY)
    price_metadata = models.JSONField(default=dict, blank=True)
    currency = models.CharField(max_length=3, blank=True)
    user_limit = models.PositiveIntegerField(null=True, blank=True)
    warehouse_limit = models.PositiveIntegerField(null=True, blank=True)
    storage_limit_gb = models.PositiveIntegerField(null=True, blank=True)
    api_limit_per_month = models.PositiveIntegerField(null=True, blank=True)
    feature_entitlements = models.JSONField(default=dict, blank=True)
    support_tier = models.CharField(max_length=80, blank=True)


class PlanModule(TimeStampedModel):
    plan = models.ForeignKey(Plan, on_delete=models.CASCADE, related_name="modules")
    module_code = models.SlugField(max_length=80)

    class Meta:
        unique_together = [("plan", "module_code")]


class Subscription(TimeStampedModel):
    class Status(models.TextChoices):
        TRIAL = "TRIAL", "Trial"
        ACTIVE = "ACTIVE", "Active"
        PAST_DUE = "PAST_DUE", "Past due"
        SUSPENDED = "SUSPENDED", "Suspended"
        CANCELLED = "CANCELLED", "Cancelled"
        EXPIRED = "EXPIRED", "Expired"

    tenant = models.OneToOneField(Tenant, on_delete=models.PROTECT, related_name="subscription")
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT)
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.ACTIVE)
    trial_starts_at = models.DateTimeField(null=True, blank=True)
    trial_ends_at = models.DateTimeField(null=True, blank=True)
    starts_at = models.DateTimeField()
    renews_at = models.DateTimeField(null=True, blank=True)
    ends_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    overrides = models.JSONField(default=dict, blank=True)


class License(TimeStampedModel):
    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        EXPIRING = "EXPIRING", "Expiring"
        EXPIRED = "EXPIRED", "Expired"
        REVOKED = "REVOKED", "Revoked"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.OneToOneField(Tenant, on_delete=models.PROTECT, related_name="license")
    license_number = models.CharField(max_length=32, unique=True, default=generate_license_number, editable=False)
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.ACTIVE)
    issued_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField(null=True, blank=True)
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT, null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)


class ModuleDefinition(TimeStampedModel):
    module_code = models.SlugField(max_length=80, unique=True)
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    active = models.BooleanField(default=True)
    display_order = models.PositiveIntegerField(default=0)
    dependencies = models.JSONField(default=list, blank=True)


class TenantModule(TimeStampedModel):
    class Source(models.TextChoices):
        PLAN = "PLAN", "Plan"
        OVERRIDE = "OVERRIDE", "Override"

    class OverrideState(models.TextChoices):
        INHERIT = "INHERIT", "Inherit"
        ENABLED = "ENABLED", "Enabled"
        DISABLED = "DISABLED", "Disabled"

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="modules")
    module_code = models.SlugField(max_length=80)
    enabled = models.BooleanField(default=True)
    source = models.CharField(max_length=24, choices=Source.choices, default=Source.OVERRIDE)
    override_state = models.CharField(max_length=24, choices=OverrideState.choices, default=OverrideState.ENABLED)

    class Meta:
        unique_together = [("tenant", "module_code")]


class TenantModuleHistory(TimeStampedModel):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="module_history")
    module_code = models.SlugField(max_length=80)
    previous_state = models.CharField(max_length=24, blank=True)
    new_state = models.CharField(max_length=24)
    changed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True)


class FeatureFlag(TimeStampedModel):
    code = models.SlugField(max_length=120, unique=True)
    name = models.CharField(max_length=120, blank=True)
    description = models.TextField(blank=True)
    active = models.BooleanField(default=True)
    enabled_by_default = models.BooleanField(default=False)
    environment_metadata = models.JSONField(default=dict, blank=True)


class TenantFeatureFlag(TimeStampedModel):
    class OverrideState(models.TextChoices):
        INHERIT = "INHERIT", "Inherit"
        ENABLED = "ENABLED", "Enabled"
        DISABLED = "DISABLED", "Disabled"

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="feature_flags")
    feature_flag = models.ForeignKey(FeatureFlag, on_delete=models.CASCADE)
    enabled = models.BooleanField(default=False)
    override_state = models.CharField(max_length=24, choices=OverrideState.choices, default=OverrideState.INHERIT)

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


class BackupPolicy(TimeStampedModel):
    tenant = models.OneToOneField(Tenant, on_delete=models.CASCADE, related_name="backup_policy")
    provider = models.CharField(max_length=80, default="NOT_CONFIGURED")
    retention_days = models.PositiveIntegerField(default=30)
    region = models.CharField(max_length=64, blank=True)
    enabled = models.BooleanField(default=False)


class BackupRecord(TimeStampedModel):
    class Status(models.TextChoices):
        HEALTHY = "HEALTHY", "Healthy"
        WARNING = "WARNING", "Warning"
        FAILED = "FAILED", "Failed"
        NOT_CONFIGURED = "NOT_CONFIGURED", "Not configured"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="backup_records")
    provider = models.CharField(max_length=80, default="NOT_CONFIGURED")
    region = models.CharField(max_length=64, blank=True)
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.NOT_CONFIGURED)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    size_bytes = models.PositiveBigIntegerField(null=True, blank=True)
    safe_error_summary = models.CharField(max_length=240, blank=True)
    restore_point_reference = models.CharField(max_length=255, blank=True)


class RestoreRequest(TimeStampedModel):
    class Status(models.TextChoices):
        REQUESTED = "REQUESTED", "Requested"
        APPROVED = "APPROVED", "Approved"
        PREPARING = "PREPARING", "Preparing"
        RESTORING = "RESTORING", "Restoring"
        VERIFYING = "VERIFYING", "Verifying"
        COMPLETED = "COMPLETED", "Completed"
        FAILED = "FAILED", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT, related_name="restore_requests")
    backup = models.ForeignKey(BackupRecord, on_delete=models.PROTECT, null=True, blank=True)
    reason = models.CharField(max_length=240)
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="restore_requests")
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="approved_restore_requests")
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.REQUESTED)
    safe_error_summary = models.CharField(max_length=240, blank=True)
    requested_at = models.DateTimeField(default=timezone.now)
    approved_at = models.DateTimeField(null=True, blank=True)


class PlatformSetting(TimeStampedModel):
    key = models.SlugField(max_length=120, unique=True)
    value = models.JSONField(default=dict, blank=True)
    description = models.CharField(max_length=240, blank=True)


class OwnerNotification(TimeStampedModel):
    class NotificationType(models.TextChoices):
        TENANT_PROVISIONING_FAILED = "TENANT_PROVISIONING_FAILED", "Tenant provisioning failed"
        TENANT_DB_UNHEALTHY = "TENANT_DB_UNHEALTHY", "Tenant database unhealthy"
        BACKUP_FAILED = "BACKUP_FAILED", "Backup failed"
        MIGRATION_FAILED = "MIGRATION_FAILED", "Migration failed"
        LICENSE_EXPIRING = "LICENSE_EXPIRING", "License expiring"
        SUBSCRIPTION_EXPIRING = "SUBSCRIPTION_EXPIRING", "Subscription expiring"
        SUSPICIOUS_LOGIN = "SUSPICIOUS_LOGIN", "Suspicious login"
        MFA_NON_COMPLIANT = "MFA_NON_COMPLIANT", "MFA non-compliant"
        SUPPORT_ACCESS_REQUEST = "SUPPORT_ACCESS_REQUEST", "Support access request"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    notification_type = models.CharField(max_length=64, choices=NotificationType.choices)
    title = models.CharField(max_length=160)
    message = models.CharField(max_length=280)
    source_type = models.CharField(max_length=80, blank=True)
    source_id = models.CharField(max_length=120, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
