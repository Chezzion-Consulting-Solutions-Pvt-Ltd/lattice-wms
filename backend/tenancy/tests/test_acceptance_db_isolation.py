import os
from uuid import uuid4

import pytest
from django.contrib.auth import get_user_model
from django.test import RequestFactory

from control.models import Tenant, TenantDatabase, TenantDomain, TenantMembership
from tenancy.connections import register_tenant_database
from tenancy.exceptions import TenantResolutionError
from tenancy.resolver import TenantResolver

psycopg = pytest.importorskip("psycopg")


pytestmark = pytest.mark.skipif(
    os.environ.get("LATTICE_RUN_DB_ISOLATION") != "1",
    reason="requires real local PostgreSQL tenant DBs",
)


def _dsn(user: str, password: str, dbname: str) -> str:
    host = os.environ.get("POSTGRES_HOST", "localhost")
    port = os.environ.get("POSTGRES_PORT", "5432")
    return f"host={host} port={port} dbname={dbname} user={user} password={password}"


@pytest.fixture
def registered_alpha_beta(db):
    tenants = {}
    for code in ("alpha", "beta"):
        tenant = Tenant.objects.create(tenant_code=code, display_name=f"Tenant {code.title()}", status=Tenant.Status.ACTIVE)
        TenantDomain.objects.create(tenant=tenant, hostname=f"{code}.localhost", verified=True, is_primary=True)
        database = TenantDatabase.objects.create(
            tenant=tenant,
            database_alias=f"tenant_{code}",
            database_host_reference=os.environ.get("POSTGRES_HOST", "localhost"),
            database_name=f"lattice_{code}",
            runtime_role_name=f"lattice_{code}_app",
            secret_reference=f"env:TENANT_{code.upper()}_DB_PASSWORD",
            sslmode=os.environ.get("POSTGRES_SSLMODE", "prefer"),
            provisioning_status=TenantDatabase.ProvisioningStatus.READY,
        )
        register_tenant_database(database)
        tenants[code] = tenant
    return tenants


def test_alpha_runtime_credential_cannot_connect_to_beta_database():
    alpha_password = os.environ["TENANT_ALPHA_DB_PASSWORD"]
    with pytest.raises(psycopg.OperationalError):
        psycopg.connect(_dsn("lattice_alpha_app", alpha_password, "lattice_beta"), connect_timeout=2)


def test_beta_runtime_credential_cannot_connect_to_alpha_database():
    beta_password = os.environ["TENANT_BETA_DB_PASSWORD"]
    with pytest.raises(psycopg.OperationalError):
        psycopg.connect(_dsn("lattice_beta_app", beta_password, "lattice_alpha"), connect_timeout=2)


def test_alpha_runtime_credential_can_connect_to_alpha_database():
    alpha_password = os.environ["TENANT_ALPHA_DB_PASSWORD"]
    with psycopg.connect(_dsn("lattice_alpha_app", alpha_password, "lattice_alpha"), connect_timeout=2) as connection:
        with connection.cursor() as cursor:
            cursor.execute("select current_database(), current_user")
            assert cursor.fetchone() == ("lattice_alpha", "lattice_alpha_app")


def test_beta_runtime_credential_can_connect_to_beta_database():
    beta_password = os.environ["TENANT_BETA_DB_PASSWORD"]
    with psycopg.connect(_dsn("lattice_beta_app", beta_password, "lattice_beta"), connect_timeout=2) as connection:
        with connection.cursor() as cursor:
            cursor.execute("select current_database(), current_user")
            assert cursor.fetchone() == ("lattice_beta", "lattice_beta_app")


@pytest.mark.django_db
def test_alpha_user_routes_to_alpha_database_and_cannot_read_beta_context_object(registered_alpha_beta):
    user = get_user_model().objects.create_user(email=f"alpha-{uuid4()}@example.test")
    TenantMembership.objects.create(user=user, tenant=registered_alpha_beta["alpha"], status=TenantMembership.Status.ACTIVE)

    request = RequestFactory().get("/api/v1/tenant/probe/", HTTP_HOST="alpha.localhost")
    request.global_user = user
    resolved = TenantResolver().resolve_request(request)
    assert resolved.tenant == registered_alpha_beta["alpha"]
    assert resolved.database.database_name == "lattice_alpha"

    alpha_password = os.environ["TENANT_ALPHA_DB_PASSWORD"]
    beta_password = os.environ["TENANT_BETA_DB_PASSWORD"]
    warehouse_id = uuid4()
    object_id = uuid4()
    with psycopg.connect(_dsn("lattice_alpha_app", alpha_password, "lattice_alpha"), connect_timeout=2) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                insert into lattice_whs (
                    id, code, name, is_active, address_line_1, address_line_2,
                    capacity_metadata, city, country, created_at, description,
                    postal_code, state, status, timezone, updated_at, warehouse_type
                )
                values (%s, %s, %s, %s, '', '', '{}', '', '', now(), '', '', '', 'ACTIVE', 'UTC', now(), '')
                """,
                (warehouse_id, f"A-{uuid4().hex[:12]}", "Alpha Warehouse", True),
            )
            cursor.execute(
                "insert into lattice_probe (id, external_reference, warehouse_id) values (%s, %s, %s)",
                (object_id, "alpha-only", warehouse_id),
            )
            cursor.execute("select external_reference from lattice_probe where id = %s", (object_id,))
            assert cursor.fetchone() == ("alpha-only",)

    with psycopg.connect(_dsn("lattice_beta_app", beta_password, "lattice_beta"), connect_timeout=2) as connection:
        with connection.cursor() as cursor:
            cursor.execute("select external_reference from lattice_probe where id = %s", (object_id,))
            assert cursor.fetchone() is None


@pytest.mark.django_db
def test_browser_supplied_database_name_is_rejected_before_database_selection(registered_alpha_beta):
    user = get_user_model().objects.create_user(email=f"selector-{uuid4()}@example.test")
    TenantMembership.objects.create(user=user, tenant=registered_alpha_beta["alpha"], status=TenantMembership.Status.ACTIVE)
    request = RequestFactory().get("/api/v1/tenant/probe/?database=lattice_beta", HTTP_HOST="alpha.localhost")
    request.global_user = user

    with pytest.raises(TenantResolutionError):
        TenantResolver().resolve_request(request)
