from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from django.utils import timezone

from control.api.access import ensure_default_roles
from control.models import Tenant, TenantDatabase, TenantDomain, TenantMembership, TenantModule
from identity.authorization import has_permission, has_platform_tenant_access, has_warehouse_access
from identity.models import MembershipRole, Permission, PlatformTenantAccessGrant, PlatformUserRole, Role, RolePermission, SecuritySession, WarehouseAssignment


def _api_login(client: Client, email: str, password: str):
    return client.post(
        "/api/v1/auth/login/",
        {"email": email, "password": password},
        content_type="application/json",
    )


def _tenant(code: str = "alpha") -> Tenant:
    tenant = Tenant.objects.create(tenant_code=code, display_name=f"Tenant {code.title()}", status=Tenant.Status.ACTIVE)
    TenantDomain.objects.create(tenant=tenant, hostname=f"{code}.localhost", verified=True, is_primary=True)
    TenantDatabase.objects.create(
        tenant=tenant,
        database_alias=f"tenant_{code}",
        database_host_reference="local-postgres",
        database_name=f"lattice_{code}",
        runtime_role_name=f"lattice_{code}_app",
        secret_reference=f"env:TENANT_{code.upper()}_DB_PASSWORD",
        provisioning_status=TenantDatabase.ProvisioningStatus.READY,
    )
    return tenant


@pytest.mark.django_db
def test_permission_allowed_and_denied_by_membership_role():
    user = get_user_model().objects.create_user(email="operator@example.test")
    tenant = _tenant()
    membership = TenantMembership.objects.create(user=user, tenant=tenant, status=TenantMembership.Status.ACTIVE)
    permission = Permission.objects.create(code="warehouse.view")
    role = Role.objects.create(code="VIEWER", name="Viewer", scope=Role.Scope.TENANT)
    RolePermission.objects.create(role=role, permission=permission)
    MembershipRole.objects.create(membership=membership, role=role)

    assert has_permission(user, tenant, "warehouse.view")
    assert not has_permission(user, tenant, "warehouse.edit")


@pytest.mark.django_db
def test_inactive_membership_and_cross_tenant_role_cannot_authorize():
    user = get_user_model().objects.create_user(email="operator@example.test")
    alpha = _tenant("alpha")
    beta = _tenant("beta")
    membership = TenantMembership.objects.create(user=user, tenant=alpha, status=TenantMembership.Status.SUSPENDED)
    permission = Permission.objects.create(code="roles.manage")
    role = Role.objects.create(code="SECURITY_ADMIN", name="Security Admin", scope=Role.Scope.TENANT)
    RolePermission.objects.create(role=role, permission=permission)
    MembershipRole.objects.create(membership=membership, role=role)

    assert not has_permission(user, alpha, "roles.manage")
    assert not has_permission(user, beta, "roles.manage")


@pytest.mark.django_db
def test_module_disabled_blocks_permission():
    user = get_user_model().objects.create_user(email="operator@example.test")
    tenant = _tenant()
    membership = TenantMembership.objects.create(user=user, tenant=tenant, status=TenantMembership.Status.ACTIVE)
    permission = Permission.objects.create(code="inventory.view")
    role = Role.objects.create(code="OPERATOR", name="Operator", scope=Role.Scope.TENANT)
    RolePermission.objects.create(role=role, permission=permission)
    MembershipRole.objects.create(membership=membership, role=role)
    TenantModule.objects.create(tenant=tenant, module_code="inventory", enabled=False)

    assert not has_permission(user, tenant, "inventory.view", module_code="inventory")


@pytest.mark.django_db
def test_warehouse_scope_allowed_and_denied():
    user = get_user_model().objects.create_user(email="operator@example.test")
    tenant = _tenant()
    membership = TenantMembership.objects.create(user=user, tenant=tenant, status=TenantMembership.Status.ACTIVE)
    WarehouseAssignment.objects.create(membership=membership, warehouse_code="WH001")

    assert has_warehouse_access(user, tenant, "WH001")
    assert not has_warehouse_access(user, tenant, "WH002")


@pytest.mark.django_db
def test_platform_support_has_no_hidden_tenant_data_bypass():
    support = get_user_model().objects.create_user(email="support@example.test", is_staff=True)
    tenant = _tenant()

    assert not has_platform_tenant_access(support, tenant)


@pytest.mark.django_db
def test_platform_support_access_requires_active_time_limited_grant():
    support = get_user_model().objects.create_user(email="support@example.test", is_staff=True)
    approver = get_user_model().objects.create_user(email="security@example.test", is_staff=True, is_platform_admin=True)
    tenant = _tenant()
    PlatformTenantAccessGrant.objects.create(
        user=support,
        tenant=tenant,
        approved_by=approver,
        reason="support investigation",
        expires_at=timezone.now() + timezone.timedelta(minutes=30),
    )

    assert has_platform_tenant_access(support, tenant)


@pytest.mark.django_db
def test_owner_dashboard_owner_read_includes_unique_license_numbers():
    _tenant("alpha")
    _tenant("beta")
    ensure_default_roles()
    client = Client()
    owner = get_user_model().objects.create_user(email="owner-dashboard@example.test", password="StrongerPass123!", is_staff=True, is_platform_admin=False)
    PlatformUserRole.objects.create(user=owner, role=Role.objects.get(code="PLATFORM_ADMIN"))
    assert _api_login(client, owner.email, "StrongerPass123!").status_code == 200
    assert SecuritySession.objects.filter(user=owner, revoked_at__isnull=True).exists()

    response = client.get("/api/v1/control/owner/dashboard/")

    assert response.status_code == 200
    payload = response.json()
    licenses = [client["license_number"] for client in payload["clients"]]
    assert len(licenses) == len(set(licenses))


@pytest.mark.django_db
def test_owner_dashboard_denies_anonymous_production_access():
    response = Client().get("/api/v1/control/owner/dashboard/")

    assert response.status_code in {401, 403}
