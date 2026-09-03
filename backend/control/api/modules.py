from __future__ import annotations

from django.db import IntegrityError
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.views import APIView

from control.api.common import IsOwnerConsoleUser, bool_from_request, record_owner_audit, validation_error
from control.api.serializers import feature_summary, module_summary, tenant_feature_summary, tenant_module_summary
from control.models import FeatureFlag, ModuleDefinition, Tenant, TenantFeatureFlag, TenantModule


DEFAULT_MODULES = [
    ("masters", "Masters"),
    ("inbound", "Inbound"),
    ("inventory", "Inventory"),
    ("outbound", "Outbound"),
    ("reports", "Reports"),
    ("integrations", "Integrations"),
    ("rf", "RF"),
    ("administration", "Administration"),
]


class OwnerModuleListCreateView(APIView):
    throttle_scope = "admin_api"
    permission_classes = [IsOwnerConsoleUser]

    def get(self, request):
        ensure_default_modules()
        modules = ModuleDefinition.objects.order_by("display_order", "module_code")
        tenant_modules = TenantModule.objects.select_related("tenant").order_by("tenant__tenant_code", "module_code")
        return JsonResponse({"modules": [module_summary(module) for module in modules], "tenant_modules": [tenant_module_summary(item) for item in tenant_modules]})

    def post(self, request):
        code = str(request.data.get("module_code", "")).strip().lower()
        name = str(request.data.get("name", "")).strip()
        if not code or not name:
            return validation_error("Module code and name are required.")
        try:
            module = ModuleDefinition.objects.create(
                module_code=code,
                name=name,
                description=str(request.data.get("description", "")).strip(),
                active=bool_from_request(request.data.get("active"), True),
                display_order=int(request.data.get("display_order", 0) or 0),
                dependencies=request.data.get("dependencies", []),
            )
        except (IntegrityError, ValueError):
            return validation_error("Module code must be unique and valid.", "MODULE_CONFLICT", status.HTTP_409_CONFLICT)
        record_owner_audit(request, "MODULE_CREATED", resource_type="ModuleDefinition", resource_id=str(module.id), after=module_summary(module))
        return JsonResponse({"module": module_summary(module)}, status=status.HTTP_201_CREATED)


class OwnerModuleDetailView(APIView):
    throttle_scope = "admin_api"
    permission_classes = [IsOwnerConsoleUser]

    def patch(self, request, module_id):
        module = get_object_or_404(ModuleDefinition, id=module_id)
        before = module_summary(module)
        for field in ["name", "description"]:
            if field in request.data:
                setattr(module, field, str(request.data.get(field, "")).strip())
        if "active" in request.data:
            module.active = bool_from_request(request.data.get("active"), True)
        if "display_order" in request.data:
            module.display_order = int(request.data.get("display_order", 0) or 0)
        if "dependencies" in request.data:
            module.dependencies = request.data.get("dependencies") or []
        module.save()
        record_owner_audit(request, "MODULE_UPDATED", resource_type="ModuleDefinition", resource_id=str(module.id), before=before, after=module_summary(module))
        return JsonResponse({"module": module_summary(module)})


class OwnerTenantModuleView(APIView):
    throttle_scope = "admin_api"
    permission_classes = [IsOwnerConsoleUser]

    def post(self, request, tenant_id):
        tenant = get_object_or_404(Tenant, id=tenant_id)
        module_code = str(request.data.get("module_code", "")).strip().lower()
        if not module_code:
            return validation_error("Module code is required.")
        enabled = bool_from_request(request.data.get("enabled"), True)
        entitlement, created = TenantModule.objects.update_or_create(
            tenant=tenant,
            module_code=module_code,
            defaults={"enabled": enabled, "source": TenantModule.Source.OVERRIDE},
        )
        record_owner_audit(
            request,
            "MODULE_ENABLED" if enabled else "MODULE_DISABLED",
            resource_type="TenantModule",
            resource_id=str(entitlement.id),
            after=tenant_module_summary(entitlement),
        )
        return JsonResponse({"tenant_module": tenant_module_summary(entitlement)}, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


class OwnerFeatureListCreateView(APIView):
    throttle_scope = "admin_api"
    permission_classes = [IsOwnerConsoleUser]

    def get(self, request):
        flags = FeatureFlag.objects.order_by("code")
        overrides = TenantFeatureFlag.objects.select_related("tenant", "feature_flag").order_by("tenant__tenant_code", "feature_flag__code")
        return JsonResponse({"features": [feature_summary(flag) for flag in flags], "tenant_overrides": [tenant_feature_summary(item) for item in overrides]})

    def post(self, request):
        code = str(request.data.get("code", "")).strip().lower()
        if not code:
            return validation_error("Feature flag code is required.")
        try:
            flag = FeatureFlag.objects.create(
                code=code,
                name=str(request.data.get("name", code)).strip(),
                description=str(request.data.get("description", "")).strip(),
                enabled_by_default=bool_from_request(request.data.get("enabled_by_default"), False),
                environment_metadata=request.data.get("environment_metadata", {}),
            )
        except IntegrityError:
            return validation_error("Feature flag code must be unique.", "FEATURE_CONFLICT", status.HTTP_409_CONFLICT)
        record_owner_audit(request, "FEATURE_FLAG_CREATED", resource_type="FeatureFlag", resource_id=str(flag.id), after=feature_summary(flag))
        return JsonResponse({"feature": feature_summary(flag)}, status=status.HTTP_201_CREATED)


class OwnerFeatureDetailView(APIView):
    throttle_scope = "admin_api"
    permission_classes = [IsOwnerConsoleUser]

    def patch(self, request, feature_id):
        flag = get_object_or_404(FeatureFlag, id=feature_id)
        before = feature_summary(flag)
        for field in ["name", "description"]:
            if field in request.data:
                setattr(flag, field, str(request.data.get(field, "")).strip())
        if "enabled_by_default" in request.data:
            flag.enabled_by_default = bool_from_request(request.data.get("enabled_by_default"), False)
        if "environment_metadata" in request.data:
            flag.environment_metadata = request.data.get("environment_metadata") or {}
        flag.save()
        record_owner_audit(request, "FEATURE_FLAG_UPDATED", resource_type="FeatureFlag", resource_id=str(flag.id), before=before, after=feature_summary(flag))
        return JsonResponse({"feature": feature_summary(flag)})


class OwnerTenantFeatureView(APIView):
    throttle_scope = "admin_api"
    permission_classes = [IsOwnerConsoleUser]

    def post(self, request, tenant_id):
        tenant = get_object_or_404(Tenant, id=tenant_id)
        flag = get_object_or_404(FeatureFlag, id=request.data.get("feature_id"))
        override_state = str(request.data.get("override_state", TenantFeatureFlag.OverrideState.INHERIT))
        if override_state not in TenantFeatureFlag.OverrideState.values:
            return validation_error("Unsupported feature override state.")
        override, created = TenantFeatureFlag.objects.update_or_create(
            tenant=tenant,
            feature_flag=flag,
            defaults={"override_state": override_state, "enabled": override_state == TenantFeatureFlag.OverrideState.ENABLED},
        )
        record_owner_audit(request, "FEATURE_FLAG_UPDATED", resource_type="TenantFeatureFlag", resource_id=str(override.id), after=tenant_feature_summary(override))
        return JsonResponse({"tenant_feature": tenant_feature_summary(override)}, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


def ensure_default_modules() -> None:
    for index, (code, name) in enumerate(DEFAULT_MODULES, start=1):
        ModuleDefinition.objects.get_or_create(module_code=code, defaults={"name": name, "display_order": index})
