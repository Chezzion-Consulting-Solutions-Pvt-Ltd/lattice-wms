from __future__ import annotations

import os
from uuid import uuid4

import pytest
from django.contrib.auth import get_user_model
from django.test import Client, override_settings
from django.utils import timezone

from audit.models import AuditEvent
from control.models import Tenant, TenantDatabase, TenantDomain, TenantMembership
from identity.models import MembershipRole, Permission, Role, RolePermission, WarehouseAssignment


pytestmark = [
    pytest.mark.skipif(
        os.environ.get("LATTICE_RUN_DB_ISOLATION") != "1",
        reason="requires real local PostgreSQL tenant DBs",
    ),
    pytest.mark.django_db(databases="__all__"),
]


ALL_HIERARCHY_PERMISSIONS = [
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


def _tenant_client(code: str, permissions: list[str]):
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
    client = Client(HTTP_HOST=f"{code}.localhost")
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
def test_zone_storage_type_section_bin_crud_and_hierarchy_validation(tenant_admin_client):
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
    bin_created = client.post(
        "/api/v1/tenant/bins/",
        {"warehouse_id": warehouse["id"], "zone_id": zone["id"], "storage_type_id": storage_type["id"], "section_id": section.json()["id"], "bin_code": f"BIN-{suffix}", "barcode": f"BC-{suffix}"},
        content_type="application/json",
        HTTP_HOST="alpha.localhost",
    )
    duplicate_bin = client.post(
        "/api/v1/tenant/bins/",
        {"warehouse_id": warehouse["id"], "zone_id": zone["id"], "bin_code": f"BIN-{suffix}"},
        content_type="application/json",
        HTTP_HOST="alpha.localhost",
    )
    blocked = client.patch(
        f"/api/v1/tenant/bins/{bin_created.json()['id']}/",
        {"is_blocked": True},
        content_type="application/json",
        HTTP_HOST="alpha.localhost",
    )

    assert section.status_code == 201
    assert invalid_section.status_code == 400
    assert bin_created.status_code == 201
    assert duplicate_bin.status_code == 400
    assert blocked.status_code == 200
    assert blocked.json()["is_blocked"] is True
    assert blocked.json()["status"] == "BLOCKED"
    for action in ("ZONE_CREATED", "STORAGE_TYPE_CREATED", "SECTION_CREATED", "BIN_CREATED", "BIN_BLOCKED"):
        assert AuditEvent.objects.filter(action=action).exists()


@override_settings(ALLOWED_HOSTS=["alpha.localhost", "beta.localhost", "testserver"])
def test_active_warehouse_context_allowed_and_denied_by_assignment(tenant_admin_client):
    client, _tenant, membership = tenant_admin_client
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
