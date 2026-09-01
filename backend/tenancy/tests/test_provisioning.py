import pytest

from tenancy.provisioning import build_provisioning_sql, build_tenant_database_plan


def test_builds_isolated_database_and_runtime_role_plan():
    plan = build_tenant_database_plan("alpha", "env:TENANT_ALPHA_DB_PASSWORD")
    assert plan.database_name == "lattice_alpha"
    assert plan.runtime_role_name == "lattice_alpha_app"
    sql = build_provisioning_sql(plan)
    assert 'CREATE ROLE "lattice_alpha_app" LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT PASSWORD %s' in sql
    assert 'CREATE DATABASE "lattice_alpha" OWNER "lattice_alpha_app"' in sql
    assert 'REVOKE ALL ON DATABASE "lattice_alpha" FROM PUBLIC' in sql


def test_rejects_unsafe_postgres_identifiers():
    with pytest.raises(ValueError):
        build_tenant_database_plan("alpha;drop_database", "env:BAD")
