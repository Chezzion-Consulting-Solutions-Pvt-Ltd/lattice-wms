from __future__ import annotations

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db import IntegrityError
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.views import APIView

from audit.models import AuditEvent
from control.api.common import IsOwnerConsoleUser, record_owner_audit, validation_error
from control.api.modules import DEFAULT_MODULES, ensure_default_modules
from control.api.serializers import tenant_summary
from control.models import License, OwnerNotification, Tenant, TenantAdminInvitation, TenantConfiguration, TenantDatabase, TenantDomain, TenantMembership, TenantModule
from identity.models import MembershipRole, Permission, Role, RolePermission
from tenancy.connections import register_tenant_database
from tenancy.provisioning import build_tenant_database_plan, execute_tenant_database_plan, validate_pg_identifier

TENANT_ADMIN_PERMISSIONS = [
    "tenant.admin.access",
    "tenant.users.manage",
    "tenant.roles.manage",
    "tenant.settings.manage",
    "tenant.modules.view",
    "tenant.warehouses.manage",
]


class OwnerTenantProvisionView(APIView):
    throttle_scope = "admin_api"
    permission_classes = [IsOwnerConsoleUser]
    required_permission = "platform.tenants.provision"

    def post(self, request):
        tenant_code = str(request.data.get("tenant_code", "")).strip().lower()
        display_name = str(request.data.get("display_name", "")).strip()
        secret_reference = str(request.data.get("secret_reference", "")).strip()
        if not tenant_code or not display_name or not secret_reference:
            return validation_error("Tenant code, display name, and secret reference are required.")
        try:
            validate_pg_identifier(tenant_code)
            plan = build_tenant_database_plan(tenant_code, secret_reference)
        except ValueError:
            return validation_error("Tenant code must be a safe PostgreSQL identifier.")

        tenant = None
        database = None
        try:
            tenant = Tenant.objects.create(
                tenant_code=tenant_code,
                display_name=display_name,
                legal_name=str(request.data.get("legal_name", "")).strip(),
                region=str(request.data.get("region", "")).strip(),
                timezone=str(request.data.get("timezone", "UTC")).strip() or "UTC",
                default_language=str(request.data.get("default_language", "en")).strip() or "en",
                subscription_plan=str(request.data.get("subscription_plan", "")).strip(),
                status=Tenant.Status.PROVISIONING,
            )
            License.objects.create(tenant=tenant, license_number=tenant.license_number)
            domain_hostname = str(request.data.get("domain", "")).strip().lower().rstrip(".")
            if domain_hostname:
                TenantDomain.objects.create(
                    tenant=tenant,
                    hostname=domain_hostname.split(":", 1)[0],
                    verification_method=TenantDomain.VerificationMethod.LOCAL_DEVELOPMENT if domain_hostname.endswith(".localhost") else TenantDomain.VerificationMethod.DNS_TXT,
                    verified=domain_hostname.endswith(".localhost"),
                    is_active=domain_hostname.endswith(".localhost"),
                    is_primary=True,
                    verified_at=timezone.now() if domain_hostname.endswith(".localhost") else None,
                )
            database = TenantDatabase.objects.create(
                tenant=tenant,
                database_alias=f"tenant_{tenant_code}",
                database_host_reference=str(request.data.get("database_host_reference", "postgres")).strip() or "postgres",
                database_name=plan.database_name,
                runtime_role_name=plan.runtime_role_name,
                secret_reference=plan.secret_reference,
                sslmode=str(request.data.get("sslmode", "prefer")).strip() or "prefer",
                provisioning_status=TenantDatabase.ProvisioningStatus.PROVISIONING,
                provisioning_step=TenantDatabase.ProvisioningStep.DATABASE_CREATING,
                health_status=TenantDatabase.HealthStatus.UNKNOWN,
            )

            execute_tenant_database_plan(plan)
            update_provisioning_step(database, TenantDatabase.ProvisioningStep.ROLE_CREATED)
            register_tenant_database(database)
            update_provisioning_step(database, TenantDatabase.ProvisioningStep.MIGRATING)
            call_command("migrate_tenant_databases", tenant_code=tenant_code, verbosity=0)
            update_provisioning_step(database, TenantDatabase.ProvisioningStep.CONFIGURING)
            configure_tenant_defaults(tenant)
            update_provisioning_step(database, TenantDatabase.ProvisioningStep.ADMIN_INVITING)
            invitation = ensure_tenant_admin_invitation(
                tenant,
                request.user,
                email=str(request.data.get("admin_email", "")).strip() or request.user.email,
                first_name=str(request.data.get("admin_first_name", "")).strip(),
                last_name=str(request.data.get("admin_last_name", "")).strip(),
            )
            update_provisioning_step(database, TenantDatabase.ProvisioningStep.HEALTH_CHECKING)
            database.provisioning_status = TenantDatabase.ProvisioningStatus.READY
            database.provisioning_step = TenantDatabase.ProvisioningStep.READY
            database.health_status = TenantDatabase.HealthStatus.HEALTHY
            database.safe_error_summary = ""
            database.last_health_check = timezone.now()
            database.save(update_fields=["provisioning_status", "provisioning_step", "health_status", "safe_error_summary", "last_health_check", "updated_at"])
            tenant.status = Tenant.Status.ACTIVE
            tenant.activated_at = timezone.now()
            tenant.save(update_fields=["status", "activated_at", "updated_at"])
        except IntegrityError:
            return validation_error("Tenant provisioning conflict. Check tenant code, domain, database, and role uniqueness.", "TENANT_PROVISIONING_CONFLICT", status.HTTP_409_CONFLICT)
        except Exception as exc:
            safe_error = "Tenant provisioning failed. Check admin connector, secret reference, and database availability."
            if database is not None:
                database.provisioning_status = TenantDatabase.ProvisioningStatus.FAILED
                database.provisioning_step = TenantDatabase.ProvisioningStep.FAILED
                database.health_status = TenantDatabase.HealthStatus.UNAVAILABLE
                database.safe_error_summary = safe_error
                database.save(update_fields=["provisioning_status", "provisioning_step", "health_status", "safe_error_summary", "updated_at"])
            if tenant is not None:
                OwnerNotification.objects.create(
                    notification_type=OwnerNotification.NotificationType.TENANT_PROVISIONING_FAILED,
                    title="Tenant provisioning failed",
                    message=f"{tenant.display_name} could not be provisioned.",
                    source_type="Tenant",
                    source_id=str(tenant.id),
                )
                record_owner_audit(
                    request,
                    "TENANT_PROVISIONING_FAILED",
                    resource_type="Tenant",
                    resource_id=str(tenant.id),
                    after={"tenant_code": tenant.tenant_code},
                    result=AuditEvent.Result.FAILURE,
                    failure_reason=safe_error,
                )
            return JsonResponse({"error": {"code": "TENANT_PROVISIONING_FAILED", "message": safe_error}}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        record_owner_audit(request, "TENANT_CREATED", resource_type="Tenant", resource_id=str(tenant.id), after=tenant_summary(tenant))
        return JsonResponse({"tenant": tenant_summary(tenant), "admin_invitation_id": str(invitation.id)}, status=status.HTTP_201_CREATED)


class OwnerTenantProvisionRetryView(APIView):
    throttle_scope = "admin_api"
    permission_classes = [IsOwnerConsoleUser]
    required_permission = "platform.tenants.provision"

    def post(self, request, tenant_id):
        tenant = get_object_or_404(Tenant.objects.select_related("database"), id=tenant_id)
        database = getattr(tenant, "database", None)
        if database is None:
            return validation_error("Tenant database metadata is required before retrying provisioning.")
        if database.provisioning_status == TenantDatabase.ProvisioningStatus.READY:
            return validation_error("Tenant database is already ready.", "TENANT_ALREADY_READY", status.HTTP_409_CONFLICT)
        try:
            validate_pg_identifier(tenant.tenant_code)
            plan = build_tenant_database_plan(tenant.tenant_code, database.secret_reference)
            update_provisioning_step(database, TenantDatabase.ProvisioningStep.DATABASE_CREATING)
            execute_tenant_database_plan(plan)
            update_provisioning_step(database, TenantDatabase.ProvisioningStep.ROLE_CREATED)
            register_tenant_database(database)
            update_provisioning_step(database, TenantDatabase.ProvisioningStep.MIGRATING)
            call_command("migrate_tenant_databases", tenant_code=tenant.tenant_code, verbosity=0)
            update_provisioning_step(database, TenantDatabase.ProvisioningStep.CONFIGURING)
            configure_tenant_defaults(tenant)
            update_provisioning_step(database, TenantDatabase.ProvisioningStep.ADMIN_INVITING)
            ensure_tenant_admin_invitation(tenant, request.user, email=str(request.data.get("admin_email", "")).strip() or request.user.email)
            update_provisioning_step(database, TenantDatabase.ProvisioningStep.HEALTH_CHECKING)
            database.provisioning_status = TenantDatabase.ProvisioningStatus.READY
            database.provisioning_step = TenantDatabase.ProvisioningStep.READY
            database.health_status = TenantDatabase.HealthStatus.HEALTHY
            database.safe_error_summary = ""
            database.last_health_check = timezone.now()
            database.save(update_fields=["provisioning_status", "provisioning_step", "health_status", "safe_error_summary", "last_health_check", "updated_at"])
            tenant.status = Tenant.Status.ACTIVE
            tenant.activated_at = tenant.activated_at or timezone.now()
            tenant.save(update_fields=["status", "activated_at", "updated_at"])
        except Exception:
            safe_error = "Tenant provisioning retry failed. Check admin connector, secret reference, and database availability."
            database.provisioning_status = TenantDatabase.ProvisioningStatus.FAILED
            database.provisioning_step = TenantDatabase.ProvisioningStep.FAILED
            database.health_status = TenantDatabase.HealthStatus.UNAVAILABLE
            database.safe_error_summary = safe_error
            database.save(update_fields=["provisioning_status", "provisioning_step", "health_status", "safe_error_summary", "updated_at"])
            record_owner_audit(
                request,
                "TENANT_PROVISIONING_RETRY_FAILED",
                resource_type="Tenant",
                resource_id=str(tenant.id),
                after={"tenant_code": tenant.tenant_code},
                result=AuditEvent.Result.FAILURE,
                failure_reason=safe_error,
            )
            return JsonResponse({"error": {"code": "TENANT_PROVISIONING_RETRY_FAILED", "message": safe_error}}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        record_owner_audit(request, "TENANT_PROVISIONING_RETRIED", resource_type="Tenant", resource_id=str(tenant.id), after=tenant_summary(tenant))
        return JsonResponse({"tenant": tenant_summary(tenant)})


def update_provisioning_step(database: TenantDatabase, step: str) -> None:
    database.provisioning_step = step
    database.provisioning_status = TenantDatabase.ProvisioningStatus.PROVISIONING
    database.save(update_fields=["provisioning_status", "provisioning_step", "updated_at"])


def configure_tenant_defaults(tenant: Tenant) -> TenantConfiguration:
    ensure_default_modules()
    default_modules = [code for code, _name in DEFAULT_MODULES]
    configuration, _created = TenantConfiguration.objects.update_or_create(
        tenant=tenant,
        defaults={
            "timezone": tenant.timezone,
            "language": tenant.default_language,
            "enabled_module_defaults": default_modules,
            "security_policy": {"mfa_required_for_admins": True, "session_timeout_minutes": 60},
            "status": TenantConfiguration.Status.READY,
        },
    )
    for module_code in default_modules:
        TenantModule.objects.update_or_create(
            tenant=tenant,
            module_code=module_code,
            defaults={"enabled": True, "source": TenantModule.Source.PLAN, "override_state": TenantModule.OverrideState.INHERIT},
        )
    return configuration


def ensure_tenant_admin_invitation(tenant: Tenant, owner_user, *, email: str, first_name: str = "", last_name: str = "") -> TenantAdminInvitation:
    normalized_email = get_user_model().objects.normalize_email_login(email)
    admin_user, created = get_user_model().objects.get_or_create(email=normalized_email)
    if created:
        admin_user.set_unusable_password()
    if first_name and not admin_user.first_name:
        admin_user.first_name = first_name
    if last_name and not admin_user.last_name:
        admin_user.last_name = last_name
    admin_user.mfa_required = True
    admin_user.is_active = True
    admin_user.save(update_fields=["first_name", "last_name", "mfa_required", "is_active", "password", "updated_at"])

    membership, _created = TenantMembership.objects.get_or_create(user=admin_user, tenant=tenant, defaults={"is_primary": True})
    role = ensure_tenant_admin_role()
    MembershipRole.objects.get_or_create(membership=membership, role=role)

    existing = TenantAdminInvitation.objects.filter(
        tenant=tenant,
        email=normalized_email,
        status=TenantAdminInvitation.Status.PENDING,
        expires_at__gt=timezone.now(),
    ).first()
    if existing:
        return existing

    token = TenantAdminInvitation.issue_token()
    return TenantAdminInvitation.objects.create(
        tenant=tenant,
        user=admin_user,
        email=normalized_email,
        first_name=first_name,
        last_name=last_name,
        token_hash=TenantAdminInvitation.hash_token(token),
        expires_at=timezone.now() + timezone.timedelta(hours=getattr(settings, "TENANT_ADMIN_INVITATION_TTL_HOURS", 72)),
    )


def ensure_tenant_admin_role() -> Role:
    role, _created = Role.objects.get_or_create(code="TENANT_ADMIN", defaults={"name": "Tenant Administrator", "scope": Role.Scope.TENANT, "requires_mfa": True})
    for code in TENANT_ADMIN_PERMISSIONS:
        permission, _created = Permission.objects.get_or_create(code=code)
        RolePermission.objects.get_or_create(role=role, permission=permission)
    return role
