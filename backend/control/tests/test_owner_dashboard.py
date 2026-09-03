from __future__ import annotations

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client
from django.utils import timezone

from audit.models import AuditEvent
from control.models import Plan, Subscription, Tenant, TenantDatabase
from identity.models import PlatformTenantAccessGrant, SecuritySession


def api_login(client: Client, email: str, password: str):
    return client.post(
        "/api/v1/auth/login/",
        {"email": email, "password": password},
        content_type="application/json",
    )


def owner_client() -> tuple[Client, object]:
    client = Client()
    user = get_user_model().objects.create_user(email="owner@example.test", password="StrongerPass123!", is_staff=True)
    assert api_login(client, user.email, "StrongerPass123!").status_code == 200
    assert SecuritySession.objects.filter(user=user, revoked_at__isnull=True).exists()
    return client, user


def service_health():
    return {
        "backend": {"status": "OK", "detail": "request served"},
        "postgresql": {"status": "OK", "detail": "control database reachable"},
        "redis": {"status": "OK", "detail": "redis ping"},
        "celery": {"status": "OK", "detail": "1 worker(s) responded"},
    }


def create_tenant(code: str, *, status=Tenant.Status.ACTIVE, db_health=TenantDatabase.HealthStatus.HEALTHY, migration_version="0001"):
    tenant = Tenant.objects.create(tenant_code=code, display_name=f"Tenant {code.title()}", status=status, region="us-east-1")
    TenantDatabase.objects.create(
        tenant=tenant,
        database_alias=f"tenant_{code}",
        database_host_reference="postgres",
        database_name=f"lattice_{code}",
        runtime_role_name=f"lattice_{code}_app",
        secret_reference=f"env:TENANT_{code.upper()}_PASSWORD",
        sslmode="prefer",
        migration_version=migration_version,
        provisioning_status=TenantDatabase.ProvisioningStatus.READY,
        health_status=db_health,
    )
    return tenant


def test_owner_dashboard_requires_owner_access(db):
    anonymous = Client().get("/api/v1/control/owner/dashboard/")
    assert anonymous.status_code in {401, 403}

    client = Client()
    user = get_user_model().objects.create_user(email="user@example.test", password="StrongerPass123!")
    assert api_login(client, user.email, "StrongerPass123!").status_code == 200

    response = client.get("/api/v1/control/owner/dashboard/")

    assert response.status_code == 403


@patch("control.views._service_health", side_effect=service_health)
def test_owner_dashboard_returns_real_control_plane_metrics(_health, db):
    active = create_tenant("alpha")
    create_tenant("beta", status=Tenant.Status.SUSPENDED, db_health=TenantDatabase.HealthStatus.DEGRADED, migration_version="")
    plan = Plan.objects.create(code="standard", name="Standard")
    Subscription.objects.create(tenant=active, plan=plan, starts_at=timezone.now(), is_active=True)
    support_user = get_user_model().objects.create_user(email="support@example.test", password="StrongerPass123!", is_staff=True)
    owner, approver = owner_client()
    PlatformTenantAccessGrant.objects.create(
        user=support_user,
        tenant=active,
        approved_by=approver,
        reason="support investigation",
        expires_at=timezone.now() + timezone.timedelta(hours=4),
    )
    AuditEvent.objects.create(request_id="req-1", action="LOGIN_FAILED", resource_type="identity", result=AuditEvent.Result.DENIED)

    response = owner.get("/api/v1/control/owner/dashboard/")
    payload = response.json()

    assert response.status_code == 200
    assert payload["summary"]["total_tenants"] == 2
    assert payload["summary"]["active_tenants"] == 1
    assert payload["summary"]["suspended_tenants"] == 1
    assert payload["summary"]["ready_databases"] == 2
    assert payload["summary"]["healthy_databases"] == 1
    assert payload["summary"]["database_warnings"] == 1
    assert payload["summary"]["migration_warnings"] == 1
    assert payload["summary"]["security_alerts"] == 1
    assert payload["summary"]["active_support_grants"] == 1
    assert payload["tenant_health"][0]["tenant_code"] == "alpha"
    assert payload["tenant_health"][0]["subscription_status"] == "ACTIVE"
    assert payload["tenant_health"][1]["subscription_status"] == "UNASSIGNED"
    assert payload["platform_health"]["redis"]["status"] == "OK"
    assert payload["recent_security_events"][0]["action"] == "LOGIN_FAILED"


@patch("control.views._service_health", side_effect=service_health)
def test_owner_dashboard_never_exposes_secret_references(_health, db):
    create_tenant("alpha")
    client, _owner = owner_client()

    response = client.get("/api/v1/control/owner/dashboard/")

    assert response.status_code == 200
    body = response.content.decode()
    assert "secret_reference" not in body
    assert "TENANT_ALPHA_PASSWORD" not in body
    assert "env:" not in body


def test_owner_tenant_crud_lifecycle_and_audit(db):
    client, owner = owner_client()

    created = client.post(
        "/api/v1/control/owner/tenants/",
        {
            "tenant_code": "gamma",
            "display_name": "Tenant Gamma",
            "legal_name": "Tenant Gamma LLC",
            "region": "us-east-1",
            "timezone": "UTC",
            "subscription_plan": "Standard",
        },
        content_type="application/json",
    )

    assert created.status_code == 201
    payload = created.json()["tenant"]
    assert payload["tenant_code"] == "gamma"
    assert payload["license_number"].startswith("LIC-")
    assert payload["database"]["provisioning_status"] == "MISSING"

    tenant_id = payload["id"]
    updated = client.patch(
        f"/api/v1/control/owner/tenants/{tenant_id}/",
        {"display_name": "Tenant Gamma Updated", "subscription_plan": "Enterprise"},
        content_type="application/json",
    )
    assert updated.status_code == 200
    assert updated.json()["tenant"]["display_name"] == "Tenant Gamma Updated"

    activated = client.post(f"/api/v1/control/owner/tenants/{tenant_id}/activate/")
    assert activated.status_code == 200
    assert activated.json()["tenant"]["status"] == Tenant.Status.ACTIVE

    suspended = client.post(f"/api/v1/control/owner/tenants/{tenant_id}/suspend/")
    assert suspended.status_code == 200
    assert suspended.json()["tenant"]["status"] == Tenant.Status.SUSPENDED

    actions = list(AuditEvent.objects.filter(global_user_id=owner.id).values_list("action", flat=True))
    assert "TENANT_CREATED" in actions
    assert "TENANT_UPDATED" in actions
    assert "TENANT_ACTIVATED" in actions
    assert "TENANT_SUSPENDED" in actions


def test_owner_can_register_tenant_database_without_exposing_secret_reference(db):
    client, owner = owner_client()
    tenant = Tenant.objects.create(tenant_code="delta", display_name="Tenant Delta")

    response = client.put(
        f"/api/v1/control/owner/tenants/{tenant.id}/database/",
        {
            "database_alias": "tenant_delta",
            "database_host_reference": "postgres",
            "port": 5432,
            "database_name": "lattice_delta",
            "runtime_role_name": "lattice_delta_app",
            "secret_reference": "env:TENANT_DELTA_DB_PASSWORD",
            "sslmode": "prefer",
            "migration_version": "0002",
            "provisioning_status": TenantDatabase.ProvisioningStatus.READY,
            "health_status": TenantDatabase.HealthStatus.HEALTHY,
        },
        content_type="application/json",
    )

    assert response.status_code == 200
    payload = response.json()["tenant"]
    assert payload["database"]["alias"] == "tenant_delta"
    assert payload["database"]["host_reference"] == "postgres"
    assert payload["database"]["name"] == "lattice_delta"
    assert payload["database"]["runtime_role"] == "lattice_delta_app"
    assert payload["database"]["provisioning_status"] == TenantDatabase.ProvisioningStatus.READY
    body = response.content.decode()
    assert "secret_reference" not in body
    assert "TENANT_DELTA_DB_PASSWORD" not in body
    audit = AuditEvent.objects.get(global_user_id=owner.id, action="TENANT_DATABASE_CREATE")
    assert audit.after_summary["secret_reference_configured"] is True
    assert "TENANT_DELTA_DB_PASSWORD" not in str(audit.after_summary)


def test_owner_tenant_database_config_rejects_raw_credentials(db):
    client, _owner = owner_client()
    tenant = Tenant.objects.create(tenant_code="epsilon", display_name="Tenant Epsilon")

    response = client.put(
        f"/api/v1/control/owner/tenants/{tenant.id}/database/",
        {
            "database_alias": "tenant_epsilon",
            "database_host_reference": "postgres",
            "database_name": "lattice_epsilon",
            "runtime_role_name": "lattice_epsilon_app",
            "secret_reference": "env:TENANT_EPSILON_DB_PASSWORD",
            "password": "plaintext-password",
        },
        content_type="application/json",
    )

    assert response.status_code == 400
    assert not TenantDatabase.objects.filter(tenant=tenant).exists()


def test_owner_tenant_crud_denies_non_owner(db):
    client = Client()
    user = get_user_model().objects.create_user(email="plain-user@example.test", password="StrongerPass123!")
    assert api_login(client, user.email, "StrongerPass123!").status_code == 200

    response = client.post(
        "/api/v1/control/owner/tenants/",
        {"tenant_code": "blocked", "display_name": "Blocked"},
        content_type="application/json",
    )

    assert response.status_code == 403


def test_owner_tenant_database_config_denies_non_owner(db):
    tenant = Tenant.objects.create(tenant_code="zeta", display_name="Tenant Zeta")
    client = Client()
    user = get_user_model().objects.create_user(email="plain-db-user@example.test", password="StrongerPass123!")
    assert api_login(client, user.email, "StrongerPass123!").status_code == 200

    response = client.put(
        f"/api/v1/control/owner/tenants/{tenant.id}/database/",
        {
            "database_alias": "tenant_zeta",
            "database_host_reference": "postgres",
            "database_name": "lattice_zeta",
            "runtime_role_name": "lattice_zeta_app",
            "secret_reference": "env:TENANT_ZETA_DB_PASSWORD",
        },
        content_type="application/json",
    )

    assert response.status_code == 403
