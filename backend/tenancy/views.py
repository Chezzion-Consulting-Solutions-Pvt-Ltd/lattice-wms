from rest_framework.response import Response
from rest_framework.views import APIView

from control.models import Tenant, TenantMembership, TenantModule
from identity.models import Role
from tenancy.context import get_tenant_context
from warehouse.models import Bin, Plant, Warehouse, Zone


class TenantProbeView(APIView):
    throttle_scope = "standard_api"

    def get(self, request):
        context = get_tenant_context()
        return Response(
            {
                "tenant_code": context.tenant_code,
                "request_id": getattr(request, "request_id", ""),
            }
        )


class TenantContextView(APIView):
    throttle_scope = "standard_api"

    def get(self, request):
        context = get_tenant_context()
        tenant = Tenant.objects.get(id=context.tenant_id)
        membership = TenantMembership.objects.get(user=request.user, tenant=tenant, status=TenantMembership.Status.ACTIVE)
        permissions = sorted(
            membership.role_assignments.filter(role__scope=Role.Scope.TENANT).values_list("role__permissions__code", flat=True).distinct()
        )
        roles = sorted(membership.role_assignments.filter(role__scope=Role.Scope.TENANT).values_list("role__code", flat=True).distinct())
        warehouse_assignments = list(
            membership.warehouse_assignments.filter(is_active=True).values("warehouse_code").order_by("warehouse_code")
        )
        return Response(
            {
                "tenant": {
                    "id": str(tenant.id),
                    "tenant_code": tenant.tenant_code,
                    "display_name": tenant.display_name,
                    "status": tenant.status,
                    "license_number": tenant.license_number,
                },
                "session": {
                    "mfa_enabled": bool(getattr(getattr(request.user, "mfa_device", None), "enabled", False)),
                    "active_warehouse": request.session.get("active_warehouse_code"),
                },
                "authorization": {
                    "membership_id": str(membership.id),
                    "roles": roles,
                    "permissions": permissions,
                    "warehouses": warehouse_assignments,
                },
                "modules": list(TenantModule.objects.filter(tenant=tenant, enabled=True).values_list("module_code", flat=True).order_by("module_code")),
                "counts": {
                    "plants": Plant.objects.count(),
                    "warehouses": Warehouse.objects.count(),
                    "zones": Zone.objects.count(),
                    "bins": Bin.objects.count(),
                    "active_users": TenantMembership.objects.filter(tenant=tenant, status=TenantMembership.Status.ACTIVE).count(),
                    "enabled_modules": TenantModule.objects.filter(tenant=tenant, enabled=True).count(),
                },
            }
        )
