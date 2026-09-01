from __future__ import annotations

from django.conf import settings
from django.db import connections

from control.models import TenantDatabase
from tenancy.secrets import get_secret_provider


def register_tenant_database(database: TenantDatabase) -> str:
    """Register a tenant DB alias from trusted control-plane metadata."""
    alias = database.database_alias
    if alias == "default":
        raise ValueError("Tenant database alias must not be default.")
    if alias in connections.databases:
        return alias
    password = get_secret_provider().get_secret(database.secret_reference)
    connection_settings = connections.databases["default"].copy()
    connection_settings.update(
        {
            "NAME": database.database_name,
            "USER": database.runtime_role_name,
            "PASSWORD": password,
            "HOST": settings.POSTGRES_HOST if hasattr(settings, "POSTGRES_HOST") else "localhost",
            "PORT": str(database.port),
            "CONN_MAX_AGE": 60,
            "OPTIONS": {
                "sslmode": database.sslmode,
                "connect_timeout": int(getattr(settings, "POSTGRES_CONNECT_TIMEOUT", 5)),
            },
        }
    )
    connections.databases[alias] = connection_settings
    return alias
