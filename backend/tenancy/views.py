from django.contrib.auth import get_user_model
from rest_framework.response import Response
from rest_framework.views import APIView

from control.models import Tenant, TenantMembership, TenantModule
from identity.authorization import has_permission
from identity.models import MembershipRole, Permission, Role, RolePermission, WarehouseAssignment
from tenancy.context import get_tenant_context
from warehouse.models import Bay, Machine, PeopleResource, Plant, StorageSection, StorageType, Warehouse, WarehouseControl, Zone
from warehouse.views import _audit, _error


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
                    "storage_types": StorageType.objects.count(),
                    "zones": Zone.objects.count(),
                    "sections": StorageSection.objects.count(),
                    "bays": Bay.objects.count(),
                    "bins": Bay.objects.count(),
                    "active_bays": Bay.objects.filter(status="ACTIVE", is_blocked=False).count(),
                    "blocked_bays": Bay.objects.filter(is_blocked=True).count(),
                    "machines": Machine.objects.count(),
                    "people_resources": PeopleResource.objects.count(),
                    "configuration_alerts": _configuration_alert_count(),
                    "active_users": TenantMembership.objects.filter(tenant=tenant, status=TenantMembership.Status.ACTIVE).count(),
                    "enabled_modules": TenantModule.objects.filter(tenant=tenant, enabled=True).count(),
                },
            }
        )


class TenantUsersView(APIView):
    throttle_scope = "standard_api"

    def get(self, request):
        permission_error = _permission_error(request, "tenant.users.view")
        if permission_error:
            return permission_error
        tenant = _current_tenant()
        memberships = TenantMembership.objects.filter(tenant=tenant).select_related("user").order_by("user__email")
        return Response({"results": [_serialize_membership(membership) for membership in memberships], "count": memberships.count()})

    def post(self, request):
        permission_error = _permission_error(request, "tenant.users.manage")
        if permission_error:
            return permission_error
        tenant = _current_tenant()
        email = str(request.data.get("email", "")).strip().lower()
        if not email:
            return _error("VALIDATION_ERROR", "email is required.", 400)
        user_model = get_user_model()
        user, created = user_model.objects.get_or_create(email=email, defaults={"is_active": True})
        if created:
            user.set_unusable_password()
            user.save(update_fields=["password", "password_changed_at"])
        membership, _ = TenantMembership.objects.get_or_create(user=user, tenant=tenant, defaults={"status": TenantMembership.Status.ACTIVE})
        _replace_roles(membership, request.data.get("roles", []))
        _replace_warehouse_assignments(membership, request.data.get("warehouses", []))
        _audit(request, "TENANT_USER_INVITED", "tenant_user", str(membership.id), after=_serialize_membership(membership))
        return Response(_serialize_membership(membership), status=201)


class TenantUserDetailView(APIView):
    throttle_scope = "standard_api"

    def patch(self, request, membership_id):
        permission_error = _permission_error(request, "tenant.users.manage")
        if permission_error:
            return permission_error
        membership = _tenant_membership(membership_id)
        if "status" in request.data:
            membership.status = request.data["status"]
            membership.save(update_fields=["status", "updated_at"])
        if "roles" in request.data:
            _replace_roles(membership, request.data.get("roles", []))
        if "warehouses" in request.data:
            _replace_warehouse_assignments(membership, request.data.get("warehouses", []))
        _audit(request, "TENANT_MEMBERSHIP_UPDATED", "tenant_user", str(membership.id), after=_serialize_membership(membership))
        return Response(_serialize_membership(membership))


class TenantRolesView(APIView):
    throttle_scope = "standard_api"

    def get(self, request):
        permission_error = _permission_error(request, "tenant.roles.view")
        if permission_error:
            return permission_error
        roles = Role.objects.filter(scope=Role.Scope.TENANT, is_active=True).order_by("code")
        return Response({"results": [_serialize_role(role) for role in roles], "count": roles.count()})

    def post(self, request):
        permission_error = _permission_error(request, "tenant.roles.manage")
        if permission_error:
            return permission_error
        code = str(request.data.get("code", "")).strip().upper()
        name = str(request.data.get("name", "")).strip()
        if not code or not name:
            return _error("VALIDATION_ERROR", "code and name are required.", 400)
        role, _ = Role.objects.update_or_create(
            code=code,
            defaults={"name": name, "scope": Role.Scope.TENANT, "is_active": bool(request.data.get("is_active", True)), "requires_mfa": bool(request.data.get("requires_mfa", False))},
        )
        _replace_permissions(role, request.data.get("permissions", []))
        _audit(request, "TENANT_ROLE_UPDATED", "tenant_role", str(role.id), after=_serialize_role(role))
        return Response(_serialize_role(role), status=201)


class TenantPermissionsView(APIView):
    throttle_scope = "standard_api"

    def get(self, request):
        permission_error = _permission_error(request, "tenant.roles.view")
        if permission_error:
            return permission_error
        permissions = Permission.objects.filter(code__startswith="tenant.").order_by("code")
        return Response({"results": [{"code": permission.code, "description": permission.description} for permission in permissions]})


class TenantWarehouseAssignmentsView(APIView):
    throttle_scope = "standard_api"

    def get(self, request):
        permission_error = _permission_error(request, "tenant.warehouse_assignments.view")
        if permission_error:
            return permission_error
        tenant = _current_tenant()
        memberships = TenantMembership.objects.filter(tenant=tenant).select_related("user").order_by("user__email")
        return Response({"results": [_serialize_membership(membership) for membership in memberships], "count": memberships.count()})

    def post(self, request):
        permission_error = _permission_error(request, "tenant.warehouse_assignments.manage")
        if permission_error:
            return permission_error
        membership = _tenant_membership(request.data.get("membership_id"))
        _replace_warehouse_assignments(membership, request.data.get("warehouses", []))
        _audit(request, "WAREHOUSE_ASSIGNMENT_UPDATED", "warehouse_assignment", str(membership.id), after=_serialize_membership(membership))
        return Response(_serialize_membership(membership))


class TenantSettingsView(APIView):
    throttle_scope = "standard_api"

    def get(self, request):
        permission_error = _permission_error(request, "tenant.settings.view")
        if permission_error:
            return permission_error
        tenant = _current_tenant()
        controls = WarehouseControl.objects.filter(scope="TENANT", process="tenant-settings").first()
        return Response({"tenant": _serialize_tenant(tenant), "warehouse_control": _serialize_warehouse_control(controls)})

    def patch(self, request):
        permission_error = _permission_error(request, "tenant.settings.manage")
        if permission_error:
            return permission_error
        tenant = _current_tenant()
        for field in ("display_name", "timezone", "default_language"):
            if field in request.data:
                setattr(tenant, field, request.data[field])
        tenant.save(update_fields=["display_name", "timezone", "default_language", "updated_at"])
        settings = request.data.get("warehouse_control")
        if isinstance(settings, dict):
            control, _ = WarehouseControl.objects.get_or_create(scope="TENANT", process="tenant-settings", defaults={"name": "Tenant Settings"})
            control.settings = settings
            control.updated_by_user_id = request.user.id
            control.save(update_fields=["settings", "updated_by_user_id", "updated_at"])
        _audit(request, "TENANT_SETTINGS_UPDATED", "tenant_settings", str(tenant.id), after=_serialize_tenant(tenant))
        return Response({"tenant": _serialize_tenant(tenant)})


def _current_tenant() -> Tenant:
    return Tenant.objects.get(id=get_tenant_context().tenant_id)


def _permission_error(request, permission_code: str):
    tenant = _current_tenant()
    if not request.user.is_authenticated:
        return _error("AUTHENTICATION_REQUIRED", "Authentication required.", 401)
    if not TenantMembership.objects.filter(user=request.user, tenant=tenant, status=TenantMembership.Status.ACTIVE).exists():
        return _error("TENANT_MEMBERSHIP_REQUIRED", "Tenant membership required.", 403)
    if not has_permission(request.user, tenant, permission_code):
        return _error("PERMISSION_DENIED", "Permission denied.", 403)
    return None


def _tenant_membership(membership_id) -> TenantMembership:
    return TenantMembership.objects.get(id=membership_id, tenant=_current_tenant())


def _replace_roles(membership: TenantMembership, role_codes):
    if role_codes is None:
        return
    codes = [str(code).strip().upper() for code in role_codes if str(code).strip()]
    MembershipRole.objects.filter(membership=membership).delete()
    for role in Role.objects.filter(code__in=codes, scope=Role.Scope.TENANT, is_active=True):
        MembershipRole.objects.get_or_create(membership=membership, role=role)


def _replace_permissions(role: Role, permission_codes):
    RolePermission.objects.filter(role=role).delete()
    for code in [str(item).strip() for item in permission_codes if str(item).strip()]:
        permission, _ = Permission.objects.get_or_create(code=code)
        RolePermission.objects.get_or_create(role=role, permission=permission)


def _replace_warehouse_assignments(membership: TenantMembership, warehouse_codes):
    if warehouse_codes is None:
        return
    codes = [str(code).strip().upper() for code in warehouse_codes if str(code).strip()]
    WarehouseAssignment.objects.filter(membership=membership).exclude(warehouse_code__in=codes).update(is_active=False)
    for code in codes:
        WarehouseAssignment.objects.update_or_create(membership=membership, warehouse_code=code, defaults={"is_active": True})


def _serialize_membership(membership: TenantMembership) -> dict:
    return {
        "id": str(membership.id),
        "user_id": str(membership.user_id),
        "email": membership.user.email,
        "first_name": membership.user.first_name,
        "last_name": membership.user.last_name,
        "status": membership.status,
        "roles": sorted(membership.role_assignments.values_list("role__code", flat=True)),
        "warehouses": sorted(membership.warehouse_assignments.filter(is_active=True).values_list("warehouse_code", flat=True)),
        "created_at": membership.created_at.isoformat(),
        "updated_at": membership.updated_at.isoformat(),
    }


def _serialize_role(role: Role) -> dict:
    return {
        "id": str(role.id),
        "code": role.code,
        "name": role.name,
        "scope": role.scope,
        "is_active": role.is_active,
        "requires_mfa": role.requires_mfa,
        "permissions": sorted(role.permissions.values_list("code", flat=True)),
    }


def _serialize_tenant(tenant: Tenant) -> dict:
    return {
        "id": str(tenant.id),
        "tenant_code": tenant.tenant_code,
        "display_name": tenant.display_name,
        "status": tenant.status,
        "timezone": tenant.timezone,
        "default_language": tenant.default_language,
        "license_number": tenant.license_number,
    }


def _serialize_warehouse_control(control: WarehouseControl | None) -> dict | None:
    if control is None:
        return None
    return {"id": str(control.id), "scope": control.scope, "process": control.process, "settings": control.settings}


def _configuration_alert_count() -> int:
    return (
        int(not Warehouse.objects.filter(status="ACTIVE", is_active=True).exists())
        + Bay.objects.filter(is_blocked=True).count()
        + StorageType.objects.filter(is_active=False).count()
    )
