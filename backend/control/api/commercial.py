from __future__ import annotations

from django.db import IntegrityError
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.views import APIView

from control.api.common import IsOwnerConsoleUser, bool_from_request, int_or_none, record_owner_audit, validation_error
from control.api.serializers import license_summary, plan_summary, subscription_summary
from control.models import License, Plan, PlanModule, Subscription, Tenant
from django.http import JsonResponse


class OwnerPlanListCreateView(APIView):
    throttle_scope = "admin_api"
    permission_classes = [IsOwnerConsoleUser]

    def get(self, request):
        plans = Plan.objects.prefetch_related("modules").order_by("code")
        return JsonResponse({"plans": [plan_summary(plan) for plan in plans]})

    def post(self, request):
        code = str(request.data.get("code", "")).strip().lower()
        name = str(request.data.get("name", "")).strip()
        if not code or not name:
            return validation_error("Plan code and name are required.")
        try:
            plan = Plan.objects.create(**plan_values(request.data, code=code, name=name))
            replace_plan_modules(plan, request.data.get("included_modules", []))
        except (IntegrityError, ValueError):
            return validation_error("Plan code must be unique and plan limits must be valid.", "PLAN_CONFLICT", status.HTTP_409_CONFLICT)
        record_owner_audit(request, "PLAN_CREATED", resource_type="Plan", resource_id=str(plan.id), after=plan_summary(plan))
        return JsonResponse({"plan": plan_summary(plan)}, status=status.HTTP_201_CREATED)


class OwnerPlanDetailView(APIView):
    throttle_scope = "admin_api"
    permission_classes = [IsOwnerConsoleUser]

    def patch(self, request, plan_id):
        plan = get_object_or_404(Plan.objects.prefetch_related("modules"), id=plan_id)
        before = plan_summary(plan)
        for field, value in plan_values(request.data).items():
            setattr(plan, field, value)
        try:
            plan.save()
            if "included_modules" in request.data:
                replace_plan_modules(plan, request.data.get("included_modules", []))
        except (IntegrityError, ValueError):
            return validation_error("Plan update is invalid.", "PLAN_UPDATE_INVALID")
        plan = get_object_or_404(Plan.objects.prefetch_related("modules"), id=plan_id)
        record_owner_audit(request, "PLAN_UPDATED", resource_type="Plan", resource_id=str(plan.id), before=before, after=plan_summary(plan))
        return JsonResponse({"plan": plan_summary(plan)})


class OwnerSubscriptionListCreateView(APIView):
    throttle_scope = "admin_api"
    permission_classes = [IsOwnerConsoleUser]

    def get(self, request):
        subscriptions = Subscription.objects.select_related("tenant", "plan").order_by("tenant__tenant_code")
        return JsonResponse({"subscriptions": [subscription_summary(subscription) for subscription in subscriptions]})

    def post(self, request):
        tenant = get_object_or_404(Tenant, id=request.data.get("tenant_id"))
        plan = get_object_or_404(Plan, id=request.data.get("plan_id"))
        starts_at = parse_datetime_or_now(request.data.get("starts_at"))
        status_value = str(request.data.get("status", Subscription.Status.ACTIVE))
        if status_value not in Subscription.Status.values:
            return validation_error("Unsupported subscription status.")
        subscription, created = Subscription.objects.update_or_create(
            tenant=tenant,
            defaults={
                "plan": plan,
                "status": status_value,
                "starts_at": starts_at,
                "renews_at": parse_datetime_or_none(request.data.get("renews_at")),
                "ends_at": parse_datetime_or_none(request.data.get("ends_at")),
                "trial_starts_at": parse_datetime_or_none(request.data.get("trial_starts_at")),
                "trial_ends_at": parse_datetime_or_none(request.data.get("trial_ends_at")),
                "is_active": status_value in {Subscription.Status.TRIAL, Subscription.Status.ACTIVE},
                "notes": str(request.data.get("notes", "")),
                "overrides": request.data.get("overrides", {}),
            },
        )
        record_owner_audit(request, "SUBSCRIPTION_CREATED" if created else "SUBSCRIPTION_UPDATED", resource_type="Subscription", resource_id=str(subscription.id), after=subscription_summary(subscription))
        return JsonResponse({"subscription": subscription_summary(subscription)}, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


class OwnerSubscriptionDetailView(APIView):
    throttle_scope = "admin_api"
    permission_classes = [IsOwnerConsoleUser]

    def patch(self, request, subscription_id):
        subscription = get_object_or_404(Subscription.objects.select_related("tenant", "plan"), id=subscription_id)
        before = subscription_summary(subscription)
        if "plan_id" in request.data:
            subscription.plan = get_object_or_404(Plan, id=request.data.get("plan_id"))
        if "status" in request.data:
            status_value = str(request.data.get("status"))
            if status_value not in Subscription.Status.values:
                return validation_error("Unsupported subscription status.")
            subscription.status = status_value
            subscription.is_active = status_value in {Subscription.Status.TRIAL, Subscription.Status.ACTIVE}
        for field in ["notes", "overrides"]:
            if field in request.data:
                setattr(subscription, field, request.data[field])
        subscription.save()
        record_owner_audit(request, "SUBSCRIPTION_UPDATED", resource_type="Subscription", resource_id=str(subscription.id), before=before, after=subscription_summary(subscription))
        return JsonResponse({"subscription": subscription_summary(subscription)})


class OwnerLicenseListView(APIView):
    throttle_scope = "admin_api"
    permission_classes = [IsOwnerConsoleUser]

    def get(self, request):
        ensure_licenses()
        licenses = License.objects.select_related("tenant", "plan").order_by("tenant__tenant_code")
        return JsonResponse({"licenses": [license_summary(license_record) for license_record in licenses]})


class OwnerLicenseActionView(APIView):
    throttle_scope = "admin_api"
    permission_classes = [IsOwnerConsoleUser]

    def post(self, request, license_id, action):
        license_record = get_object_or_404(License.objects.select_related("tenant", "plan"), id=license_id)
        before = license_summary(license_record)
        if action == "revoke":
            license_record.status = License.Status.REVOKED
            audit_action = "LICENSE_REVOKED"
        elif action == "reactivate":
            license_record.status = License.Status.ACTIVE
            audit_action = "LICENSE_REACTIVATED"
        elif action == "renew":
            days = int(request.data.get("days", 365) or 365)
            base = license_record.expires_at or timezone.now()
            license_record.expires_at = base + timezone.timedelta(days=days)
            license_record.status = License.Status.ACTIVE
            audit_action = "LICENSE_RENEWED"
        else:
            return validation_error("Unsupported license action.", "UNKNOWN_ACTION", status.HTTP_404_NOT_FOUND)
        license_record.save(update_fields=["status", "expires_at", "updated_at"])
        record_owner_audit(request, audit_action, resource_type="License", resource_id=str(license_record.id), before=before, after=license_summary(license_record))
        return JsonResponse({"license": license_summary(license_record)})


def plan_values(data, *, code: str | None = None, name: str | None = None) -> dict:
    values = {}
    if code is not None:
        values["code"] = code
    if name is not None:
        values["name"] = name
    field_map = {
        "description": str,
        "billing_interval": str,
        "support_tier": str,
    }
    for field, caster in field_map.items():
        if field in data:
            values[field] = caster(data.get(field, "")).strip()
    for field in ["user_limit", "warehouse_limit", "storage_limit_gb", "api_limit_per_month"]:
        if field in data:
            values[field] = int_or_none(data.get(field))
    if "active" in data:
        values["is_active"] = bool_from_request(data.get("active"))
    if "feature_entitlements" in data:
        values["feature_entitlements"] = data.get("feature_entitlements") or {}
    return values


def replace_plan_modules(plan: Plan, module_codes) -> None:
    PlanModule.objects.filter(plan=plan).delete()
    for module_code in module_codes or []:
        normalized = str(module_code).strip().lower()
        if normalized:
            PlanModule.objects.get_or_create(plan=plan, module_code=normalized)


def ensure_licenses() -> None:
    for tenant in Tenant.objects.all():
        License.objects.get_or_create(tenant=tenant, defaults={"license_number": tenant.license_number})


def parse_datetime_or_now(value):
    return parse_datetime_or_none(value) or timezone.now()


def parse_datetime_or_none(value):
    if not value:
        return None
    parsed = timezone.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed, timezone.get_current_timezone())
    return parsed
