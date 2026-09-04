from __future__ import annotations

import os
from uuid import uuid4

import pytest
from django.core.cache import cache
from django.contrib.auth import get_user_model
from django.test import Client, override_settings
from django.utils import timezone

from audit.models import AuditEvent
from control.models import Tenant, TenantDatabase, TenantDomain, TenantMembership
from identity.models import MembershipRole, Permission, Role, RolePermission, WarehouseAssignment
from warehouse.models import Bay, WarehouseLog


pytestmark = [
    pytest.mark.skipif(
        os.environ.get("LATTICE_RUN_DB_ISOLATION") != "1",
        reason="requires real local PostgreSQL tenant DBs",
    ),
    pytest.mark.django_db(databases="__all__"),
]


ALL_HIERARCHY_PERMISSIONS = [
    "tenant.dashboard.view",
    "tenant.plants.view",
    "tenant.plants.manage",
    "tenant.warehouses.view",
    "tenant.warehouses.manage",
    "tenant.storage_types.view",
    "tenant.storage_types.manage",
    "tenant.zones.view",
    "tenant.zones.manage",
    "tenant.sections.view",
    "tenant.sections.manage",
    "tenant.bays.view",
    "tenant.bays.manage",
    "tenant.bays.bulk_create",
    "tenant.bays.import",
    "tenant.bays.export",
    "tenant.configuration.view",
    "tenant.configuration.manage",
    "tenant.users.view",
    "tenant.users.manage",
    "tenant.roles.view",
    "tenant.roles.manage",
    "tenant.settings.view",
    "tenant.settings.manage",
    "tenant.warehouse_assignments.view",
    "tenant.warehouse_assignments.manage",
    "masters.categories.view",
    "masters.categories.manage",
    "organization.hierarchy.view",
    "organization.plants.view",
    "organization.plants.manage",
    "organization.warehouses.view",
    "organization.warehouses.manage",
    "organization.zones.view",
    "organization.zones.manage",
    "organization.storage_types.view",
    "organization.storage_types.manage",
    "organization.sections.view",
    "organization.sections.manage",
    "organization.bins.view",
    "organization.bins.manage",
]


@pytest.fixture(autouse=True)
def allow_dynamic_tenant_database_aliases(django_db_blocker):
    with django_db_blocker.unblock():
        yield


@pytest.fixture
def tenant_admin_client(db):
    return _tenant_client("alpha", ALL_HIERARCHY_PERMISSIONS)


def _tenant_client(code: str, permissions: list[str], *, assign_all_warehouses: bool = True):
    tenant = Tenant.objects.create(tenant_code=f"{code}-{uuid4().hex[:8]}", display_name=f"Tenant {code.title()}", status=Tenant.Status.ACTIVE)
    TenantDomain.objects.create(
        tenant=tenant,
        hostname=f"{code}.localhost",
        verified=True,
        is_active=True,
        is_primary=True,
        verification_method=TenantDomain.VerificationMethod.LOCAL_DEVELOPMENT,
        verified_at=timezone.now(),
    )
    TenantDatabase.objects.create(
        tenant=tenant,
        database_alias=f"tenant_{code}",
        database_host_reference=os.environ.get("POSTGRES_HOST", "postgres"),
        database_name=f"lattice_{code}",
        runtime_role_name=f"lattice_{code}_app",
        secret_reference=f"env:TENANT_{code.upper()}_DB_PASSWORD",
        sslmode=os.environ.get("POSTGRES_SSLMODE", "prefer"),
        provisioning_status=TenantDatabase.ProvisioningStatus.READY,
    )
    user = get_user_model().objects.create_user(email=f"{code}-{uuid4().hex}@example.test", password="StrongerPass123!")
    membership = TenantMembership.objects.create(user=user, tenant=tenant, status=TenantMembership.Status.ACTIVE)
    role = Role.objects.create(code=f"TENANT_ADMIN_{uuid4().hex[:8]}", name="Tenant Admin", scope=Role.Scope.TENANT)
    for code_name in permissions:
        permission, _ = Permission.objects.get_or_create(code=code_name, defaults={"description": code_name})
        RolePermission.objects.get_or_create(role=role, permission=permission)
    MembershipRole.objects.create(membership=membership, role=role)
    if assign_all_warehouses:
        WarehouseAssignment.objects.create(membership=membership, warehouse_code="*", is_active=True)
    client = Client(HTTP_HOST=f"{code}.localhost")
    cache.clear()
    login = client.post(
        "/api/v1/auth/login/",
        {"email": user.email, "password": "StrongerPass123!"},
        content_type="application/json",
        HTTP_HOST=f"{code}.localhost",
    )
    assert login.status_code == 200
    return client, tenant, membership


@override_settings(ALLOWED_HOSTS=["alpha.localhost", "beta.localhost", "testserver"])
def test_plant_create_edit_duplicate_and_audit(tenant_admin_client):
    client, _tenant, _membership = tenant_admin_client
    suffix = uuid4().hex[:10]

    created = client.post(
        "/api/v1/tenant/plants/",
        {"plant_code": f"PL-{suffix}", "name": "Primary Site", "timezone": "UTC"},
        content_type="application/json",
        HTTP_HOST="alpha.localhost",
    )
    duplicate = client.post(
        "/api/v1/tenant/plants/",
        {"plant_code": f"PL-{suffix}", "name": "Duplicate Site"},
        content_type="application/json",
        HTTP_HOST="alpha.localhost",
    )
    updated = client.patch(
        f"/api/v1/tenant/plants/{created.json()['id']}/",
        {"name": "Primary Site Updated", "status": "INACTIVE"},
        content_type="application/json",
        HTTP_HOST="alpha.localhost",
    )

    assert created.status_code == 201
    assert duplicate.status_code == 400
    assert duplicate.json()["error"]["code"] == "DUPLICATE_CODE"
    assert updated.status_code == 200
    assert updated.json()["name"] == "Primary Site Updated"
    assert AuditEvent.objects.filter(action="PLANT_CREATED").exists()
    assert AuditEvent.objects.filter(action="PLANT_UPDATED").exists()
    assert AuditEvent.objects.filter(action="PLANT_STATUS_CHANGED").exists()


@override_settings(ALLOWED_HOSTS=["alpha.localhost", "beta.localhost", "testserver"])
def test_warehouse_direct_to_tenant_and_invalid_plant_reference(tenant_admin_client):
    client, _tenant, _membership = tenant_admin_client
    suffix = uuid4().hex[:10]

    direct = client.post(
        "/api/v1/tenant/warehouses/",
        {"code": f"WH-{suffix}", "name": "Direct Warehouse", "status": "ACTIVE", "warehouse_type": "GENERAL"},
        content_type="application/json",
        HTTP_HOST="alpha.localhost",
    )
    invalid = client.post(
        "/api/v1/tenant/warehouses/",
        {"code": f"WH-X-{suffix}", "name": "Invalid Warehouse", "plant_id": str(uuid4())},
        content_type="application/json",
        HTTP_HOST="alpha.localhost",
    )

    assert direct.status_code == 201
    assert direct.json()["plant_id"] is None
    assert invalid.status_code == 400


@override_settings(ALLOWED_HOSTS=["alpha.localhost", "beta.localhost", "testserver"])
def test_product_category_crud_hierarchy_duplicate_and_audit(tenant_admin_client):
    client, _tenant, _membership = tenant_admin_client
    suffix = uuid4().hex[:10]

    parent = client.post(
        "/api/v1/tenant/product-categories/",
        {"category_code": f"CAT-{suffix}", "name": "Parent Category", "status": "ACTIVE"},
        content_type="application/json",
        HTTP_HOST="alpha.localhost",
    )
    child = client.post(
        "/api/v1/tenant/product-categories/",
        {"category_code": f"CAT-C-{suffix}", "name": "Child Category", "parent_category_id": parent.json()["id"]},
        content_type="application/json",
        HTTP_HOST="alpha.localhost",
    )
    duplicate = client.post(
        "/api/v1/tenant/product-categories/",
        {"category_code": f"CAT-{suffix}", "name": "Duplicate Category"},
        content_type="application/json",
        HTTP_HOST="alpha.localhost",
    )
    self_parent = client.patch(
        f"/api/v1/tenant/product-categories/{child.json()['id']}/",
        {"parent_category_id": child.json()["id"]},
        content_type="application/json",
        HTTP_HOST="alpha.localhost",
    )
    updated = client.patch(
        f"/api/v1/tenant/product-categories/{child.json()['id']}/",
        {"name": "Child Category Updated", "status": "INACTIVE"},
        content_type="application/json",
        HTTP_HOST="alpha.localhost",
    )
    listed = client.get("/api/v1/tenant/product-categories/?search=Child", HTTP_HOST="alpha.localhost")

    assert parent.status_code == 201
    assert child.status_code == 201
    assert child.json()["parent_category_id"] == parent.json()["id"]
    assert duplicate.status_code == 400
    assert duplicate.json()["error"]["code"] == "DUPLICATE_CODE"
    assert self_parent.status_code == 400
    assert updated.status_code == 200
    assert updated.json()["name"] == "Child Category Updated"
    assert updated.json()["status"] == "INACTIVE"
    assert listed.status_code == 200
    assert listed.json()["count"] >= 1
    assert AuditEvent.objects.filter(action="PRODUCT_CATEGORY_CREATED").count() >= 2
    assert AuditEvent.objects.filter(action="PRODUCT_CATEGORY_UPDATED").exists()
    assert AuditEvent.objects.filter(action="PRODUCT_CATEGORY_STATUS_CHANGED").exists()


@override_settings(ALLOWED_HOSTS=["alpha.localhost", "beta.localhost", "testserver"])
def test_zone_storage_type_section_bay_crud_and_hierarchy_validation(tenant_admin_client):
    client, _tenant, _membership = tenant_admin_client
    suffix = uuid4().hex[:10]
    warehouse = client.post(
        "/api/v1/tenant/warehouses/",
        {"code": f"WH-{suffix}", "name": "Hierarchy Warehouse", "status": "ACTIVE"},
        content_type="application/json",
        HTTP_HOST="alpha.localhost",
    ).json()
    other_warehouse = client.post(
        "/api/v1/tenant/warehouses/",
        {"code": f"WH-B-{suffix}", "name": "Other Warehouse", "status": "ACTIVE"},
        content_type="application/json",
        HTTP_HOST="alpha.localhost",
    ).json()
    zone = client.post(
        "/api/v1/tenant/zones/",
        {"warehouse_id": warehouse["id"], "zone_code": f"ZN-{suffix}", "name": "Storage", "zone_type": "STORAGE"},
        content_type="application/json",
        HTTP_HOST="alpha.localhost",
    ).json()
    other_zone = client.post(
        "/api/v1/tenant/zones/",
        {"warehouse_id": other_warehouse["id"], "zone_code": f"ZN-B-{suffix}", "name": "Other", "zone_type": "STORAGE"},
        content_type="application/json",
        HTTP_HOST="alpha.localhost",
    ).json()
    storage_type = client.post(
        "/api/v1/tenant/storage-types/",
        {"warehouse_id": warehouse["id"], "storage_type_code": f"ST-{suffix}", "name": "Rack"},
        content_type="application/json",
        HTTP_HOST="alpha.localhost",
    ).json()
    section = client.post(
        "/api/v1/tenant/storage-sections/",
        {"warehouse_id": warehouse["id"], "zone_id": zone["id"], "storage_type_id": storage_type["id"], "section_code": f"SC-{suffix}", "name": "Aisle A"},
        content_type="application/json",
        HTTP_HOST="alpha.localhost",
    )
    invalid_section = client.post(
        "/api/v1/tenant/storage-sections/",
        {"warehouse_id": warehouse["id"], "zone_id": other_zone["id"], "section_code": f"BAD-{suffix}", "name": "Invalid"},
        content_type="application/json",
        HTTP_HOST="alpha.localhost",
    )
    bay_created = client.post(
        "/api/v1/tenant/bays/",
        {"warehouse_id": warehouse["id"], "zone_id": zone["id"], "storage_type_id": storage_type["id"], "section_id": section.json()["id"], "bay_code": f"BAY-{suffix}", "barcode": f"BC-{suffix}"},
        content_type="application/json",
        HTTP_HOST="alpha.localhost",
    )
    duplicate_bay = client.post(
        "/api/v1/tenant/bays/",
        {"warehouse_id": warehouse["id"], "zone_id": zone["id"], "bay_code": f"BAY-{suffix}"},
        content_type="application/json",
        HTTP_HOST="alpha.localhost",
    )
    blocked = client.patch(
        f"/api/v1/tenant/bays/{bay_created.json()['id']}/",
        {"is_blocked": True},
        content_type="application/json",
        HTTP_HOST="alpha.localhost",
    )

    assert section.status_code == 201
    assert invalid_section.status_code == 400
    assert bay_created.status_code == 201
    assert duplicate_bay.status_code == 400
    assert blocked.status_code == 200
    assert blocked.json()["is_blocked"] is True
    assert blocked.json()["status"] == "BLOCKED"
    for action in ("ZONE_CREATED", "STORAGE_TYPE_CREATED", "SECTION_CREATED", "BAY_CREATED", "BAY_BLOCKED"):
        assert AuditEvent.objects.filter(action=action).exists()
    assert WarehouseLog.objects.using("tenant_alpha").filter(action="BAY_CREATED").exists()


@override_settings(ALLOWED_HOSTS=["alpha.localhost", "beta.localhost", "testserver"])
def test_bay_bulk_import_export_and_table_name(tenant_admin_client):
    client, _tenant, _membership = tenant_admin_client
    suffix = uuid4().hex[:10]
    warehouse = client.post(
        "/api/v1/tenant/warehouses/",
        {"code": f"WH-{suffix}", "name": "Bulk Warehouse", "status": "ACTIVE"},
        content_type="application/json",
        HTTP_HOST="alpha.localhost",
    ).json()
    zone = client.post(
        "/api/v1/tenant/zones/",
        {"warehouse_id": warehouse["id"], "zone_code": f"ZN-{suffix}", "name": "Storage", "zone_type": "STORAGE"},
        content_type="application/json",
        HTTP_HOST="alpha.localhost",
    ).json()

    preview = client.post(
        "/api/v1/tenant/bays/bulk/",
        {"warehouse_id": warehouse["id"], "zone_id": zone["id"], "pattern": "A-{rack}-{level}", "racks": "01..02", "levels": "01..02"},
        content_type="application/json",
        HTTP_HOST="alpha.localhost",
    )
    commit = client.post(
        "/api/v1/tenant/bays/bulk/",
        {"warehouse_id": warehouse["id"], "zone_id": zone["id"], "pattern": "A-{rack}-{level}", "racks": "01..02", "levels": "01..02", "commit": True},
        content_type="application/json",
        HTTP_HOST="alpha.localhost",
    )
    import_preview = client.post(
        "/api/v1/tenant/bays/import/",
        {"rows": [{"warehouse_id": warehouse["id"], "zone_id": zone["id"], "bay_code": f"IMP-{suffix}"}]},
        content_type="application/json",
        HTTP_HOST="alpha.localhost",
    )
    imported = client.post(
        "/api/v1/tenant/bays/import/",
        {"commit": True, "rows": [{"warehouse_id": warehouse["id"], "zone_id": zone["id"], "bay_code": f"IMP-{suffix}"}]},
        content_type="application/json",
        HTTP_HOST="alpha.localhost",
    )
    exported = client.get("/api/v1/tenant/bays/export/", HTTP_HOST="alpha.localhost")

    assert preview.status_code == 200
    assert preview.json()["count"] == 4
    assert commit.status_code == 201
    assert commit.json()["created"] == 4
    assert import_preview.status_code == 200
    assert imported.status_code == 201
    assert exported.status_code == 200
    assert b"bay_code" in exported.content
    assert Bay._meta.db_table == "lattice_bay"
    assert Bay.objects.using("tenant_alpha").filter(bin_code=f"IMP-{suffix}").exists()
    assert AuditEvent.objects.filter(action="BAY_BULK_CREATED").exists()
    assert AuditEvent.objects.filter(action="BAY_IMPORT_COMPLETED").exists()


@override_settings(ALLOWED_HOSTS=["alpha.localhost", "beta.localhost", "testserver"])
def test_configuration_crud_and_sequence_actions(tenant_admin_client):
    client, _tenant, _membership = tenant_admin_client
    suffix = uuid4().hex[:10]
    hu = client.post(
        "/api/v1/tenant/configuration/holding-units/",
        {"hu_code": f"HU-{suffix}", "name": "Carton", "hu_type": "CARTON"},
        content_type="application/json",
        HTTP_HOST="alpha.localhost",
    )
    sequence = client.post(
        "/api/v1/tenant/configuration/sequences/",
        {"sequence_code": f"SEQ-{suffix}", "name": "Bay Sequence", "entity_type": "BAY", "prefix": "B-", "padding": 4, "current_value": 7},
        content_type="application/json",
        HTTP_HOST="alpha.localhost",
    )
    preview = client.post(f"/api/v1/tenant/configuration/sequences/{sequence.json()['id']}/preview/", {}, content_type="application/json", HTTP_HOST="alpha.localhost")
    reserve = client.post(f"/api/v1/tenant/configuration/sequences/{sequence.json()['id']}/reserve/", {}, content_type="application/json", HTTP_HOST="alpha.localhost")
    reset = client.post(f"/api/v1/tenant/configuration/sequences/{sequence.json()['id']}/reset/", {}, content_type="application/json", HTTP_HOST="alpha.localhost")

    assert hu.status_code == 201
    assert hu.json()["hu_code"] == f"HU-{suffix}"
    assert sequence.status_code == 201
    assert preview.status_code == 200
    assert preview.json()["value"] == "B-0008"
    assert reserve.status_code == 200
    assert reserve.json()["value"] == "B-0008"
    assert reset.status_code == 200
    assert reset.json()["value"] == "B-0001"


@override_settings(ALLOWED_HOSTS=["alpha.localhost", "beta.localhost", "testserver"])
def test_tenant_users_roles_assignments_and_settings(tenant_admin_client):
    client, _tenant, _membership = tenant_admin_client
    suffix = uuid4().hex[:10]
    role = client.post(
        "/api/v1/tenant/roles/",
        {"code": f"TENANT_OPERATOR_{suffix}".upper(), "name": "Tenant Operator", "permissions": ["tenant.dashboard.view"]},
        content_type="application/json",
        HTTP_HOST="alpha.localhost",
    )
    user = client.post(
        "/api/v1/tenant/users/",
        {"email": f"operator-{suffix}@example.test", "roles": [role.json()["code"]], "warehouses": ["*"]},
        content_type="application/json",
        HTTP_HOST="alpha.localhost",
    )
    assignments = client.post(
        "/api/v1/tenant/warehouse-assignments/",
        {"membership_id": user.json()["id"], "warehouses": ["WH-A"]},
        content_type="application/json",
        HTTP_HOST="alpha.localhost",
    )
    settings = client.patch(
        "/api/v1/tenant/settings/",
        {"display_name": "Tenant Alpha Updated", "timezone": "UTC", "default_language": "en", "warehouse_control": {"uom": "EA"}},
        content_type="application/json",
        HTTP_HOST="alpha.localhost",
    )

    assert role.status_code == 201
    assert user.status_code == 201
    assert user.json()["roles"] == [role.json()["code"]]
    assert assignments.status_code == 200
    assert assignments.json()["warehouses"] == ["WH-A"]
    assert settings.status_code == 200
    assert settings.json()["tenant"]["display_name"] == "Tenant Alpha Updated"


@override_settings(ALLOWED_HOSTS=["alpha.localhost", "beta.localhost", "testserver"])
def test_active_warehouse_context_allowed_and_denied_by_assignment(db):
    client, _tenant, membership = _tenant_client("alpha", ALL_HIERARCHY_PERMISSIONS, assign_all_warehouses=False)
    suffix = uuid4().hex[:10]
    warehouse = client.post(
        "/api/v1/tenant/warehouses/",
        {"code": f"WH-{suffix}", "name": "Assignable Warehouse", "status": "ACTIVE"},
        content_type="application/json",
        HTTP_HOST="alpha.localhost",
    ).json()
    denied = client.post(
        "/api/v1/tenant/context/warehouse/",
        {"warehouse_id": warehouse["id"]},
        content_type="application/json",
        HTTP_HOST="alpha.localhost",
    )
    WarehouseAssignment.objects.create(membership=membership, warehouse_code=warehouse["warehouse_code"], is_active=True)
    allowed = client.post(
        "/api/v1/tenant/context/warehouse/",
        {"warehouse_id": warehouse["id"]},
        content_type="application/json",
        HTTP_HOST="alpha.localhost",
    )

    assert denied.status_code == 403
    assert allowed.status_code == 200
    assert allowed.json()["active_warehouse"]["warehouse_code"] == warehouse["warehouse_code"]
    assert AuditEvent.objects.filter(action="ACTIVE_WAREHOUSE_CHANGED").exists()


@override_settings(ALLOWED_HOSTS=["alpha.localhost", "beta.localhost", "testserver"])
def test_unauthorized_tenant_admin_mutation_is_denied(db):
    client, _tenant, _membership = _tenant_client("alpha", ["organization.plants.view"])

    response = client.post(
        "/api/v1/tenant/plants/",
        {"plant_code": f"PL-{uuid4().hex[:10]}", "name": "Denied"},
        content_type="application/json",
        HTTP_HOST="alpha.localhost",
    )

    assert response.status_code == 403


@override_settings(ALLOWED_HOSTS=["alpha.localhost", "beta.localhost", "testserver"])
def test_unauthorized_product_category_mutation_is_denied(db):
    client, _tenant, _membership = _tenant_client("alpha", ["masters.categories.view"])

    response = client.post(
        "/api/v1/tenant/product-categories/",
        {"category_code": f"CAT-{uuid4().hex[:10]}", "name": "Denied"},
        content_type="application/json",
        HTTP_HOST="alpha.localhost",
    )

    assert response.status_code == 403


@override_settings(ALLOWED_HOSTS=["alpha.localhost", "beta.localhost", "testserver"])
def test_alpha_cannot_access_beta_hierarchy_with_alpha_session(tenant_admin_client):
    client, _tenant, _membership = tenant_admin_client

    response = client.get("/api/v1/tenant/plants/", HTTP_HOST="beta.localhost")

    assert response.status_code == 403
