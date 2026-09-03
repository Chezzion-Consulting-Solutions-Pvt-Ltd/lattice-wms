from __future__ import annotations

from typing import Any

from audit.models import AuditEvent
from control.models import (
    BackupPolicy,
    BackupRecord,
    FeatureFlag,
    License,
    ModuleDefinition,
    OwnerNotification,
    Plan,
    PlanModule,
    PlatformSetting,
    RestoreRequest,
    Subscription,
    Tenant,
    TenantDatabase,
    TenantDomain,
    TenantFeatureFlag,
    TenantModule,
)
from identity.models import MfaDevice, Permission, PlatformTenantAccessGrant, Role, SecuritySession


def iso(value) -> str | None:
    return value.isoformat() if value else None


def tenant_summary(tenant: Tenant) -> dict[str, Any]:
    database = getattr(tenant, "database", None)
    try:
        subscription = tenant.subscription
    except Subscription.DoesNotExist:
        subscription = None
    try:
        license_record = tenant.license
    except License.DoesNotExist:
        license_record = None
    primary_domain = next((domain.hostname for domain in tenant.domains.all() if domain.is_primary), "")
    return {
        "id": str(tenant.id),
        "tenant_code": tenant.tenant_code,
        "display_name": tenant.display_name,
        "legal_name": tenant.legal_name,
        "license_number": license_record.license_number if license_record else tenant.license_number,
        "license_status": license_record.status if license_record else "ACTIVE",
        "status": tenant.status,
        "primary_domain": primary_domain,
        "region": tenant.region,
        "timezone": tenant.timezone,
        "default_language": tenant.default_language,
        "subscription_plan": subscription.plan.name if subscription else tenant.subscription_plan or "Unassigned",
        "subscription_status": subscription.status if subscription else "UNASSIGNED",
        "created_at": iso(tenant.created_at),
        "activated_at": iso(tenant.activated_at),
        "suspended_at": iso(tenant.suspended_at),
        "database": database_summary(database),
    }


def database_summary(database: TenantDatabase | None) -> dict[str, Any]:
    if database is None:
        return {
            "alias": "",
            "host_reference": "",
            "port": 5432,
            "name": "",
            "runtime_role": "",
            "sslmode": "",
            "provisioning_status": "MISSING",
            "health_status": "MISSING",
            "migration_version": "",
            "last_health_check": None,
            "secret_reference_configured": False,
        }
    return {
        "alias": database.database_alias,
        "host_reference": database.database_host_reference,
        "port": database.port,
        "name": database.database_name,
        "runtime_role": database.runtime_role_name,
        "sslmode": database.sslmode,
        "provisioning_status": database.provisioning_status,
        "health_status": database.health_status,
        "migration_version": database.migration_version,
        "last_health_check": iso(database.last_health_check),
        "secret_reference_configured": bool(database.secret_reference),
    }


def domain_summary(domain: TenantDomain) -> dict[str, Any]:
    return {
        "id": str(domain.id),
        "tenant_id": str(domain.tenant_id),
        "hostname": domain.hostname,
        "is_primary": domain.is_primary,
        "verified": domain.verified,
        "is_active": domain.is_active,
        "verification_method": domain.verification_method,
        "verified_at": iso(domain.verified_at),
        "created_at": iso(domain.created_at),
    }


def plan_summary(plan: Plan) -> dict[str, Any]:
    return {
        "id": plan.id,
        "code": plan.code,
        "name": plan.name,
        "description": plan.description,
        "active": plan.is_active,
        "billing_interval": plan.billing_interval,
        "user_limit": plan.user_limit,
        "warehouse_limit": plan.warehouse_limit,
        "storage_limit_gb": plan.storage_limit_gb,
        "api_limit_per_month": plan.api_limit_per_month,
        "included_modules": list(plan.modules.order_by("module_code").values_list("module_code", flat=True)),
        "feature_entitlements": plan.feature_entitlements,
        "support_tier": plan.support_tier,
    }


def subscription_summary(subscription: Subscription) -> dict[str, Any]:
    return {
        "id": subscription.id,
        "tenant_id": str(subscription.tenant_id),
        "tenant": subscription.tenant.display_name,
        "tenant_code": subscription.tenant.tenant_code,
        "plan_id": subscription.plan_id,
        "plan": subscription.plan.name,
        "status": subscription.status,
        "trial_starts_at": iso(subscription.trial_starts_at),
        "trial_ends_at": iso(subscription.trial_ends_at),
        "starts_at": iso(subscription.starts_at),
        "renews_at": iso(subscription.renews_at),
        "ends_at": iso(subscription.ends_at),
        "is_active": subscription.is_active,
        "notes": subscription.notes,
        "overrides": subscription.overrides,
    }


def license_summary(license_record: License) -> dict[str, Any]:
    return {
        "id": str(license_record.id),
        "tenant_id": str(license_record.tenant_id),
        "tenant": license_record.tenant.display_name,
        "tenant_code": license_record.tenant.tenant_code,
        "license_number": license_record.license_number,
        "status": license_record.status,
        "issued_at": iso(license_record.issued_at),
        "expires_at": iso(license_record.expires_at),
        "plan": license_record.plan.name if license_record.plan else "",
        "metadata": license_record.metadata,
    }


def module_summary(module: ModuleDefinition) -> dict[str, Any]:
    return {
        "id": module.id,
        "module_code": module.module_code,
        "name": module.name,
        "description": module.description,
        "active": module.active,
        "display_order": module.display_order,
        "dependencies": module.dependencies,
    }


def tenant_module_summary(entitlement: TenantModule) -> dict[str, Any]:
    return {
        "id": entitlement.id,
        "tenant_id": str(entitlement.tenant_id),
        "tenant": entitlement.tenant.display_name,
        "module_code": entitlement.module_code,
        "enabled": entitlement.enabled,
        "source": entitlement.source,
    }


def feature_summary(flag: FeatureFlag) -> dict[str, Any]:
    return {
        "id": flag.id,
        "code": flag.code,
        "name": flag.name or flag.code,
        "description": flag.description,
        "enabled_by_default": flag.enabled_by_default,
        "environment_metadata": flag.environment_metadata,
    }


def tenant_feature_summary(override: TenantFeatureFlag) -> dict[str, Any]:
    effective = override.feature_flag.enabled_by_default
    if override.override_state == TenantFeatureFlag.OverrideState.ENABLED:
        effective = True
    if override.override_state == TenantFeatureFlag.OverrideState.DISABLED:
        effective = False
    return {
        "id": override.id,
        "tenant_id": str(override.tenant_id),
        "tenant": override.tenant.display_name,
        "feature_flag": override.feature_flag.code,
        "override_state": override.override_state,
        "effective_enabled": effective,
    }


def user_summary(user) -> dict[str, Any]:
    device = getattr(user, "mfa_device", None)
    active_sessions = user.security_sessions.filter(revoked_at__isnull=True).count()
    return {
        "id": str(user.id),
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "is_active": user.is_active,
        "is_staff": user.is_staff,
        "is_platform_admin": user.is_platform_admin,
        "mfa_required": user.mfa_required,
        "mfa_enabled": bool(device and device.enabled and device.confirmed_at),
        "active_sessions": active_sessions,
        "created_at": iso(user.created_at),
        "last_login": iso(user.last_login),
    }


def role_summary(role: Role) -> dict[str, Any]:
    return {
        "id": role.id,
        "code": role.code,
        "name": role.name,
        "scope": role.scope,
        "requires_mfa": role.requires_mfa,
        "permissions": list(role.permissions.order_by("code").values_list("code", flat=True)),
    }


def permission_summary(permission: Permission) -> dict[str, Any]:
    return {"id": permission.id, "code": permission.code, "description": permission.description, "category": permission.code.split(".")[1] if "." in permission.code else "general"}


def support_access_summary(grant: PlatformTenantAccessGrant) -> dict[str, Any]:
    return {
        "id": grant.id,
        "support_user": grant.user.email,
        "tenant": grant.tenant.display_name,
        "tenant_id": str(grant.tenant_id),
        "reason": grant.reason,
        "scope": "tenant",
        "approved_by": grant.approved_by.email,
        "approved_at": iso(grant.created_at),
        "starts_at": iso(grant.created_at),
        "expires_at": iso(grant.expires_at),
        "revoked_at": iso(grant.revoked_at),
        "status": "REVOKED" if grant.revoked_at else "ACTIVE",
    }


def session_summary(session: SecuritySession) -> dict[str, Any]:
    return {
        "id": str(session.id),
        "user": session.user.email,
        "tenant": session.tenant.display_name if session.tenant else "",
        "created_at": iso(session.created_at),
        "last_seen_at": iso(session.last_seen_at),
        "expires_at": iso(session.expires_at),
        "ip_address": str(session.ip_address or ""),
        "device_summary": session.user_agent[:120],
        "status": "REVOKED" if session.revoked_at else "ACTIVE",
    }


def audit_summary(event: AuditEvent) -> dict[str, Any]:
    return {
        "event_id": str(event.event_id),
        "timestamp": iso(event.timestamp),
        "request_id": event.request_id,
        "actor_id": str(event.global_user_id) if event.global_user_id else "",
        "tenant_id": str(event.tenant_id) if event.tenant_id else "",
        "action": event.action,
        "resource_type": event.resource_type,
        "resource_id": event.resource_id,
        "result": event.result,
        "failure_reason": event.failure_reason,
        "source_ip": str(event.source_ip or ""),
        "user_agent": event.user_agent[:120],
    }


def backup_policy_summary(policy: BackupPolicy | None, tenant: Tenant) -> dict[str, Any]:
    return {
        "tenant_id": str(tenant.id),
        "tenant": tenant.display_name,
        "provider": policy.provider if policy else "NOT_CONFIGURED",
        "retention_days": policy.retention_days if policy else 0,
        "region": policy.region if policy else tenant.region,
        "enabled": policy.enabled if policy else False,
    }


def backup_record_summary(record: BackupRecord) -> dict[str, Any]:
    return {
        "id": str(record.id),
        "tenant_id": str(record.tenant_id),
        "tenant": record.tenant.display_name,
        "provider": record.provider,
        "region": record.region,
        "status": record.status,
        "started_at": iso(record.started_at),
        "finished_at": iso(record.finished_at),
        "size_bytes": record.size_bytes,
        "safe_error_summary": record.safe_error_summary,
    }


def restore_request_summary(request: RestoreRequest) -> dict[str, Any]:
    return {
        "id": str(request.id),
        "tenant_id": str(request.tenant_id),
        "tenant": request.tenant.display_name,
        "backup_id": str(request.backup_id) if request.backup_id else "",
        "reason": request.reason,
        "requested_by": request.requested_by.email,
        "approved_by": request.approved_by.email if request.approved_by else "",
        "status": request.status,
        "requested_at": iso(request.requested_at),
        "approved_at": iso(request.approved_at),
        "safe_error_summary": request.safe_error_summary,
    }


def setting_summary(setting: PlatformSetting) -> dict[str, Any]:
    return {"key": setting.key, "value": setting.value, "description": setting.description, "updated_at": iso(setting.updated_at)}


def notification_summary(notification: OwnerNotification) -> dict[str, Any]:
    return {
        "id": str(notification.id),
        "notification_type": notification.notification_type,
        "title": notification.title,
        "message": notification.message,
        "source_type": notification.source_type,
        "source_id": notification.source_id,
        "read": bool(notification.read_at),
        "read_at": iso(notification.read_at),
        "created_at": iso(notification.created_at),
    }
