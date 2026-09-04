from __future__ import annotations

import re
from dataclasses import dataclass

import psycopg
from django.conf import settings

from tenancy.secrets import get_secret_provider

SAFE_IDENTIFIER = re.compile(r"^[a-z][a-z0-9_]{2,62}$")


@dataclass(frozen=True)
class TenantDatabasePlan:
    database_name: str
    runtime_role_name: str
    secret_reference: str


def validate_pg_identifier(identifier: str) -> str:
    if not SAFE_IDENTIFIER.fullmatch(identifier):
        raise ValueError("Unsafe PostgreSQL identifier.")
    return identifier


def quote_identifier(identifier: str) -> str:
    validate_pg_identifier(identifier)
    return f'"{identifier}"'


def build_tenant_database_plan(tenant_code: str, secret_reference: str) -> TenantDatabasePlan:
    safe_code = validate_pg_identifier(tenant_code)
    return TenantDatabasePlan(
        database_name=f"lattice_{safe_code}",
        runtime_role_name=f"lattice_{safe_code}_app",
        secret_reference=secret_reference,
    )


def build_provisioning_sql(plan: TenantDatabasePlan) -> list[str]:
    database = quote_identifier(plan.database_name)
    role = quote_identifier(plan.runtime_role_name)
    return [
        f"CREATE ROLE {role} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT PASSWORD %s",
        f"CREATE DATABASE {database} OWNER {role}",
        f"REVOKE ALL ON DATABASE {database} FROM PUBLIC",
        f"GRANT CONNECT, TEMPORARY ON DATABASE {database} TO {role}",
    ]


def execute_tenant_database_plan(plan: TenantDatabasePlan) -> None:
    """Create a tenant PostgreSQL database and non-superuser runtime role.

    The raw password is resolved from the configured secret provider and is
    never persisted in the control database or returned to API callers.
    """
    password = get_secret_provider().get_secret(plan.secret_reference)
    admin_user = getattr(settings, "POSTGRES_ADMIN_USER", "")
    admin_password = getattr(settings, "POSTGRES_ADMIN_PASSWORD", "")
    if not admin_user or not admin_password:
        raise RuntimeError("PostgreSQL admin connector is not configured.")
    admin_host = getattr(settings, "POSTGRES_HOST", "localhost")
    admin_port = getattr(settings, "POSTGRES_PORT", 5432)
    sslmode = getattr(settings, "POSTGRES_SSLMODE", "prefer")
    with psycopg.connect(
        dbname="postgres",
        user=admin_user,
        password=admin_password,
        host=admin_host,
        port=admin_port,
        sslmode=sslmode,
        autocommit=True,
    ) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", [plan.runtime_role_name])
            if cursor.fetchone() is None:
                cursor.execute(
                    f"CREATE ROLE {quote_identifier(plan.runtime_role_name)} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT PASSWORD %s",
                    [password],
                )
            cursor.execute("SELECT 1 FROM pg_database WHERE datname = %s", [plan.database_name])
            if cursor.fetchone() is None:
                cursor.execute(f"CREATE DATABASE {quote_identifier(plan.database_name)} OWNER {quote_identifier(plan.runtime_role_name)}")
            cursor.execute(f"REVOKE ALL ON DATABASE {quote_identifier(plan.database_name)} FROM PUBLIC")
            cursor.execute(f"GRANT CONNECT, TEMPORARY ON DATABASE {quote_identifier(plan.database_name)} TO {quote_identifier(plan.runtime_role_name)}")
