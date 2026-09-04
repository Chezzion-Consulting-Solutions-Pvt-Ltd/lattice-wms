from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import Client
from django.utils import timezone

from audit.models import AuditEvent
from control.api.access import ensure_default_roles
from control.models import BackupPolicy, BackupRecord, FeatureFlag, License, ModuleDefinition, OwnerNotification, Plan, RestoreRequest, Subscription, Tenant, TenantAdminInvitation, TenantConfiguration, TenantDatabase, TenantDomain, TenantFeatureFlag, TenantMembership, TenantModule, TenantModuleHistory
from identity.models import MembershipRole, PasswordResetToken, Permission, PlatformTenantAccessGrant, PlatformUserRole, Role, RolePermission, SecuritySession
from tenancy.exceptions import TenantResolutionError
from tenancy.resolver import TenantResolver


def api_login(client: Client, email: str, password: str):
    return client.post(
        "/api/v1/auth/login/",
        {"email": email, "password": password},
        content_type="application/json",
    )


def owner_client() -> tuple[Client, object]:
    cache.clear()
    client = Client()
    ensure_default_roles()
    user = get_user_model().objects.create_user(email=f"owner-{uuid.uuid4().hex}@example.test", password="StrongerPass123!", is_staff=True, is_platform_admin=False)
    PlatformUserRole.objects.create(user=user, role=Role.objects.get(code="PLATFORM_ADMIN"))
    assert api_login(client, user.email, "StrongerPass123!").status_code == 200
    assert SecuritySession.objects.filter(user=user, revoked_at__isnull=True).exists()
    return client, user


def owner_client_with_permissions(permission_codes: list[str], *, active_role: bool = True) -> tuple[Client, object]:
    cache.clear()
    client = Client()
    user = get_user_model().objects.create_user(
        email=f"limited-owner-{uuid.uuid4().hex}@example.test",
        password="StrongerPass123!",
        is_staff=True,
        is_platform_admin=False,
    )
    role = Role.objects.create(
        code=f"PLATFORM_TEST_{uuid.uuid4().hex[:12].upper()}",
        name="Platform Test Role",
        scope=Role.Scope.PLATFORM,
        is_active=active_role,
    )
    for code in permission_codes:
        permission, _ = Permission.objects.get_or_create(code=code)
        RolePermission.objects.create(role=role, permission=permission)
    PlatformUserRole.objects.create(user=user, role=role)
    assert api_login(client, user.email, "StrongerPass123!").status_code == 200
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


def test_owner_dashboard_denies_staff_without_required_platform_permission(db):
    client = Client()
    user = get_user_model().objects.create_user(
        email="staff-no-owner-permission@example.test",
        password="StrongerPass123!",
        is_staff=True,
        is_platform_admin=False,
    )
    assert api_login(client, user.email, "StrongerPass123!").status_code == 200

    response = client.get("/api/v1/control/owner/dashboard/")

    assert response.status_code == 403


@patch("control.views._service_health", side_effect=service_health)
def test_owner_dashboard_allows_active_role_with_required_permission(_health, db):
    client, _owner = owner_client_with_permissions(["platform.dashboard.view"])

    response = client.get("/api/v1/control/owner/dashboard/")

    assert response.status_code == 200


def test_owner_dashboard_denies_inactive_platform_role(db):
    client, _owner = owner_client_with_permissions(["platform.dashboard.view"], active_role=False)

    response = client.get("/api/v1/control/owner/dashboard/")

    assert response.status_code == 403


def test_owner_plan_write_requires_manage_permission(db):
    client, _owner = owner_client_with_permissions(["platform.plans.view"])

    list_response = client.get("/api/v1/control/owner/plans/")
    create_response = client.post("/api/v1/control/owner/plans/", {"code": "blocked", "name": "Blocked"}, content_type="application/json")

    assert list_response.status_code == 200
    assert create_response.status_code == 403


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

    activated = client.post(f"/api/v1/control/owner/tenants/{tenant_id}/activate/", {"reason": "initial activation"}, content_type="application/json")
    assert activated.status_code == 200
    assert activated.json()["tenant"]["status"] == Tenant.Status.ACTIVE

    suspended = client.post(f"/api/v1/control/owner/tenants/{tenant_id}/suspend/", {"reason": "billing issue"}, content_type="application/json")
    assert suspended.status_code == 200
    assert suspended.json()["tenant"]["status"] == Tenant.Status.SUSPENDED

    actions = list(AuditEvent.objects.filter(global_user_id=owner.id).values_list("action", flat=True))
    assert "TENANT_CREATED" in actions
    assert "TENANT_UPDATED" in actions
    assert "TENANT_ACTIVATED" in actions
    assert "TENANT_SUSPENDED" in actions


def test_owner_tenant_suspend_requires_reason(db):
    client, _owner = owner_client()
    tenant = Tenant.objects.create(tenant_code="needs-reason", display_name="Needs Reason", status=Tenant.Status.ACTIVE)

    response = client.post(f"/api/v1/control/owner/tenants/{tenant.id}/suspend/")

    assert response.status_code == 400
    tenant.refresh_from_db()
    assert tenant.status == Tenant.Status.ACTIVE


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


def test_owner_tenant_related_tabs_return_control_plane_resources_without_secrets(db):
    client, _owner = owner_client()
    tenant = create_tenant("related")
    plan = Plan.objects.create(code="related-plan", name="Related Plan")
    Subscription.objects.create(tenant=tenant, plan=plan, starts_at=timezone.now())
    License.objects.create(tenant=tenant, plan=plan)
    TenantDomain.objects.create(tenant=tenant, hostname="related.localhost", verified=True, is_active=True, is_primary=True)
    TenantModule.objects.create(tenant=tenant, module_code="inventory")
    feature = FeatureFlag.objects.create(code="related-feature", name="Related Feature")
    TenantFeatureFlag.objects.create(tenant=tenant, feature_flag=feature, override_state=TenantFeatureFlag.OverrideState.ENABLED)
    support_user = get_user_model().objects.create_user(email="related-support@example.test", password="StrongerPass123!", is_staff=True)
    PlatformTenantAccessGrant.objects.create(user=support_user, tenant=tenant, approved_by=_owner, reason="support", expires_at=timezone.now() + timezone.timedelta(hours=1))
    BackupPolicy.objects.create(tenant=tenant, provider="LOCAL_METADATA", enabled=True, region="us-east-1")
    BackupRecord.objects.create(tenant=tenant, provider="LOCAL_METADATA", status=BackupRecord.Status.HEALTHY, started_at=timezone.now(), finished_at=timezone.now())
    RestoreRequest.objects.create(tenant=tenant, requested_by=_owner, reason="validation")

    response = client.get(f"/api/v1/control/owner/tenants/{tenant.id}/related/")

    assert response.status_code == 200
    payload = response.json()
    assert payload["tabs"]["subscription"]["plan"] == "Related Plan"
    assert payload["tabs"]["license"]["tenant_code"] == "related"
    assert payload["tabs"]["domains"][0]["hostname"] == "related.localhost"
    assert payload["tabs"]["modules"][0]["module_code"] == "inventory"
    assert payload["tabs"]["feature_flags"][0]["feature_flag"] == "related-feature"
    assert payload["tabs"]["support_access"][0]["support_user"] == "related-support@example.test"
    assert payload["tabs"]["backups"]["policy"]["provider"] == "LOCAL_METADATA"
    assert payload["tabs"]["restore_requests"][0]["reason"] == "validation"
    body = response.content.decode()
    assert '"secret_reference":' not in body
    assert "TENANT_RELATED_PASSWORD" not in body


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


@patch("control.api.infrastructure.call_command")
def test_owner_migration_orchestration_runs_trusted_tenant_command(_call_command, db):
    client, owner = owner_client()
    tenant = create_tenant("migrate", migration_version="")

    response = client.post("/api/v1/control/owner/infrastructure/migrations/", {"tenant_id": str(tenant.id)}, content_type="application/json")

    assert response.status_code == 200
    _call_command.assert_called_once()
    tenant.database.refresh_from_db()
    assert tenant.database.migration_version.startswith("warehouse.")
    assert tenant.database.safe_error_summary == ""
    assert AuditEvent.objects.filter(global_user_id=owner.id, action="TENANT_MIGRATION_RUN", resource_id=str(tenant.database.id)).exists()


@patch("control.api.infrastructure.call_command", side_effect=RuntimeError("database host leaked.example"))
def test_owner_migration_orchestration_failure_is_safe(_call_command, db):
    client, owner = owner_client()
    tenant = create_tenant("migfail", migration_version="")

    response = client.post("/api/v1/control/owner/infrastructure/migrations/", {"tenant_id": str(tenant.id)}, content_type="application/json")

    assert response.status_code == 500
    tenant.database.refresh_from_db()
    assert tenant.database.safe_error_summary == "Tenant migration orchestration failed."
    assert "leaked.example" not in response.content.decode()
    assert OwnerNotification.objects.filter(notification_type=OwnerNotification.NotificationType.MIGRATION_FAILED, source_id=str(tenant.database.id)).exists()
    audit = AuditEvent.objects.get(global_user_id=owner.id, action="TENANT_MIGRATION_FAILED", resource_id=str(tenant.database.id))
    assert "leaked.example" not in str(audit.after_summary)
    assert audit.result == AuditEvent.Result.FAILURE


def test_owner_backup_without_provider_fails_closed(db):
    client, owner = owner_client()
    tenant = create_tenant("nobackup")

    response = client.post("/api/v1/control/owner/infrastructure/backups/", {"tenant_id": str(tenant.id)}, content_type="application/json")

    assert response.status_code == 409
    record = BackupRecord.objects.get(tenant=tenant)
    assert record.status == BackupRecord.Status.NOT_CONFIGURED
    assert AuditEvent.objects.filter(global_user_id=owner.id, action="BACKUP_SKIPPED", resource_id=str(record.id), result=AuditEvent.Result.FAILURE).exists()


def test_owner_local_metadata_backup_and_restore_execution(db):
    client, owner = owner_client()
    tenant = create_tenant("backupok")
    BackupPolicy.objects.create(tenant=tenant, provider="LOCAL_METADATA", retention_days=7, region="us-east-1", enabled=True)

    backup_response = client.post("/api/v1/control/owner/infrastructure/backups/", {"tenant_id": str(tenant.id)}, content_type="application/json")

    assert backup_response.status_code == 201
    backup_id = backup_response.json()["backup"]["id"]
    backup = BackupRecord.objects.get(id=backup_id)
    assert backup.status == BackupRecord.Status.HEALTHY
    assert backup.restore_point_reference.startswith("metadata:")

    restore_response = client.post(
        "/api/v1/control/owner/infrastructure/restore/",
        {"tenant_id": str(tenant.id), "backup_id": backup_id, "reason": "restore drill"},
        content_type="application/json",
    )
    assert restore_response.status_code == 201
    restore_id = restore_response.json()["restore_request"]["id"]
    approved = client.post(f"/api/v1/control/owner/infrastructure/restore/{restore_id}/approve/")
    executed = client.post(f"/api/v1/control/owner/infrastructure/restore/{restore_id}/execute/")

    assert approved.status_code == 200
    assert executed.status_code == 200
    assert executed.json()["restore_request"]["status"] == RestoreRequest.Status.COMPLETED
    actions = set(AuditEvent.objects.filter(global_user_id=owner.id).values_list("action", flat=True))
    assert {"BACKUP_CREATED", "RESTORE_REQUESTED", "RESTORE_APPROVED", "RESTORE_COMPLETED"}.issubset(actions)


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


def test_owner_domain_management_and_resolver_gate(db):
    client, owner = owner_client()
    tenant = create_tenant("domainco")

    created = client.post(
        f"/api/v1/control/owner/tenants/{tenant.id}/domains/",
        {"hostname": "DomainCo.Localhost:5173", "verification_method": TenantDomain.VerificationMethod.LOCAL_DEVELOPMENT},
        content_type="application/json",
    )

    assert created.status_code == 201
    domain_payload = created.json()["domain"]
    assert domain_payload["hostname"] == "domainco.localhost"
    assert domain_payload["verified"] is False
    assert domain_payload["is_active"] is False

    class Request:
        GET = {}
        META = {}

        def get_host(self):
            return "domainco.localhost"

    with pytest.raises(TenantResolutionError):
        TenantResolver().resolve_request(Request())

    domain_id = domain_payload["id"]
    verified = client.post(f"/api/v1/control/owner/tenants/{tenant.id}/domains/{domain_id}/verify-development/")
    assert verified.status_code == 200
    activated = client.post(f"/api/v1/control/owner/tenants/{tenant.id}/domains/{domain_id}/activate/")
    assert activated.status_code == 200
    primary = client.post(f"/api/v1/control/owner/tenants/{tenant.id}/domains/{domain_id}/make-primary/")
    assert primary.status_code == 200
    assert primary.json()["domain"]["is_primary"] is True

    resolved = TenantResolver().resolve_request(Request())
    assert resolved.tenant == tenant

    actions = list(AuditEvent.objects.filter(global_user_id=owner.id).values_list("action", flat=True))
    assert "TENANT_DOMAIN_CREATED" in actions
    assert "TENANT_DOMAIN_VERIFIED" in actions
    assert "TENANT_DOMAIN_ACTIVATED" in actions


@patch("control.api.provisioning.call_command")
@patch("control.api.provisioning.register_tenant_database", return_value="tenant_provisioned")
@patch("control.api.provisioning.execute_tenant_database_plan")
def test_owner_tenant_provisioning_workflow_marks_ready(_execute, _register, _migrate, db, monkeypatch):
    monkeypatch.setenv("TENANT_PROVISIONED_DB_PASSWORD", "local-provisioned-password")
    client, owner = owner_client()

    response = client.post(
        "/api/v1/control/owner/tenants/provision/",
        {
            "tenant_code": "provisioned",
            "display_name": "Provisioned Tenant",
            "domain": "provisioned.localhost",
            "secret_reference": "env:TENANT_PROVISIONED_DB_PASSWORD",
            "admin_email": "admin@provisioned.test",
            "admin_first_name": "Tenant",
            "admin_last_name": "Admin",
        },
        content_type="application/json",
    )

    assert response.status_code == 201
    body = response.content.decode()
    assert "local-provisioned-password" not in body
    assert "token_hash" not in body
    tenant = Tenant.objects.get(tenant_code="provisioned")
    assert tenant.status == Tenant.Status.ACTIVE
    assert tenant.database.provisioning_status == TenantDatabase.ProvisioningStatus.READY
    assert tenant.database.provisioning_step == TenantDatabase.ProvisioningStep.READY
    assert tenant.database.health_status == TenantDatabase.HealthStatus.HEALTHY
    assert tenant.domains.get().verified is True
    assert TenantConfiguration.objects.get(tenant=tenant).status == TenantConfiguration.Status.READY
    assert TenantModule.objects.filter(tenant=tenant, source=TenantModule.Source.PLAN).count() >= 1
    invitation = TenantAdminInvitation.objects.get(tenant=tenant, email="admin@provisioned.test")
    assert invitation.token_hash
    assert invitation.status == TenantAdminInvitation.Status.PENDING
    membership = TenantMembership.objects.get(tenant=tenant, user=invitation.user)
    assert MembershipRole.objects.filter(membership=membership, role__code="TENANT_ADMIN").exists()
    assert Role.objects.get(code="TENANT_ADMIN").requires_mfa is True
    assert License.objects.filter(tenant=tenant, license_number=tenant.license_number).exists()
    assert AuditEvent.objects.filter(global_user_id=owner.id, action="TENANT_CREATED", resource_id=str(tenant.id)).exists()


@patch("control.api.provisioning.execute_tenant_database_plan", side_effect=RuntimeError("admin unavailable"))
def test_owner_tenant_provisioning_failure_is_persisted_and_safe(_execute, db, monkeypatch):
    monkeypatch.setenv("TENANT_FAILEDPROV_DB_PASSWORD", "local-failed-password")
    client, owner = owner_client()

    response = client.post(
        "/api/v1/control/owner/tenants/provision/",
        {
            "tenant_code": "failedprov",
            "display_name": "Failed Provision",
            "secret_reference": "env:TENANT_FAILEDPROV_DB_PASSWORD",
        },
        content_type="application/json",
    )

    assert response.status_code == 500
    body = response.content.decode()
    assert "local-failed-password" not in body
    tenant = Tenant.objects.get(tenant_code="failedprov")
    assert tenant.database.provisioning_status == TenantDatabase.ProvisioningStatus.FAILED
    assert tenant.database.provisioning_step == TenantDatabase.ProvisioningStep.FAILED
    assert tenant.database.safe_error_summary
    assert OwnerNotification.objects.filter(source_id=str(tenant.id), notification_type=OwnerNotification.NotificationType.TENANT_PROVISIONING_FAILED).exists()
    audit = AuditEvent.objects.get(global_user_id=owner.id, action="TENANT_PROVISIONING_FAILED", resource_id=str(tenant.id))
    assert "local-failed-password" not in str(audit.after_summary)
    assert "local-failed-password" not in audit.failure_reason


@patch("control.api.provisioning.call_command")
@patch("control.api.provisioning.register_tenant_database", return_value="tenant_retryprov")
@patch("control.api.provisioning.execute_tenant_database_plan")
def test_owner_tenant_provisioning_retry_is_idempotent(_execute, _register, _migrate, db, monkeypatch):
    monkeypatch.setenv("TENANT_RETRYPROV_DB_PASSWORD", "local-retry-password")
    client, owner = owner_client()
    tenant = Tenant.objects.create(tenant_code="retryprov", display_name="Retry Provision", status=Tenant.Status.PROVISIONING)
    TenantDatabase.objects.create(
        tenant=tenant,
        database_alias="tenant_retryprov",
        database_host_reference="postgres",
        database_name="lattice_retryprov",
        runtime_role_name="lattice_retryprov_app",
        secret_reference="env:TENANT_RETRYPROV_DB_PASSWORD",
        sslmode="prefer",
        provisioning_status=TenantDatabase.ProvisioningStatus.FAILED,
        provisioning_step=TenantDatabase.ProvisioningStep.FAILED,
        health_status=TenantDatabase.HealthStatus.UNAVAILABLE,
        safe_error_summary="previous safe failure",
    )
    TenantAdminInvitation.objects.create(
        tenant=tenant,
        user=owner,
        email=owner.email,
        token_hash=TenantAdminInvitation.hash_token("existing-token"),
        expires_at=timezone.now() + timezone.timedelta(hours=12),
    )

    response = client.post(f"/api/v1/control/owner/tenants/{tenant.id}/provision/retry/")

    assert response.status_code == 200
    tenant.refresh_from_db()
    tenant.database.refresh_from_db()
    assert tenant.status == Tenant.Status.ACTIVE
    assert tenant.database.provisioning_status == TenantDatabase.ProvisioningStatus.READY
    assert tenant.database.safe_error_summary == ""
    assert TenantAdminInvitation.objects.filter(tenant=tenant, email=owner.email, status=TenantAdminInvitation.Status.PENDING).count() == 1
    assert AuditEvent.objects.filter(global_user_id=owner.id, action="TENANT_PROVISIONING_RETRIED", resource_id=str(tenant.id)).exists()


def test_owner_plan_full_crud_lifecycle_and_audit(db):
    client, owner = owner_client()

    created = client.post(
        "/api/v1/control/owner/plans/",
        {
            "code": "growth",
            "name": "Growth",
            "description": "Growth plan",
            "billing_interval": Plan.BillingInterval.MONTHLY,
            "currency": "USD",
            "price_metadata": {"monthly": "199.00"},
            "user_limit": 25,
            "warehouse_limit": 4,
            "storage_limit": 100,
            "api_limit": 10000,
            "included_modules": ["masters", "inventory"],
            "support_tier": "standard",
        },
        content_type="application/json",
    )

    assert created.status_code == 201
    plan_id = created.json()["plan"]["id"]
    detail = client.get(f"/api/v1/control/owner/plans/{plan_id}/")
    assert detail.status_code == 200
    assert detail.json()["plan"]["currency"] == "USD"
    updated = client.patch(
        f"/api/v1/control/owner/plans/{plan_id}/",
        {"name": "Growth Plus", "included_modules": ["masters", "inbound", "inventory"], "price_metadata": {"monthly": "249.00"}},
        content_type="application/json",
    )
    assert updated.status_code == 200
    assert updated.json()["plan"]["name"] == "Growth Plus"
    deactivated = client.post(f"/api/v1/control/owner/plans/{plan_id}/deactivate/")
    assert deactivated.status_code == 200
    assert deactivated.json()["plan"]["is_active"] is False
    activated = client.post(f"/api/v1/control/owner/plans/{plan_id}/activate/")
    assert activated.status_code == 200
    assert activated.json()["plan"]["is_active"] is True
    duplicate = client.post("/api/v1/control/owner/plans/", {"code": "growth", "name": "Duplicate"}, content_type="application/json")
    assert duplicate.status_code == 409
    actions = set(AuditEvent.objects.filter(global_user_id=owner.id, resource_type="Plan").values_list("action", flat=True))
    assert {"PLAN_CREATED", "PLAN_UPDATED", "PLAN_ACTIVATED", "PLAN_DEACTIVATED", "PLAN_MODULES_CHANGED", "PLAN_FEATURES_CHANGED"} - actions == {"PLAN_FEATURES_CHANGED"}


def test_owner_plan_validation_and_referenced_delete_protection(db):
    client, _owner = owner_client()
    plan = Plan.objects.create(code="locked", name="Locked")
    tenant = create_tenant("lockedsub")
    Subscription.objects.create(tenant=tenant, plan=plan, starts_at=timezone.now())

    invalid_limit = client.patch(f"/api/v1/control/owner/plans/{plan.id}/", {"user_limit": -1}, content_type="application/json")
    assert invalid_limit.status_code == 400
    code_change = client.patch(f"/api/v1/control/owner/plans/{plan.id}/", {"code": "renamed"}, content_type="application/json")
    assert code_change.status_code == 400
    deleted = client.delete(f"/api/v1/control/owner/plans/{plan.id}/")
    assert deleted.status_code == 409
    assert Plan.objects.filter(id=plan.id).exists()


def test_owner_subscription_full_crud_lifecycle_and_audit(db):
    client, owner = owner_client()
    tenant = create_tenant("subcrud")
    plan = Plan.objects.create(code="sub-growth", name="Sub Growth")
    new_plan = Plan.objects.create(code="sub-enterprise", name="Sub Enterprise")
    starts_at = timezone.now()

    created = client.post(
        "/api/v1/control/owner/subscriptions/",
        {
            "tenant_id": str(tenant.id),
            "plan_id": plan.id,
            "status": Subscription.Status.TRIAL,
            "starts_at": starts_at.isoformat(),
            "trial_ends_at": (starts_at + timezone.timedelta(days=14)).isoformat(),
            "renewal_at": (starts_at + timezone.timedelta(days=30)).isoformat(),
            "notes": "trial",
            "override_metadata": {"users": 10},
        },
        content_type="application/json",
    )

    assert created.status_code == 201
    subscription_id = created.json()["subscription"]["id"]
    assert client.get(f"/api/v1/control/owner/subscriptions/{subscription_id}/").status_code == 200
    duplicate = client.post("/api/v1/control/owner/subscriptions/", {"tenant_id": str(tenant.id), "plan_id": plan.id}, content_type="application/json")
    assert duplicate.status_code == 409
    updated = client.patch(
        f"/api/v1/control/owner/subscriptions/{subscription_id}/",
        {"plan_id": new_plan.id, "notes": "upgraded", "status": Subscription.Status.ACTIVE},
        content_type="application/json",
    )
    assert updated.status_code == 200
    assert updated.json()["subscription"]["plan_id"] == new_plan.id
    suspended = client.post(f"/api/v1/control/owner/subscriptions/{subscription_id}/suspend/")
    assert suspended.status_code == 200
    assert suspended.json()["subscription"]["status"] == Subscription.Status.SUSPENDED
    cancelled = client.post(f"/api/v1/control/owner/subscriptions/{subscription_id}/cancel/")
    assert cancelled.status_code == 200
    assert cancelled.json()["subscription"]["status"] == Subscription.Status.CANCELLED
    blocked = client.post(f"/api/v1/control/owner/subscriptions/{subscription_id}/activate/")
    assert blocked.status_code == 400
    actions = set(AuditEvent.objects.filter(global_user_id=owner.id, resource_type="Subscription").values_list("action", flat=True))
    assert {"SUBSCRIPTION_CREATED", "SUBSCRIPTION_UPDATED", "SUBSCRIPTION_PLAN_CHANGED", "SUBSCRIPTION_SUSPENDED", "SUBSCRIPTION_CANCELLED"}.issubset(actions)


def test_owner_subscription_validation(db):
    client, _owner = owner_client()
    tenant = create_tenant("subinvalid")
    inactive_plan = Plan.objects.create(code="inactive-sub", name="Inactive Sub", is_active=False)
    active_plan = Plan.objects.create(code="active-sub", name="Active Sub")
    starts_at = timezone.now()

    inactive = client.post("/api/v1/control/owner/subscriptions/", {"tenant_id": str(tenant.id), "plan_id": inactive_plan.id}, content_type="application/json")
    assert inactive.status_code == 400
    invalid_dates = client.post(
        "/api/v1/control/owner/subscriptions/",
        {"tenant_id": str(tenant.id), "plan_id": active_plan.id, "starts_at": starts_at.isoformat(), "trial_ends_at": (starts_at - timezone.timedelta(days=1)).isoformat()},
        content_type="application/json",
    )
    assert invalid_dates.status_code == 400


def test_owner_license_issue_update_and_lifecycle_audit(db):
    client, owner = owner_client()
    tenant = Tenant.objects.create(tenant_code="liccrud", display_name="License CRUD", status=Tenant.Status.ACTIVE)
    plan = Plan.objects.create(code="license-plan", name="License Plan")

    issued = client.post(
        "/api/v1/control/owner/licenses/",
        {"tenant_id": str(tenant.id), "plan_id": plan.id, "metadata": {"seats": 15}},
        content_type="application/json",
    )
    assert issued.status_code == 201
    license_id = issued.json()["license"]["id"]
    detail = client.get(f"/api/v1/control/owner/licenses/{license_id}/")
    assert detail.status_code == 200
    assert detail.json()["license"]["metadata"] == {"seats": 15}
    updated = client.patch(f"/api/v1/control/owner/licenses/{license_id}/", {"metadata": {"seats": 20}}, content_type="application/json")
    assert updated.status_code == 200
    renewed = client.post(f"/api/v1/control/owner/licenses/{license_id}/renew/", {"days": 30}, content_type="application/json")
    assert renewed.status_code == 200
    revoked = client.post(f"/api/v1/control/owner/licenses/{license_id}/revoke/")
    assert revoked.status_code == 200
    assert revoked.json()["license"]["status"] == License.Status.REVOKED
    actions = set(AuditEvent.objects.filter(global_user_id=owner.id, resource_type="License").values_list("action", flat=True))
    assert {"LICENSE_ISSUED", "LICENSE_UPDATED", "LICENSE_RENEWED", "LICENSE_REVOKED"}.issubset(actions)


def test_owner_module_crud_lifecycle_and_tenant_override_audit(db):
    client, owner = owner_client()
    tenant = create_tenant("modulecrud")

    created = client.post(
        "/api/v1/control/owner/modules/",
        {"module_code": "yard", "name": "Yard", "description": "Yard operations", "display_order": 30},
        content_type="application/json",
    )
    assert created.status_code == 201
    module_id = created.json()["module"]["id"]
    assert client.get(f"/api/v1/control/owner/modules/{module_id}/").status_code == 200
    updated = client.patch(f"/api/v1/control/owner/modules/{module_id}/", {"name": "Yard Management"}, content_type="application/json")
    assert updated.status_code == 200
    deactivated = client.post(f"/api/v1/control/owner/modules/{module_id}/deactivate/")
    assert deactivated.status_code == 200
    assert deactivated.json()["module"]["active"] is False
    activated = client.post(f"/api/v1/control/owner/modules/{module_id}/activate/")
    assert activated.status_code == 200
    override = client.post(f"/api/v1/control/owner/tenants/{tenant.id}/modules/", {"module_code": "yard", "enabled": False}, content_type="application/json")
    assert override.status_code == 201
    assert TenantModule.objects.get(tenant=tenant, module_code="yard").override_state == TenantModule.OverrideState.DISABLED
    assert TenantModuleHistory.objects.filter(tenant=tenant, module_code="yard", changed_by=owner).exists()
    actions = set(AuditEvent.objects.filter(global_user_id=owner.id).values_list("action", flat=True))
    assert {"MODULE_CREATED", "MODULE_UPDATED", "MODULE_ACTIVATED", "MODULE_DEACTIVATED", "MODULE_DISABLED"}.issubset(actions)


def test_owner_feature_flag_crud_lifecycle_and_override_audit(db):
    client, owner = owner_client()
    tenant = create_tenant("featurecrud")

    created = client.post(
        "/api/v1/control/owner/features/",
        {"code": "wave-picking", "name": "Wave Picking", "description": "Wave picking controls", "enabled_by_default": False},
        content_type="application/json",
    )
    assert created.status_code == 201
    feature_id = created.json()["feature"]["id"]
    assert client.get(f"/api/v1/control/owner/features/{feature_id}/").status_code == 200
    updated = client.patch(f"/api/v1/control/owner/features/{feature_id}/", {"enabled_by_default": True}, content_type="application/json")
    assert updated.status_code == 200
    deactivated = client.post(f"/api/v1/control/owner/features/{feature_id}/deactivate/")
    assert deactivated.status_code == 200
    assert deactivated.json()["feature"]["active"] is False
    activated = client.post(f"/api/v1/control/owner/features/{feature_id}/activate/")
    assert activated.status_code == 200
    override = client.post(f"/api/v1/control/owner/tenants/{tenant.id}/features/", {"feature_id": feature_id, "override_state": TenantFeatureFlag.OverrideState.ENABLED}, content_type="application/json")
    assert override.status_code == 201
    assert FeatureFlag.objects.get(id=feature_id).active is True
    assert TenantFeatureFlag.objects.get(tenant=tenant, feature_flag_id=feature_id).override_state == TenantFeatureFlag.OverrideState.ENABLED
    actions = set(AuditEvent.objects.filter(global_user_id=owner.id).values_list("action", flat=True))
    assert {"FEATURE_FLAG_CREATED", "FEATURE_FLAG_UPDATED", "FEATURE_FLAG_ACTIVATED", "FEATURE_FLAG_DEACTIVATED"}.issubset(actions)


def test_owner_platform_user_lifecycle_role_assignment_and_password_reset(db):
    client, owner = owner_client()
    role = Role.objects.get(code="PLATFORM_SECURITY_ADMIN")

    created = client.post(
        "/api/v1/control/owner/users/",
        {"email": "security-admin@example.test", "first_name": "Security", "mfa_required": True},
        content_type="application/json",
    )
    assert created.status_code == 201
    user_id = created.json()["user"]["id"]
    assigned = client.post(f"/api/v1/control/owner/users/{user_id}/roles/", {"role_id": role.id}, content_type="application/json")
    assert assigned.status_code == 200
    user = get_user_model().objects.get(id=user_id)
    assert PlatformUserRole.objects.filter(user=user, role=role).exists()
    reset = client.post(f"/api/v1/control/owner/users/{user_id}/password-reset/")
    assert reset.status_code == 200
    assert PasswordResetToken.objects.filter(user=user, used_at__isnull=True).exists()
    disabled = client.post(f"/api/v1/control/owner/users/{user_id}/disable/")
    assert disabled.status_code == 200
    user.refresh_from_db()
    assert user.is_active is False
    activated = client.post(f"/api/v1/control/owner/users/{user_id}/activate/")
    assert activated.status_code == 200
    actions = set(AuditEvent.objects.filter(global_user_id=owner.id, resource_type="GlobalUser").values_list("action", flat=True))
    assert {"PLATFORM_USER_CREATED", "PLATFORM_USER_ROLE_CHANGED", "PASSWORD_RESET_REQUESTED", "PLATFORM_USER_DISABLED", "PLATFORM_USER_ACTIVATED"}.issubset(actions)


def test_owner_platform_user_protects_last_platform_admin(db):
    client, _owner = owner_client()
    protected_admin = get_user_model().objects.create_user(
        email="protected-admin@example.test",
        password="StrongerPass123!",
        is_active=True,
        is_staff=True,
        is_platform_admin=True,
    )

    response = client.post(f"/api/v1/control/owner/users/{protected_admin.id}/disable/")

    assert response.status_code == 409
    protected_admin.refresh_from_db()
    assert protected_admin.is_active is True


def test_owner_role_lifecycle_and_permission_assignment(db):
    client, owner = owner_client()

    created = client.post(
        "/api/v1/control/owner/roles/",
        {"code": "PLATFORM_REPORTING", "name": "Platform Reporting", "permissions": ["platform.reports.view"]},
        content_type="application/json",
    )
    assert created.status_code == 201
    role_id = created.json()["role"]["id"]
    assert client.get(f"/api/v1/control/owner/roles/{role_id}/").status_code == 200
    updated = client.patch(f"/api/v1/control/owner/roles/{role_id}/", {"permissions": ["platform.reports.view", "platform.reports.export"]}, content_type="application/json")
    assert updated.status_code == 200
    assert "platform.reports.export" in updated.json()["role"]["permissions"]
    disabled = client.post(f"/api/v1/control/owner/roles/{role_id}/disable/")
    assert disabled.status_code == 200
    assert disabled.json()["role"]["is_active"] is False
    actions = set(AuditEvent.objects.filter(global_user_id=owner.id, resource_type="Role").values_list("action", flat=True))
    assert {"ROLE_CREATED", "PERMISSION_ASSIGNED", "ROLE_DISABLED"}.issubset(actions)


def test_owner_support_access_request_approve_deny_revoke_and_expiry(db):
    client, owner = owner_client()
    support_user = get_user_model().objects.create_user(email="support-flow@example.test", password="StrongerPass123!", is_staff=True)
    tenant = create_tenant("supportflow")

    requested = client.post(
        "/api/v1/control/owner/support-access/",
        {"user_id": str(support_user.id), "tenant_id": str(tenant.id), "reason": "investigate ticket", "requested": True, "hours": 2},
        content_type="application/json",
    )
    assert requested.status_code == 201
    grant_id = requested.json()["support_access"]["id"]
    assert requested.json()["support_access"]["status"] == PlatformTenantAccessGrant.Status.REQUESTED
    approved = client.post(f"/api/v1/control/owner/support-access/{grant_id}/approve/")
    assert approved.status_code == 200
    assert approved.json()["support_access"]["status"] == PlatformTenantAccessGrant.Status.ACTIVE
    updated = client.patch(f"/api/v1/control/owner/support-access/{grant_id}/", {"reason": "updated reason"}, content_type="application/json")
    assert updated.status_code == 200
    assert updated.json()["support_access"]["reason"] == "updated reason"
    revoked = client.post(f"/api/v1/control/owner/support-access/{grant_id}/revoke/")
    assert revoked.status_code == 200
    assert revoked.json()["support_access"]["status"] == PlatformTenantAccessGrant.Status.REVOKED

    deny_request = client.post(
        "/api/v1/control/owner/support-access/",
        {"user_id": str(support_user.id), "tenant_id": str(tenant.id), "reason": "not needed", "requested": True},
        content_type="application/json",
    )
    denied = client.post(f"/api/v1/control/owner/support-access/{deny_request.json()['support_access']['id']}/deny/")
    assert denied.status_code == 200
    assert denied.json()["support_access"]["status"] == PlatformTenantAccessGrant.Status.DENIED
    expired = PlatformTenantAccessGrant.objects.create(
        user=support_user,
        tenant=tenant,
        approved_by=owner,
        approved_at=timezone.now() - timezone.timedelta(hours=3),
        starts_at=timezone.now() - timezone.timedelta(hours=3),
        expires_at=timezone.now() - timezone.timedelta(hours=1),
        reason="expired",
        status=PlatformTenantAccessGrant.Status.ACTIVE,
    )
    list_response = client.get("/api/v1/control/owner/support-access/")
    assert list_response.status_code == 200
    expired_payload = next(item for item in list_response.json()["support_access"] if item["id"] == expired.id)
    assert expired_payload["status"] == PlatformTenantAccessGrant.Status.EXPIRED
    actions = set(AuditEvent.objects.filter(global_user_id=owner.id, resource_type="PlatformTenantAccessGrant").values_list("action", flat=True))
    assert {"SUPPORT_ACCESS_REQUESTED", "SUPPORT_ACCESS_APPROVED", "SUPPORT_ACCESS_UPDATED", "SUPPORT_ACCESS_DENIED", "SUPPORT_ACCESS_REVOKED"}.issubset(actions)


def test_owner_report_csv_export_sanitizes_formula_values_and_audits(db):
    client, owner = owner_client()
    Tenant.objects.create(tenant_code="csvsafe", display_name="=SUM(1,1)", status=Tenant.Status.ACTIVE)

    response = client.get("/api/v1/control/owner/reports/", {"type": "tenant-status", "export": "csv"})

    assert response.status_code == 200
    body = response.content.decode()
    assert "'=SUM(1,1)" in body
    assert AuditEvent.objects.filter(global_user_id=owner.id, action="EXPORT_CREATED", resource_type="OwnerReport").exists()
