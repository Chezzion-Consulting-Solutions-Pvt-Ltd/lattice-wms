from __future__ import annotations

from dataclasses import dataclass

from control.models import Tenant, TenantDatabase, TenantDomain, TenantMembership
from tenancy.context import TenantContext
from tenancy.exceptions import TenantResolutionError, TenantUnavailableError


UNTRUSTED_DB_QUERY_KEYS = {"database", "db", "database_name", "database_alias", "schema", "connection_string"}
UNTRUSTED_DB_HEADERS = {"HTTP_X_DATABASE", "HTTP_X_TENANT_ID", "HTTP_X_DATABASE_ALIAS"}


@dataclass(frozen=True)
class ResolvedTenant:
    tenant: Tenant
    database: TenantDatabase

    def to_context(self) -> TenantContext:
        return TenantContext(
            tenant_id=self.tenant.id,
            tenant_code=self.tenant.tenant_code,
            database_alias=self.database.database_alias,
            database_name=self.database.database_name,
            runtime_role_name=self.database.runtime_role_name,
        )


class TenantResolver:
    """Resolve tenants from trusted server-side state only."""

    def resolve_request(self, request) -> ResolvedTenant:
        self._reject_database_selector_attempts(request)
        hostname = request.get_host().split(":", 1)[0].lower()
        domain = (
            TenantDomain.objects.select_related("tenant", "tenant__database")
            .filter(hostname=hostname, verified=True)
            .first()
        )
        if domain is None:
            raise TenantResolutionError("Tenant could not be resolved.")
        tenant = domain.tenant
        if tenant.status != Tenant.Status.ACTIVE:
            raise TenantUnavailableError("Tenant is not active.")
        database = getattr(tenant, "database", None)
        if database is None or database.provisioning_status != TenantDatabase.ProvisioningStatus.READY:
            raise TenantUnavailableError("Tenant database is unavailable.")
        self._assert_membership(request, tenant)
        return ResolvedTenant(tenant=tenant, database=database)

    def _assert_membership(self, request, tenant: Tenant) -> None:
        global_user = getattr(request, "global_user", None) or getattr(request, "user", None)
        if global_user is None or not getattr(global_user, "is_authenticated", True):
            return
        membership_exists = TenantMembership.objects.filter(
            user=global_user,
            tenant=tenant,
            status=TenantMembership.Status.ACTIVE,
        ).exists()
        if not membership_exists:
            raise TenantResolutionError("Tenant membership is required.")

    def _reject_database_selector_attempts(self, request) -> None:
        query_keys = {key.lower() for key in request.GET.keys()}
        if query_keys & UNTRUSTED_DB_QUERY_KEYS:
            raise TenantResolutionError("Client-supplied database selectors are not allowed.")
        if any(header in request.META for header in UNTRUSTED_DB_HEADERS):
            raise TenantResolutionError("Client-supplied tenant database headers are not allowed.")
