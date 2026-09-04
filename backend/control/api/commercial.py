from __future__ import annotations

from django.db import IntegrityError
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.views import APIView

from control.api.common import IsOwnerConsoleUser, bool_from_request, int_or_none, record_owner_audit, validation_error
from control.api.modules import ensure_default_modules
from control.api.serializers import license_summary, plan_summary, subscription_summary
from control.models import FeatureFlag, License, ModuleDefinition, Plan, PlanModule, Subscription, Tenant


class OwnerPlanListCreateView(APIView):
    throttle_scope = "admin_api"
    permission_classes = [IsOwnerConsoleUser]
    required_permissions = {"GET": "platform.plans.view", "POST": "platform.plans.manage"}

    def get(self, request):
        plans = filter_plans(request)
        page, paginator, page_size = paginate_queryset(request, plans)
        return JsonResponse({"plans": [plan_summary(plan) for plan in page.object_list], "pagination": pagination_summary(page, paginator, page_size)})

    def post(self, request):
        code = str(request.data.get("code", "")).strip().lower()
        name = str(request.data.get("name", "")).strip()
        if not code or not name:
            return validation_error("Plan code and name are required.")
        if Plan.objects.filter(code=code).exists():
            return validation_error("Plan code must be unique.", "PLAN_CONFLICT", status.HTTP_409_CONFLICT)
        validation = validate_plan_payload(request.data)
        if validation:
            return validation
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
    required_permissions = {"GET": "platform.plans.view", "PATCH": "platform.plans.manage", "DELETE": "platform.plans.manage"}

    def get(self, request, plan_id):
        plan = get_object_or_404(Plan.objects.prefetch_related("modules"), id=plan_id)
        return JsonResponse({"plan": plan_summary(plan)})

    def patch(self, request, plan_id):
        plan = get_object_or_404(Plan.objects.prefetch_related("modules"), id=plan_id)
        before = plan_summary(plan)
        validation = validate_plan_payload(request.data, plan=plan)
        if validation:
            return validation
        for field, value in plan_values(request.data).items():
            setattr(plan, field, value)
        try:
            plan.save()
            if "included_modules" in request.data:
                replace_plan_modules(plan, request.data.get("included_modules", []))
        except (IntegrityError, ValueError):
            return validation_error("Plan update is invalid.", "PLAN_UPDATE_INVALID")
        plan = get_object_or_404(Plan.objects.prefetch_related("modules"), id=plan_id)
        after = plan_summary(plan)
        record_owner_audit(request, "PLAN_UPDATED", resource_type="Plan", resource_id=str(plan.id), before=before, after=after)
        if before["included_modules"] != after["included_modules"]:
            record_owner_audit(request, "PLAN_MODULES_CHANGED", resource_type="Plan", resource_id=str(plan.id), before=before, after=after)
        if before["feature_entitlements"] != after["feature_entitlements"]:
            record_owner_audit(request, "PLAN_FEATURES_CHANGED", resource_type="Plan", resource_id=str(plan.id), before=before, after=after)
        return JsonResponse({"plan": plan_summary(plan)})

    def delete(self, request, plan_id):
        plan = get_object_or_404(Plan, id=plan_id)
        if Subscription.objects.filter(plan=plan).exists():
            return validation_error("Plans referenced by subscriptions cannot be deleted. Deactivate the plan instead.", "PLAN_REFERENCED", status.HTTP_409_CONFLICT)
        return validation_error("Plans are not hard-deleted from the owner console. Deactivate the plan instead.", "PLAN_DELETE_DISABLED", status.HTTP_405_METHOD_NOT_ALLOWED)


class OwnerPlanActionView(APIView):
    throttle_scope = "admin_api"
    permission_classes = [IsOwnerConsoleUser]
    required_permission = "platform.plans.manage"

    def post(self, request, plan_id, action):
        plan = get_object_or_404(Plan.objects.prefetch_related("modules"), id=plan_id)
        before = plan_summary(plan)
        if action == "activate":
            plan.is_active = True
            audit_action = "PLAN_ACTIVATED"
        elif action == "deactivate":
            plan.is_active = False
            audit_action = "PLAN_DEACTIVATED"
        else:
            return validation_error("Unsupported plan action.", "UNKNOWN_ACTION", status.HTTP_404_NOT_FOUND)
        plan.save(update_fields=["is_active", "updated_at"])
        record_owner_audit(request, audit_action, resource_type="Plan", resource_id=str(plan.id), before=before, after=plan_summary(plan))
        return JsonResponse({"plan": plan_summary(plan)})


class OwnerSubscriptionListCreateView(APIView):
    throttle_scope = "admin_api"
    permission_classes = [IsOwnerConsoleUser]
    required_permissions = {"GET": "platform.subscriptions.view", "POST": "platform.subscriptions.manage"}

    def get(self, request):
        subscriptions = filter_subscriptions(request)
        page, paginator, page_size = paginate_queryset(request, subscriptions)
        return JsonResponse({"subscriptions": [subscription_summary(subscription) for subscription in page.object_list], "pagination": pagination_summary(page, paginator, page_size)})

    def post(self, request):
        tenant = get_object_or_404(Tenant, id=request.data.get("tenant_id"))
        plan = get_object_or_404(Plan, id=request.data.get("plan_id"))
        if not plan.is_active:
            return validation_error("New subscriptions require an active plan.", "PLAN_INACTIVE")
        starts_at = parse_datetime_or_now(request.data.get("starts_at"))
        status_value = str(request.data.get("status", Subscription.Status.ACTIVE))
        if status_value not in Subscription.Status.values:
            return validation_error("Unsupported subscription status.")
        validation = validate_subscription_dates(starts_at, parse_datetime_or_none(request.data.get("trial_ends_at")), parse_datetime_or_none(request.data.get("ends_at")))
        if validation:
            return validation
        if Subscription.objects.filter(tenant=tenant).exists():
            return validation_error("Tenant already has a current subscription. Update the existing subscription instead.", "SUBSCRIPTION_EXISTS", status.HTTP_409_CONFLICT)
        subscription, created = Subscription.objects.update_or_create(
            tenant=tenant,
            defaults={
                "plan": plan,
                "status": status_value,
                "starts_at": starts_at,
                "renews_at": parse_datetime_or_none(request.data.get("renewal_at") or request.data.get("renews_at")),
                "ends_at": parse_datetime_or_none(request.data.get("ends_at")),
                "trial_starts_at": parse_datetime_or_none(request.data.get("trial_starts_at")),
                "trial_ends_at": parse_datetime_or_none(request.data.get("trial_ends_at")),
                "is_active": status_value in {Subscription.Status.TRIAL, Subscription.Status.ACTIVE},
                "notes": str(request.data.get("notes", "")),
                "overrides": request.data.get("override_metadata", request.data.get("overrides", {})) or {},
            },
        )
        record_owner_audit(request, "SUBSCRIPTION_CREATED" if created else "SUBSCRIPTION_UPDATED", resource_type="Subscription", resource_id=str(subscription.id), after=subscription_summary(subscription))
        return JsonResponse({"subscription": subscription_summary(subscription)}, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


class OwnerSubscriptionDetailView(APIView):
    throttle_scope = "admin_api"
    permission_classes = [IsOwnerConsoleUser]
    required_permissions = {"GET": "platform.subscriptions.view", "PATCH": "platform.subscriptions.manage"}

    def get(self, request, subscription_id):
        subscription = get_object_or_404(Subscription.objects.select_related("tenant", "plan"), id=subscription_id)
        return JsonResponse({"subscription": subscription_summary(subscription)})

    def patch(self, request, subscription_id):
        subscription = get_object_or_404(Subscription.objects.select_related("tenant", "plan"), id=subscription_id)
        before = subscription_summary(subscription)
        if "plan_id" in request.data:
            plan = get_object_or_404(Plan, id=request.data.get("plan_id"))
            if not plan.is_active:
                return validation_error("Subscriptions can only move to an active plan.", "PLAN_INACTIVE")
            subscription.plan = plan
        if "status" in request.data:
            status_value = str(request.data.get("status"))
            if status_value not in Subscription.Status.values:
                return validation_error("Unsupported subscription status.")
            if not can_transition_subscription(subscription.status, status_value):
                return validation_error("Unsupported subscription status transition.", "INVALID_SUBSCRIPTION_TRANSITION")
            subscription.status = status_value
            subscription.is_active = status_value in {Subscription.Status.TRIAL, Subscription.Status.ACTIVE}
        if "starts_at" in request.data:
            subscription.starts_at = parse_datetime_or_now(request.data.get("starts_at"))
        if "trial_ends_at" in request.data:
            subscription.trial_ends_at = parse_datetime_or_none(request.data.get("trial_ends_at"))
        if "renewal_at" in request.data or "renews_at" in request.data:
            subscription.renews_at = parse_datetime_or_none(request.data.get("renewal_at") or request.data.get("renews_at"))
        if "ends_at" in request.data:
            subscription.ends_at = parse_datetime_or_none(request.data.get("ends_at"))
        if "notes" in request.data:
            subscription.notes = str(request.data.get("notes", ""))
        if "override_metadata" in request.data or "overrides" in request.data:
            subscription.overrides = request.data.get("override_metadata", request.data.get("overrides", {})) or {}
        validation = validate_subscription_dates(subscription.starts_at, subscription.trial_ends_at, subscription.ends_at)
        if validation:
            return validation
        subscription.save()
        after = subscription_summary(subscription)
        record_owner_audit(request, "SUBSCRIPTION_UPDATED", resource_type="Subscription", resource_id=str(subscription.id), before=before, after=after)
        if before["plan_id"] != after["plan_id"]:
            record_owner_audit(request, "SUBSCRIPTION_PLAN_CHANGED", resource_type="Subscription", resource_id=str(subscription.id), before=before, after=after)
        return JsonResponse({"subscription": subscription_summary(subscription)})


class OwnerSubscriptionActionView(APIView):
    throttle_scope = "admin_api"
    permission_classes = [IsOwnerConsoleUser]
    required_permission = "platform.subscriptions.manage"

    def post(self, request, subscription_id, action):
        subscription = get_object_or_404(Subscription.objects.select_related("tenant", "plan"), id=subscription_id)
        before = subscription_summary(subscription)
        action_map = {
            "activate": (Subscription.Status.ACTIVE, "SUBSCRIPTION_ACTIVATED"),
            "suspend": (Subscription.Status.SUSPENDED, "SUBSCRIPTION_SUSPENDED"),
            "cancel": (Subscription.Status.CANCELLED, "SUBSCRIPTION_CANCELLED"),
            "expire": (Subscription.Status.EXPIRED, "SUBSCRIPTION_EXPIRED"),
        }
        if action not in action_map:
            return validation_error("Unsupported subscription action.", "UNKNOWN_ACTION", status.HTTP_404_NOT_FOUND)
        target_status, audit_action = action_map[action]
        if not can_transition_subscription(subscription.status, target_status):
            return validation_error("Unsupported subscription status transition.", "INVALID_SUBSCRIPTION_TRANSITION")
        subscription.status = target_status
        subscription.is_active = target_status == Subscription.Status.ACTIVE
        if target_status in {Subscription.Status.CANCELLED, Subscription.Status.EXPIRED} and subscription.ends_at is None:
            subscription.ends_at = timezone.now()
        subscription.save(update_fields=["status", "is_active", "ends_at", "updated_at"])
        record_owner_audit(request, audit_action, resource_type="Subscription", resource_id=str(subscription.id), before=before, after=subscription_summary(subscription))
        return JsonResponse({"subscription": subscription_summary(subscription)})


class OwnerLicenseListView(APIView):
    throttle_scope = "admin_api"
    permission_classes = [IsOwnerConsoleUser]
    required_permissions = {"GET": "platform.licenses.view", "POST": "platform.licenses.manage"}

    def get(self, request):
        ensure_licenses()
        licenses = License.objects.select_related("tenant", "plan").order_by("tenant__tenant_code")
        return JsonResponse({"licenses": [license_summary(license_record) for license_record in licenses]})

    def post(self, request):
        tenant = get_object_or_404(Tenant, id=request.data.get("tenant_id"))
        if License.objects.filter(tenant=tenant).exists():
            return validation_error("Tenant already has a license record.", "LICENSE_EXISTS", status.HTTP_409_CONFLICT)
        plan = None
        if request.data.get("plan_id"):
            plan = get_object_or_404(Plan, id=request.data.get("plan_id"))
        license_record = License.objects.create(
            tenant=tenant,
            plan=plan,
            status=str(request.data.get("status", License.Status.ACTIVE)),
            expires_at=parse_datetime_or_none(request.data.get("expires_at")),
            metadata=request.data.get("metadata", {}) or {},
        )
        record_owner_audit(request, "LICENSE_ISSUED", resource_type="License", resource_id=str(license_record.id), after=license_summary(license_record))
        return JsonResponse({"license": license_summary(license_record)}, status=status.HTTP_201_CREATED)


class OwnerLicenseDetailView(APIView):
    throttle_scope = "admin_api"
    permission_classes = [IsOwnerConsoleUser]
    required_permissions = {"GET": "platform.licenses.view", "PATCH": "platform.licenses.manage"}

    def get(self, request, license_id):
        license_record = get_object_or_404(License.objects.select_related("tenant", "plan"), id=license_id)
        return JsonResponse({"license": license_summary(license_record)})

    def patch(self, request, license_id):
        license_record = get_object_or_404(License.objects.select_related("tenant", "plan"), id=license_id)
        before = license_summary(license_record)
        if "status" in request.data:
            status_value = str(request.data.get("status"))
            if status_value not in License.Status.values:
                return validation_error("Unsupported license status.")
            license_record.status = status_value
        if "plan_id" in request.data:
            license_record.plan = get_object_or_404(Plan, id=request.data.get("plan_id")) if request.data.get("plan_id") else None
        if "expires_at" in request.data:
            license_record.expires_at = parse_datetime_or_none(request.data.get("expires_at"))
        if "metadata" in request.data:
            license_record.metadata = request.data.get("metadata") or {}
        license_record.save(update_fields=["status", "plan", "expires_at", "metadata", "updated_at"])
        record_owner_audit(request, "LICENSE_UPDATED", resource_type="License", resource_id=str(license_record.id), before=before, after=license_summary(license_record))
        return JsonResponse({"license": license_summary(license_record)})


class OwnerLicenseActionView(APIView):
    throttle_scope = "admin_api"
    permission_classes = [IsOwnerConsoleUser]
    required_permission = "platform.licenses.manage"

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
    elif "name" in data:
        values["name"] = str(data.get("name", "")).strip()
    field_map = {
        "description": str,
        "billing_interval": str,
        "support_tier": str,
        "currency": str,
    }
    for field, caster in field_map.items():
        if field in data:
            values[field] = caster(data.get(field, "")).strip()
    for field in ["user_limit", "warehouse_limit", "storage_limit_gb", "api_limit_per_month"]:
        if field in data:
            values[field] = int_or_none(data.get(field))
    if "storage_limit" in data:
        values["storage_limit_gb"] = int_or_none(data.get("storage_limit"))
    if "api_limit" in data:
        values["api_limit_per_month"] = int_or_none(data.get("api_limit"))
    if "active" in data:
        values["is_active"] = bool_from_request(data.get("active"))
    if "is_active" in data:
        values["is_active"] = bool_from_request(data.get("is_active"))
    if "price_metadata" in data:
        values["price_metadata"] = data.get("price_metadata") or {}
    if "feature_entitlements" in data:
        values["feature_entitlements"] = data.get("feature_entitlements") or {}
    return values


def replace_plan_modules(plan: Plan, module_codes) -> None:
    PlanModule.objects.filter(plan=plan).delete()
    for module_code in module_codes or []:
        normalized = str(module_code).strip().lower()
        if normalized:
            PlanModule.objects.get_or_create(plan=plan, module_code=normalized)


def filter_plans(request):
    plans = Plan.objects.prefetch_related("modules").order_by("code")
    search = request.GET.get("search", "").strip()
    if search:
        plans = plans.filter(Q(code__icontains=search) | Q(name__icontains=search) | Q(description__icontains=search))
    active = request.GET.get("active", "")
    if active != "":
        plans = plans.filter(is_active=bool_from_request(active))
    allowed_sort_fields = {"code": "code", "name": "name", "active": "is_active", "created": "created_at", "updated": "updated_at"}
    direction = "-" if request.GET.get("direction") == "desc" else ""
    return plans.order_by(f"{direction}{allowed_sort_fields.get(request.GET.get('sort', 'code'), 'code')}")


def filter_subscriptions(request):
    subscriptions = Subscription.objects.select_related("tenant", "plan").order_by("tenant__tenant_code")
    search = request.GET.get("search", "").strip()
    if search:
        subscriptions = subscriptions.filter(Q(tenant__tenant_code__icontains=search) | Q(tenant__display_name__icontains=search) | Q(plan__name__icontains=search) | Q(plan__code__icontains=search))
    if request.GET.get("status"):
        subscriptions = subscriptions.filter(status=request.GET["status"])
    if request.GET.get("plan"):
        subscriptions = subscriptions.filter(Q(plan__code__icontains=request.GET["plan"]) | Q(plan__name__icontains=request.GET["plan"]))
    renewal = request.GET.get("renewal", "")
    if renewal == "overdue":
        subscriptions = subscriptions.filter(renews_at__lt=timezone.now())
    elif renewal == "upcoming":
        subscriptions = subscriptions.filter(renews_at__gte=timezone.now(), renews_at__lte=timezone.now() + timezone.timedelta(days=30))
    elif renewal == "ending":
        subscriptions = subscriptions.filter(ends_at__gte=timezone.now(), ends_at__lte=timezone.now() + timezone.timedelta(days=30))
    allowed_sort_fields = {"tenant": "tenant__display_name", "plan": "plan__name", "status": "status", "renewal": "renews_at", "created": "created_at", "updated": "updated_at"}
    direction = "-" if request.GET.get("direction") == "desc" else ""
    return subscriptions.order_by(f"{direction}{allowed_sort_fields.get(request.GET.get('sort', 'tenant'), 'tenant__display_name')}")


def paginate_queryset(request, queryset):
    page_size = min(max(int(request.GET.get("page_size", 25) or 25), 1), 100)
    paginator = Paginator(queryset, page_size)
    page_number = max(int(request.GET.get("page", 1) or 1), 1)
    return paginator.get_page(page_number), paginator, page_size


def pagination_summary(page, paginator, page_size: int) -> dict:
    return {"page": page.number, "page_size": page_size, "total": paginator.count, "pages": paginator.num_pages, "has_next": page.has_next(), "has_previous": page.has_previous()}


def validate_plan_payload(data, *, plan: Plan | None = None):
    if "billing_interval" in data and str(data.get("billing_interval")) not in Plan.BillingInterval.values:
        return validation_error("Unsupported billing interval.")
    if plan and "code" in data and Subscription.objects.filter(plan=plan).exists() and str(data.get("code", "")).strip().lower() != plan.code:
        return validation_error("Plan code cannot be changed after subscriptions reference it.", "PLAN_CODE_LOCKED")
    for field in ["user_limit", "warehouse_limit", "storage_limit", "storage_limit_gb", "api_limit", "api_limit_per_month"]:
        if field in data:
            value = int_or_none(data.get(field))
            if value is not None and value < 0:
                return validation_error("Plan limits must be zero or greater.")
    ensure_default_modules()
    module_codes = {str(code).strip().lower() for code in data.get("included_modules", []) or [] if str(code).strip()}
    if module_codes:
        valid_modules = set(ModuleDefinition.objects.filter(module_code__in=module_codes).values_list("module_code", flat=True))
        if module_codes - valid_modules:
            return validation_error("Included modules must reference known modules.", "UNKNOWN_MODULE")
    entitlement_keys = set((data.get("feature_entitlements") or {}).keys())
    if entitlement_keys:
        valid_features = set(FeatureFlag.objects.filter(code__in=entitlement_keys).values_list("code", flat=True))
        if entitlement_keys - valid_features:
            return validation_error("Feature entitlements must reference known feature flags.", "UNKNOWN_FEATURE")
    return None


def validate_subscription_dates(starts_at, trial_ends_at, ends_at):
    if trial_ends_at and trial_ends_at < starts_at:
        return validation_error("Trial end date cannot precede start date.")
    if ends_at and ends_at < starts_at:
        return validation_error("End date cannot precede start date.")
    return None


def can_transition_subscription(current_status: str, target_status: str) -> bool:
    if current_status == target_status:
        return True
    blocked = {
        Subscription.Status.CANCELLED: {Subscription.Status.ACTIVE, Subscription.Status.TRIAL},
        Subscription.Status.EXPIRED: {Subscription.Status.TRIAL},
    }
    return target_status not in blocked.get(current_status, set())


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
