from __future__ import annotations

from control.models import Tenant, TenantMembership, TenantModule
from identity.models import PlatformTenantAccessGrant


def active_membership(user, tenant: Tenant) -> TenantMembership | None:
    if not getattr(user, "is_authenticated", False):
        return None
    return (
        TenantMembership.objects.filter(user=user, tenant=tenant, status=TenantMembership.Status.ACTIVE)
        .select_related("tenant")
        .first()
    )


def has_permission(user, tenant: Tenant, permission_code: str, *, module_code: str | None = None) -> bool:
    membership = active_membership(user, tenant)
    if membership is None or tenant.status != Tenant.Status.ACTIVE:
        return False
    if module_code and not TenantModule.objects.filter(tenant=tenant, module_code=module_code, enabled=True).exists():
        return False
    return membership.role_assignments.filter(role__permissions__code=permission_code).exists()


def has_warehouse_access(user, tenant: Tenant, warehouse_code: str) -> bool:
    membership = active_membership(user, tenant)
    if membership is None:
        return False
    return membership.warehouse_assignments.filter(warehouse_code=warehouse_code, is_active=True).exists()


def has_platform_tenant_access(user, tenant: Tenant, *, at_time=None) -> bool:
    if not getattr(user, "is_authenticated", False):
        return False
    from django.utils import timezone

    now = at_time or timezone.now()
    return PlatformTenantAccessGrant.objects.filter(
        user=user,
        tenant=tenant,
        expires_at__gt=now,
        revoked_at__isnull=True,
    ).exists()
