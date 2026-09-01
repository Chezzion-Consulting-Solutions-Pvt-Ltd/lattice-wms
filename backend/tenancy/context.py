from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Iterator
from uuid import UUID

from tenancy.exceptions import TenantContextError


@dataclass(frozen=True)
class TenantContext:
    tenant_id: UUID
    tenant_code: str
    database_alias: str
    database_name: str
    runtime_role_name: str


_tenant_context: ContextVar[TenantContext | None] = ContextVar("lattice_tenant_context", default=None)


def set_tenant_context(
    tenant_id: UUID | str,
    tenant_code: str,
    database_alias: str,
    database_name: str,
    runtime_role_name: str,
) -> TenantContext:
    context = TenantContext(
        tenant_id=UUID(str(tenant_id)),
        tenant_code=tenant_code,
        database_alias=database_alias,
        database_name=database_name,
        runtime_role_name=runtime_role_name,
    )
    _tenant_context.set(context)
    return context


def get_tenant_context() -> TenantContext:
    context = _tenant_context.get()
    if context is None:
        raise TenantContextError("Tenant context is required for tenant database access.")
    return context


def get_optional_tenant_context() -> TenantContext | None:
    return _tenant_context.get()


def clear_tenant_context() -> None:
    _tenant_context.set(None)


@contextmanager
def tenant_context(**kwargs: object) -> Iterator[TenantContext]:
    context = set_tenant_context(**kwargs)
    try:
        yield context
    finally:
        clear_tenant_context()
