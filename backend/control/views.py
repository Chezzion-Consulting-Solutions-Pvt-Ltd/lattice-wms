from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.paginator import Paginator
from django.db import IntegrityError
from django.db import connection
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
import redis

from audit.models import AuditEvent
from control.api.serializers import (
    backup_policy_summary,
    backup_record_summary,
    domain_summary,
    license_summary,
    restore_request_summary,
    subscription_summary,
    support_access_summary,
    tenant_feature_summary,
    tenant_module_summary,
    tenant_summary,
)
from control.api.common import required_owner_permission, user_has_platform_permission
from control.models import BackupRecord, License, RestoreRequest, Subscription, Tenant, TenantDatabase, TenantFeatureFlag, TenantModule
from identity.models import Permission, PlatformTenantAccessGrant, Role
from lattice.celery import app as celery_app


class IsOwnerConsoleUser(IsAuthenticated):
    def has_permission(self, request, view) -> bool:
        user = getattr(request, "user", None)
        required_permission = required_owner_permission(request, view)
        return bool(
            super().has_permission(request, view)
            and user
            and user.is_active
            and (user.is_staff or user.is_platform_admin or user.is_superuser)
            and required_permission
            and user_has_platform_permission(user, required_permission)
        )


class OwnerDashboardView(APIView):
    throttle_scope = "admin_api"
    permission_classes = [IsOwnerConsoleUser]
    required_permission = "platform.dashboard.view"

    def get(self, request):
        tenants = Tenant.objects.prefetch_related("domains").select_related("database").order_by("tenant_code")
        tenant_health = [self._serialize_tenant(tenant) for tenant in tenants]
        active = Tenant.objects.filter(status=Tenant.Status.ACTIVE).count()
        suspended = Tenant.objects.filter(status=Tenant.Status.SUSPENDED).count()
        ready_databases = TenantDatabase.objects.filter(provisioning_status=TenantDatabase.ProvisioningStatus.READY).count()
        healthy_databases = TenantDatabase.objects.filter(health_status=TenantDatabase.HealthStatus.HEALTHY).count()
        database_warnings = TenantDatabase.objects.exclude(health_status=TenantDatabase.HealthStatus.HEALTHY).count()
        migration_warnings = TenantDatabase.objects.filter(migration_version="").count()
        backup_warnings = tenants.count() - BackupRecord.objects.filter(status=BackupRecord.Status.HEALTHY).values("tenant_id").distinct().count()
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
                    "backup_warnings": backup_warnings,
                    "backup_status": "HEALTHY" if backup_warnings == 0 else "NOT_CONFIGURED",
                    "license_count": License.objects.count() or Tenant.objects.exclude(license_number="").count(),
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
                    "storage_usage": "NOT_CONFIGURED",
                    "backup_status": "HEALTHY" if backup_warnings == 0 else "NOT_CONFIGURED",
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
                "host_reference": "",
                "port": 5432,
                "name": "",
                "runtime_role": "",
                "sslmode": "",
                "provisioning_status": "MISSING",
                "provisioning_step": "MISSING",
                "health_status": "MISSING",
                "migration_version": "",
                "last_health_check": None,
                "safe_error_summary": "",
            }
            if database is None
            else {
                "alias": database.database_alias,
                "host_reference": database.database_host_reference,
                "port": database.port,
                "name": database.database_name,
                "runtime_role": database.runtime_role_name,
                "sslmode": database.sslmode,
                "provisioning_status": database.provisioning_status,
                "provisioning_step": database.provisioning_step,
                "health_status": database.health_status,
                "migration_version": database.migration_version,
                "last_health_check": database.last_health_check.isoformat() if database.last_health_check else None,
                "safe_error_summary": database.safe_error_summary,
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
    required_permissions = {"GET": "platform.tenants.view", "POST": "platform.tenants.create"}

    def get(self, request):
        tenants = Tenant.objects.prefetch_related("domains").select_related("database").order_by("tenant_code")
        search = request.GET.get("search", "").strip()
        if search:
            tenants = tenants.filter(Q(tenant_code__icontains=search) | Q(display_name__icontains=search) | Q(legal_name__icontains=search) | Q(license_number__icontains=search) | Q(domains__hostname__icontains=search)).distinct()
        if request.GET.get("status"):
            tenants = tenants.filter(status=request.GET["status"])
        if request.GET.get("region"):
            tenants = tenants.filter(region=request.GET["region"])
        if request.GET.get("plan"):
            plan = request.GET["plan"]
            tenants = tenants.filter(Q(subscription_plan__icontains=plan) | Q(subscription__plan__code__icontains=plan) | Q(subscription__plan__name__icontains=plan)).distinct()
        if request.GET.get("database_health"):
            tenants = tenants.filter(database__health_status=request.GET["database_health"])

        allowed_sort_fields = {
            "tenant": "display_name",
            "tenant_code": "tenant_code",
            "status": "status",
            "region": "region",
            "created": "created_at",
            "database": "database__provisioning_status",
            "migration": "database__migration_version",
        }
        sort = request.GET.get("sort", "tenant_code")
        direction = "-" if request.GET.get("direction") == "desc" else ""
        tenants = tenants.order_by(f"{direction}{allowed_sort_fields.get(sort, 'tenant_code')}")

        page_size = min(max(int(request.GET.get("page_size", 25) or 25), 1), 100)
        paginator = Paginator(tenants, page_size)
        page_number = max(int(request.GET.get("page", 1) or 1), 1)
        page = paginator.get_page(page_number)
        return JsonResponse(
            {
                "tenants": [serialize_tenant(tenant) for tenant in page.object_list],
                "pagination": {
                    "page": page.number,
                    "page_size": page_size,
                    "total": paginator.count,
                    "pages": paginator.num_pages,
                    "has_next": page.has_next(),
                    "has_previous": page.has_previous(),
                },
            }
        )

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
        License.objects.get_or_create(tenant=tenant, defaults={"license_number": tenant.license_number})
        record_owner_audit(request, "TENANT_CREATED", tenant, after=tenant_audit_summary(tenant))
        return JsonResponse({"tenant": serialize_tenant(tenant)}, status=status.HTTP_201_CREATED)


class OwnerTenantDetailView(APIView):
    throttle_scope = "admin_api"
    permission_classes = [IsOwnerConsoleUser]
    required_permissions = {"GET": "platform.tenants.view", "PATCH": "platform.tenants.edit"}

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
        record_owner_audit(request, "TENANT_UPDATED", tenant, before=before, after=tenant_audit_summary(tenant))
        return JsonResponse({"tenant": serialize_tenant(tenant)})


class OwnerTenantRelatedView(APIView):
    throttle_scope = "admin_api"
    permission_classes = [IsOwnerConsoleUser]
    required_permission = "platform.tenants.view"

    def get(self, request, tenant_id):
        tenant = get_object_or_404(
            Tenant.objects.prefetch_related("domains", "modules", "feature_flags__feature_flag", "backup_records", "restore_requests").select_related(
                "database", "configuration", "subscription__plan", "license__plan", "backup_policy"
            ),
            id=tenant_id,
        )
        try:
            subscription = subscription_summary(tenant.subscription)
        except Subscription.DoesNotExist:
            subscription = None
        try:
            license_record = license_summary(tenant.license)
        except License.DoesNotExist:
            license_record = None
        backup_policy = getattr(tenant, "backup_policy", None)
        return JsonResponse(
            {
                "tenant": tenant_summary(tenant),
                "tabs": {
                    "domains": [domain_summary(domain) for domain in tenant.domains.order_by("-is_primary", "hostname")],
                    "subscription": subscription,
                    "license": license_record,
                    "modules": [tenant_module_summary(module) for module in TenantModule.objects.filter(tenant=tenant).order_by("module_code")],
                    "feature_flags": [tenant_feature_summary(flag) for flag in TenantFeatureFlag.objects.select_related("feature_flag").filter(tenant=tenant).order_by("feature_flag__code")],
                    "support_access": [
                        support_access_summary(grant)
                        for grant in PlatformTenantAccessGrant.objects.select_related("user", "tenant", "approved_by").filter(tenant=tenant).order_by("-created_at")[:20]
                    ],
                    "backups": {
                        "policy": backup_policy_summary(backup_policy, tenant),
                        "records": [backup_record_summary(record) for record in tenant.backup_records.order_by("-started_at", "-created_at")[:20]],
                    },
                    "restore_requests": [
                        restore_request_summary(item)
                        for item in RestoreRequest.objects.select_related("tenant", "backup", "requested_by", "approved_by").filter(tenant=tenant).order_by("-requested_at")[:20]
                    ],
                },
            }
        )


class OwnerTenantDatabaseView(APIView):
    throttle_scope = "admin_api"
    permission_classes = [IsOwnerConsoleUser]
    required_permission = "platform.infrastructure.manage"

    def put(self, request, tenant_id):
        tenant = get_owner_tenant(tenant_id)
        unsafe_fields = {"password", "database_password", "db_password", "connection_string", "dsn", "url"}
        if unsafe_fields & set(request.data.keys()):
            return JsonResponse(
                {"error": {"code": "UNSAFE_DATABASE_CONFIG", "message": "Store tenant credentials in a secret manager and submit only a secret reference."}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        required_fields = ["database_alias", "database_host_reference", "database_name", "runtime_role_name", "secret_reference"]
        current_database = getattr(tenant, "database", None)
        missing_fields = [field for field in required_fields if not str(request.data.get(field, getattr(current_database, field, "")) or "").strip()]
        if missing_fields:
            return JsonResponse(
                {"error": {"code": "VALIDATION_ERROR", "message": "Database alias, host reference, database name, runtime role, and secret reference are required."}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        before = database_audit_summary(current_database) if current_database else None
        database_values = {
            "database_alias": str(request.data.get("database_alias", getattr(current_database, "database_alias", ""))).strip().lower(),
            "database_host_reference": str(request.data.get("database_host_reference", getattr(current_database, "database_host_reference", ""))).strip(),
            "port": int(request.data.get("port", getattr(current_database, "port", 5432)) or 5432),
            "database_name": str(request.data.get("database_name", getattr(current_database, "database_name", ""))).strip(),
            "runtime_role_name": str(request.data.get("runtime_role_name", getattr(current_database, "runtime_role_name", ""))).strip(),
            "secret_reference": str(request.data.get("secret_reference", getattr(current_database, "secret_reference", ""))).strip(),
            "sslmode": str(request.data.get("sslmode", getattr(current_database, "sslmode", "require")) or "require").strip(),
            "migration_version": str(request.data.get("migration_version", getattr(current_database, "migration_version", ""))).strip(),
            "provisioning_status": str(request.data.get("provisioning_status", getattr(current_database, "provisioning_status", TenantDatabase.ProvisioningStatus.PENDING))).strip(),
            "health_status": str(request.data.get("health_status", getattr(current_database, "health_status", TenantDatabase.HealthStatus.UNKNOWN))).strip(),
        }
        if database_values["database_alias"] == "default":
            return JsonResponse(
                {"error": {"code": "VALIDATION_ERROR", "message": "Tenant database alias cannot be default."}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if database_values["provisioning_status"] not in TenantDatabase.ProvisioningStatus.values:
            return JsonResponse(
                {"error": {"code": "VALIDATION_ERROR", "message": "Unsupported provisioning status."}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if database_values["health_status"] not in TenantDatabase.HealthStatus.values:
            return JsonResponse(
                {"error": {"code": "VALIDATION_ERROR", "message": "Unsupported health status."}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            database, created = TenantDatabase.objects.update_or_create(tenant=tenant, defaults=database_values)
        except (IntegrityError, ValueError):
            return JsonResponse(
                {"error": {"code": "DATABASE_CONFIG_CONFLICT", "message": "Tenant database alias, name, and runtime role must be unique and valid."}},
                status=status.HTTP_409_CONFLICT,
            )

        record_owner_audit(
            request,
            "TENANT_DATABASE_CREATE" if created else "TENANT_DATABASE_UPDATE",
            tenant,
            before=before,
            after=database_audit_summary(database),
        )
        return JsonResponse({"tenant": serialize_tenant(get_owner_tenant(tenant.id))})


class OwnerTenantStatusView(APIView):
    throttle_scope = "admin_api"
    permission_classes = [IsOwnerConsoleUser]
    required_permission = "platform.tenants.suspend"

    def post(self, request, tenant_id, action):
        tenant = get_owner_tenant(tenant_id)
        before = tenant_audit_summary(tenant)
        reason = str(request.data.get("reason", "")).strip()
        if action == "activate":
            tenant.status = Tenant.Status.ACTIVE
            tenant.activated_at = timezone.now()
            tenant.suspended_at = None
            audit_action = "TENANT_ACTIVATED"
        elif action == "suspend":
            if not reason:
                return JsonResponse(
                    {"error": {"code": "VALIDATION_ERROR", "message": "A suspension reason is required."}},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            tenant.status = Tenant.Status.SUSPENDED
            tenant.suspended_at = timezone.now()
            audit_action = "TENANT_SUSPENDED"
        else:
            return JsonResponse(
                {"error": {"code": "UNKNOWN_ACTION", "message": "Unsupported tenant status action."}},
                status=status.HTTP_404_NOT_FOUND,
            )
        tenant.save(update_fields=["status", "activated_at", "suspended_at", "updated_at"])
        after = tenant_audit_summary(tenant)
        if reason:
            after["reason"] = reason[:240]
        record_owner_audit(request, audit_action, tenant, before=before, after=after)
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


def database_audit_summary(database: TenantDatabase | None) -> dict[str, object]:
    if database is None:
        return {}
    return {
        "database_alias": database.database_alias,
        "database_host_reference": database.database_host_reference,
        "port": database.port,
        "database_name": database.database_name,
        "runtime_role_name": database.runtime_role_name,
        "sslmode": database.sslmode,
        "migration_version": database.migration_version,
        "provisioning_status": database.provisioning_status,
        "provisioning_step": database.provisioning_step,
        "health_status": database.health_status,
        "safe_error_summary": database.safe_error_summary,
        "secret_reference_configured": bool(database.secret_reference),
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
