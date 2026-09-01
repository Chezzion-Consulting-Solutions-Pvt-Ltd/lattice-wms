from __future__ import annotations

from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.db import connection
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
import redis

from audit.models import AuditEvent
from control.models import Subscription, Tenant, TenantDatabase
from identity.models import Permission, PlatformTenantAccessGrant, Role
from lattice.celery import app as celery_app


class IsOwnerConsoleUser(IsAuthenticated):
    def has_permission(self, request, view) -> bool:
        user = getattr(request, "user", None)
        return bool(
            super().has_permission(request, view)
            and user
            and user.is_active
            and (user.is_staff or user.is_platform_admin or user.is_superuser)
        )


class OwnerDashboardView(APIView):
    throttle_scope = "admin_api"
    permission_classes = [IsOwnerConsoleUser]

    def get(self, request):
        tenants = Tenant.objects.prefetch_related("domains").select_related("database").order_by("tenant_code")
        tenant_health = [self._serialize_tenant(tenant) for tenant in tenants]
        active = Tenant.objects.filter(status=Tenant.Status.ACTIVE).count()
        suspended = Tenant.objects.filter(status=Tenant.Status.SUSPENDED).count()
        ready_databases = TenantDatabase.objects.filter(provisioning_status=TenantDatabase.ProvisioningStatus.READY).count()
        healthy_databases = TenantDatabase.objects.filter(health_status=TenantDatabase.HealthStatus.HEALTHY).count()
        database_warnings = TenantDatabase.objects.exclude(health_status=TenantDatabase.HealthStatus.HEALTHY).count()
        migration_warnings = TenantDatabase.objects.filter(migration_version="").count()
        active_support_grants = PlatformTenantAccessGrant.objects.filter(expires_at__gt=timezone.now(), revoked_at__isnull=True).count()
        security_events = AuditEvent.objects.filter(result__in=[AuditEvent.Result.DENIED, AuditEvent.Result.FAILURE])
        recent_security_events = [self._serialize_event(event) for event in security_events[:8]]
        recent_activity = [self._serialize_event(event) for event in AuditEvent.objects.all()[:8]]
        service_health = _service_health()

        return JsonResponse(
            {
                "generated_at": timezone.now().isoformat(),
                "summary": {
                    "total_tenants": tenants.count(),
                    "total_clients": tenants.count(),
                    "active_clients": active,
                    "active_tenants": active,
                    "suspended_clients": suspended,
                    "suspended_tenants": suspended,
                    "ready_databases": ready_databases,
                    "healthy_databases": healthy_databases,
                    "database_warnings": database_warnings,
                    "migration_warnings": migration_warnings,
                    "backup_warnings": None,
                    "backup_status": "NOT_IMPLEMENTED",
                    "license_count": Tenant.objects.exclude(license_number="").count(),
                    "active_users": get_user_model().objects.filter(is_active=True).count(),
                    "roles": Role.objects.count(),
                    "permissions": Permission.objects.count(),
                    "security_alerts": security_events.count(),
                    "active_support_grants": active_support_grants,
                },
                "tenant_health": tenant_health,
                "clients": tenant_health,
                "infrastructure": {
                    "database_health": "HEALTHY" if database_warnings == 0 else "DEGRADED",
                    "storage_usage": "NOT_IMPLEMENTED",
                    "backup_status": "NOT_IMPLEMENTED",
                    "migration_status": "CURRENT" if migration_warnings == 0 else "ATTENTION",
                    "service_health": "OK" if all(item["status"] == "OK" for item in service_health.values()) else "DEGRADED",
                },
                "platform_health": service_health,
                "recent_security_events": recent_security_events,
                "recent_activity": recent_activity,
                "subscription_license_attention": self._subscription_license_attention(tenant_health),
                "provisioning_activity": [tenant for tenant in tenant_health if tenant["database"]["provisioning_status"] != TenantDatabase.ProvisioningStatus.READY] if tenant_health else [],
            }
        )

    def _serialize_tenant(self, tenant: Tenant) -> dict[str, object]:
        domain = next((item.hostname for item in tenant.domains.all() if item.is_primary), "")
        database = getattr(tenant, "database", None)
        try:
            subscription = tenant.subscription
        except Subscription.DoesNotExist:
            subscription = None
        return {
            "id": str(tenant.id),
            "tenant_code": tenant.tenant_code,
            "display_name": tenant.display_name,
            "legal_name": tenant.legal_name,
            "license_number": tenant.license_number,
            "status": tenant.status,
            "primary_domain": domain,
            "region": tenant.region,
            "timezone": tenant.timezone,
            "default_language": tenant.default_language,
            "subscription_plan": subscription.plan.name if subscription else tenant.subscription_plan or "Unassigned",
            "subscription_status": "ACTIVE" if subscription and subscription.is_active else "UNASSIGNED",
            "created_at": tenant.created_at.isoformat(),
            "database": {
                "alias": "",
                "name": "",
                "runtime_role": "",
                "provisioning_status": "MISSING",
                "health_status": "MISSING",
                "migration_version": "",
                "last_health_check": None,
            }
            if database is None
            else {
                "alias": database.database_alias,
                "name": database.database_name,
                "runtime_role": database.runtime_role_name,
                "provisioning_status": database.provisioning_status,
                "health_status": database.health_status,
                "migration_version": database.migration_version,
                "last_health_check": database.last_health_check.isoformat() if database.last_health_check else None,
            },
        }

    def _serialize_event(self, event: AuditEvent) -> dict[str, object]:
        return {
            "event_id": str(event.event_id),
            "timestamp": event.timestamp.isoformat(),
            "action": event.action,
            "result": event.result,
            "resource_type": event.resource_type,
            "request_id": event.request_id,
            "failure_reason": event.failure_reason,
        }

    def _subscription_license_attention(self, tenants: list[dict[str, object]]) -> list[dict[str, object]]:
        return [
            {
                "tenant": tenant["display_name"],
                "tenant_code": tenant["tenant_code"],
                "license_number": tenant["license_number"],
                "subscription_status": tenant["subscription_status"],
            }
            for tenant in tenants
            if tenant["subscription_status"] != "ACTIVE"
        ]


class OwnerTenantListCreateView(APIView):
    throttle_scope = "admin_api"
    permission_classes = [IsOwnerConsoleUser]

    def get(self, request):
        tenants = Tenant.objects.prefetch_related("domains").select_related("database").order_by("tenant_code")
        return JsonResponse({"tenants": [serialize_tenant(tenant) for tenant in tenants]})

    def post(self, request):
        tenant_code = str(request.data.get("tenant_code", "")).strip().lower()
        display_name = str(request.data.get("display_name", "")).strip()
        if not tenant_code or not display_name:
            return JsonResponse(
                {"error": {"code": "VALIDATION_ERROR", "message": "Tenant code and display name are required."}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            tenant = Tenant.objects.create(
                tenant_code=tenant_code,
                display_name=display_name,
                legal_name=str(request.data.get("legal_name", "")).strip(),
                region=str(request.data.get("region", "")).strip(),
                timezone=str(request.data.get("timezone", "UTC")).strip() or "UTC",
                default_language=str(request.data.get("default_language", "en")).strip() or "en",
                subscription_plan=str(request.data.get("subscription_plan", "")).strip(),
            )
        except IntegrityError:
            return JsonResponse(
                {"error": {"code": "TENANT_CONFLICT", "message": "Tenant code already exists."}},
                status=status.HTTP_409_CONFLICT,
            )
        record_owner_audit(request, "TENANT_CREATE", tenant, after=tenant_audit_summary(tenant))
        return JsonResponse({"tenant": serialize_tenant(tenant)}, status=status.HTTP_201_CREATED)


class OwnerTenantDetailView(APIView):
    throttle_scope = "admin_api"
    permission_classes = [IsOwnerConsoleUser]

    def get(self, request, tenant_id):
        tenant = get_owner_tenant(tenant_id)
        return JsonResponse({"tenant": serialize_tenant(tenant)})

    def patch(self, request, tenant_id):
        tenant = get_owner_tenant(tenant_id)
        before = tenant_audit_summary(tenant)
        editable_fields = ["display_name", "legal_name", "region", "timezone", "default_language", "subscription_plan"]
        for field in editable_fields:
            if field in request.data:
                value = str(request.data.get(field, "")).strip()
                if field in {"display_name", "timezone", "default_language"} and not value:
                    return JsonResponse(
                        {"error": {"code": "VALIDATION_ERROR", "message": f"{field} cannot be blank."}},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                setattr(tenant, field, value)
        tenant.save(update_fields=[*editable_fields, "updated_at"])
        record_owner_audit(request, "TENANT_UPDATE", tenant, before=before, after=tenant_audit_summary(tenant))
        return JsonResponse({"tenant": serialize_tenant(tenant)})


class OwnerTenantStatusView(APIView):
    throttle_scope = "admin_api"
    permission_classes = [IsOwnerConsoleUser]

    def post(self, request, tenant_id, action):
        tenant = get_owner_tenant(tenant_id)
        before = tenant_audit_summary(tenant)
        if action == "activate":
            tenant.status = Tenant.Status.ACTIVE
            tenant.activated_at = timezone.now()
            tenant.suspended_at = None
            audit_action = "TENANT_ACTIVATE"
        elif action == "suspend":
            tenant.status = Tenant.Status.SUSPENDED
            tenant.suspended_at = timezone.now()
            audit_action = "TENANT_SUSPEND"
        else:
            return JsonResponse(
                {"error": {"code": "UNKNOWN_ACTION", "message": "Unsupported tenant status action."}},
                status=status.HTTP_404_NOT_FOUND,
            )
        tenant.save(update_fields=["status", "activated_at", "suspended_at", "updated_at"])
        record_owner_audit(request, audit_action, tenant, before=before, after=tenant_audit_summary(tenant))
        return JsonResponse({"tenant": serialize_tenant(tenant)})


def _service_health() -> dict[str, dict[str, object]]:
    return {
        "backend": {"status": "OK", "detail": "request served"},
        "postgresql": _postgres_health(),
        "redis": _redis_health(),
        "celery": _celery_health(),
    }


def _postgres_health() -> dict[str, object]:
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        return {"status": "OK", "detail": "control database reachable"}
    except Exception:
        return {"status": "DEGRADED", "detail": "control database check failed"}


def _redis_health() -> dict[str, object]:
    from django.conf import settings

    try:
        client = redis.Redis.from_url(settings.REDIS_URL, socket_connect_timeout=1, socket_timeout=1)
        return {"status": "OK" if client.ping() else "DEGRADED", "detail": "redis ping"}
    except Exception:
        return {"status": "DEGRADED", "detail": "redis check failed"}


def _celery_health() -> dict[str, object]:
    try:
        responses = celery_app.control.inspect(timeout=1).ping() or {}
        return {"status": "OK" if responses else "DEGRADED", "detail": f"{len(responses)} worker(s) responded"}
    except Exception:
        return {"status": "DEGRADED", "detail": "celery check failed"}


def get_owner_tenant(tenant_id) -> Tenant:
    return get_object_or_404(Tenant.objects.prefetch_related("domains").select_related("database"), id=tenant_id)


def serialize_tenant(tenant: Tenant) -> dict[str, object]:
    return OwnerDashboardView()._serialize_tenant(tenant)


def tenant_audit_summary(tenant: Tenant) -> dict[str, object]:
    return {
        "id": str(tenant.id),
        "tenant_code": tenant.tenant_code,
        "display_name": tenant.display_name,
        "license_number": tenant.license_number,
        "status": tenant.status,
        "region": tenant.region,
        "subscription_plan": tenant.subscription_plan,
    }


def record_owner_audit(request, action: str, tenant: Tenant, before: dict[str, object] | None = None, after: dict[str, object] | None = None) -> None:
    AuditEvent.objects.create(
        request_id=getattr(request, "request_id", ""),
        global_user_id=getattr(request.user, "id", None),
        action=action,
        resource_type="Tenant",
        resource_id=str(tenant.id),
        before_summary=before or {},
        after_summary=after or {},
        result=AuditEvent.Result.SUCCESS,
    )
