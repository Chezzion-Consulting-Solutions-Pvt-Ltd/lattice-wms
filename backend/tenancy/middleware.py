from __future__ import annotations

from collections.abc import Callable

from django.http import JsonResponse

from tenancy.context import clear_tenant_context, set_tenant_context
from tenancy.connections import register_tenant_database
from tenancy.exceptions import LatticeSecurityError
from tenancy.resolver import TenantResolver


class TenantResolutionMiddleware:
    """Establish tenant context for tenant API requests and always clean it up."""

    def __init__(self, get_response: Callable) -> None:
        self.get_response = get_response
        self.resolver = TenantResolver()

    def __call__(self, request):
        try:
            if request.path.startswith("/api/v1/tenant/"):
                resolved = self.resolver.resolve_request(request)
                register_tenant_database(resolved.database)
                set_tenant_context(
                    tenant_id=resolved.tenant.id,
                    tenant_code=resolved.tenant.tenant_code,
                    database_alias=resolved.database.database_alias,
                    database_name=resolved.database.database_name,
                    runtime_role_name=resolved.database.runtime_role_name,
                )
            return self.get_response(request)
        except LatticeSecurityError as exc:
            return JsonResponse(
                {
                    "error": {
                        "code": exc.__class__.__name__,
                        "message": "Tenant access denied.",
                        "request_id": getattr(request, "request_id", ""),
                    }
                },
                status=403,
            )
        finally:
            clear_tenant_context()
