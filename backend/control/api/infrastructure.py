from __future__ import annotations

from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.views import APIView

from control.api.common import IsOwnerConsoleUser, record_owner_audit, validation_error
from control.api.serializers import backup_policy_summary, backup_record_summary, database_summary, restore_request_summary
from control.models import BackupPolicy, BackupRecord, RestoreRequest, Tenant, TenantDatabase
from control.views import _service_health


class OwnerDatabasesView(APIView):
    throttle_scope = "admin_api"
    permission_classes = [IsOwnerConsoleUser]

    def get(self, request):
        tenants = Tenant.objects.select_related("database").order_by("tenant_code")
        return JsonResponse({"databases": [database_row(tenant) for tenant in tenants]})


class OwnerDatabaseHealthCheckView(APIView):
    throttle_scope = "admin_api"
    permission_classes = [IsOwnerConsoleUser]

    def post(self, request, tenant_id):
        tenant = get_object_or_404(Tenant.objects.select_related("database"), id=tenant_id)
        database = getattr(tenant, "database", None)
        if database is None:
            return validation_error("Tenant database is not configured.", "TENANT_DATABASE_MISSING", status.HTTP_409_CONFLICT)
        before = database_summary(database)
        database.last_health_check = timezone.now()
        database.health_status = TenantDatabase.HealthStatus.HEALTHY if database.provisioning_status == TenantDatabase.ProvisioningStatus.READY else TenantDatabase.HealthStatus.DEGRADED
        database.save(update_fields=["last_health_check", "health_status", "updated_at"])
        record_owner_audit(request, "TENANT_DATABASE_HEALTH_CHECKED", resource_type="TenantDatabase", resource_id=str(database.id), before=before, after=database_summary(database))
        return JsonResponse({"database": database_row(tenant)})


class OwnerMigrationsView(APIView):
    throttle_scope = "admin_api"
    permission_classes = [IsOwnerConsoleUser]

    def get(self, request):
        tenants = Tenant.objects.select_related("database").order_by("tenant_code")
        return JsonResponse({"migrations": [migration_row(tenant) for tenant in tenants]})


class OwnerBackupsView(APIView):
    throttle_scope = "admin_api"
    permission_classes = [IsOwnerConsoleUser]

    def get(self, request):
        tenants = Tenant.objects.prefetch_related("backup_records").order_by("tenant_code")
        rows = []
        for tenant in tenants:
            policy = getattr(tenant, "backup_policy", None)
            latest = tenant.backup_records.order_by("-finished_at", "-created_at").first()
            rows.append(
                {
                    "tenant_id": str(tenant.id),
                    "tenant": tenant.display_name,
                    "policy": backup_policy_summary(policy, tenant),
                    "latest_backup": backup_record_summary(latest) if latest else None,
                    "status": latest.status if latest else BackupRecord.Status.NOT_CONFIGURED,
                }
            )
        return JsonResponse({"backups": rows})


class OwnerBackupPolicyView(APIView):
    throttle_scope = "admin_api"
    permission_classes = [IsOwnerConsoleUser]

    def put(self, request, tenant_id):
        tenant = get_object_or_404(Tenant, id=tenant_id)
        provider = str(request.data.get("provider", "NOT_CONFIGURED")).strip() or "NOT_CONFIGURED"
        policy, _created = BackupPolicy.objects.update_or_create(
            tenant=tenant,
            defaults={
                "provider": provider,
                "retention_days": int(request.data.get("retention_days", 30) or 30),
                "region": str(request.data.get("region", tenant.region)).strip(),
                "enabled": provider != "NOT_CONFIGURED" and bool(request.data.get("enabled", False)),
            },
        )
        record_owner_audit(request, "BACKUP_POLICY_UPDATED", resource_type="BackupPolicy", resource_id=str(policy.id), after=backup_policy_summary(policy, tenant))
        return JsonResponse({"policy": backup_policy_summary(policy, tenant)})


class OwnerRestoreListCreateView(APIView):
    throttle_scope = "admin_api"
    permission_classes = [IsOwnerConsoleUser]

    def get(self, request):
        restores = RestoreRequest.objects.select_related("tenant", "backup", "requested_by", "approved_by").order_by("-requested_at")
        return JsonResponse({"restore_requests": [restore_request_summary(item) for item in restores]})

    def post(self, request):
        tenant = get_object_or_404(Tenant, id=request.data.get("tenant_id"))
        reason = str(request.data.get("reason", "")).strip()
        if not reason:
            return validation_error("Restore reason is required.")
        backup = None
        if request.data.get("backup_id"):
            backup = get_object_or_404(BackupRecord, id=request.data.get("backup_id"))
        restore_request = RestoreRequest.objects.create(tenant=tenant, backup=backup, reason=reason, requested_by=request.user)
        record_owner_audit(request, "RESTORE_REQUESTED", resource_type="RestoreRequest", resource_id=str(restore_request.id), after=restore_request_summary(restore_request))
        return JsonResponse({"restore_request": restore_request_summary(restore_request)}, status=status.HTTP_201_CREATED)


class OwnerServiceHealthView(APIView):
    throttle_scope = "admin_api"
    permission_classes = [IsOwnerConsoleUser]

    def get(self, request):
        tenant_databases = TenantDatabase.objects.all()
        return JsonResponse(
            {
                "generated_at": timezone.now().isoformat(),
                "services": _service_health(),
                "tenant_database_health": {
                    "total": tenant_databases.count(),
                    "healthy": tenant_databases.filter(health_status=TenantDatabase.HealthStatus.HEALTHY).count(),
                    "unavailable": tenant_databases.filter(health_status=TenantDatabase.HealthStatus.UNAVAILABLE).count(),
                },
            }
        )


def database_row(tenant: Tenant) -> dict:
    database = getattr(tenant, "database", None)
    row = database_summary(database)
    row.update({"tenant_id": str(tenant.id), "tenant": tenant.display_name, "tenant_code": tenant.tenant_code, "region": tenant.region})
    return row


def migration_row(tenant: Tenant) -> dict:
    database = getattr(tenant, "database", None)
    if database is None:
        return {"tenant_id": str(tenant.id), "tenant": tenant.display_name, "current_version": "", "target_version": "", "status": "BLOCKED", "safe_error_summary": "Tenant database is not configured."}
    status_value = "CURRENT" if database.migration_version else "PENDING"
    if database.provisioning_status == TenantDatabase.ProvisioningStatus.FAILED:
        status_value = "FAILED"
    return {"tenant_id": str(tenant.id), "tenant": tenant.display_name, "current_version": database.migration_version, "target_version": "", "status": status_value, "started_at": None, "finished_at": None, "safe_error_summary": ""}
