from __future__ import annotations

import re
from dataclasses import dataclass

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
