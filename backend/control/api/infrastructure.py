from __future__ import annotations

from importlib import import_module
from pathlib import Path

from django.conf import settings
from django.core.management import call_command
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.views import APIView

from control.api.common import IsOwnerConsoleUser, bool_from_request, record_owner_audit, validation_error
from control.api.serializers import backup_policy_summary, backup_record_summary, database_summary, restore_request_summary
from control.models import BackupPolicy, BackupRecord, OwnerNotification, RestoreRequest, Tenant, TenantDatabase
from control.views import _service_health


class OwnerDatabasesView(APIView):
    throttle_scope = "admin_api"
    permission_classes = [IsOwnerConsoleUser]
    required_permission = "platform.infrastructure.view"

    def get(self, request):
        tenants = Tenant.objects.select_related("database").order_by("tenant_code")
        return JsonResponse({"databases": [database_row(tenant) for tenant in tenants]})


class OwnerDatabaseHealthCheckView(APIView):
    throttle_scope = "admin_api"
    permission_classes = [IsOwnerConsoleUser]
    required_permission = "platform.infrastructure.manage"

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
    required_permissions = {"GET": "platform.infrastructure.view", "POST": "platform.infrastructure.manage"}

    def get(self, request):
        tenants = Tenant.objects.select_related("database").order_by("tenant_code")
        return JsonResponse({"migrations": [migration_row(tenant) for tenant in tenants]})

    def post(self, request):
        tenant = None
        tenant_code = ""
        if request.data.get("tenant_id"):
            tenant = get_object_or_404(Tenant.objects.select_related("database"), id=request.data.get("tenant_id"))
            tenant_code = tenant.tenant_code
        elif request.data.get("tenant_code"):
            tenant_code = str(request.data.get("tenant_code", "")).strip()
            tenant = get_object_or_404(Tenant.objects.select_related("database"), tenant_code=tenant_code)

        targets = TenantDatabase.objects.select_related("tenant").filter(provisioning_status=TenantDatabase.ProvisioningStatus.READY)
        if tenant is not None:
            targets = targets.filter(tenant=tenant)
        if not targets.exists():
            return validation_error("No ready tenant databases are available for migration.", "NO_READY_TENANT_DATABASES", status.HTTP_409_CONFLICT)

        target_version = tenant_migration_target_version()
        before = {str(item.id): database_summary(item) for item in targets}
        try:
            call_kwargs = {"verbosity": 0}
            if tenant_code:
                call_kwargs["tenant_code"] = tenant_code
            call_command("migrate_tenant_databases", **call_kwargs)
        except Exception:
            now = timezone.now()
            targets.update(safe_error_summary="Tenant migration orchestration failed.", health_status=TenantDatabase.HealthStatus.DEGRADED, last_health_check=now)
            for database in targets:
                database.refresh_from_db()
                OwnerNotification.objects.create(
                    notification_type=OwnerNotification.NotificationType.MIGRATION_FAILED,
                    title="Tenant migration failed",
                    message=f"Migration failed for {database.tenant.display_name}.",
                    source_type="TenantDatabase",
                    source_id=str(database.id),
                )
                record_owner_audit(request, "TENANT_MIGRATION_FAILED", resource_type="TenantDatabase", resource_id=str(database.id), before=before.get(str(database.id)), after=database_summary(database), result="FAILURE", failure_reason="tenant_migration_failed")
            return validation_error("Tenant migration orchestration failed.", "TENANT_MIGRATION_FAILED", status.HTTP_500_INTERNAL_SERVER_ERROR)

        now = timezone.now()
        targets.update(migration_version=target_version, safe_error_summary="", health_status=TenantDatabase.HealthStatus.HEALTHY, last_health_check=now)
        rows = []
        for database in targets:
            database.refresh_from_db()
            record_owner_audit(request, "TENANT_MIGRATION_RUN", resource_type="TenantDatabase", resource_id=str(database.id), before=before.get(str(database.id)), after=database_summary(database))
            rows.append(migration_row(database.tenant))
        return JsonResponse({"migrations": rows, "target_version": target_version})


class OwnerBackupsView(APIView):
    throttle_scope = "admin_api"
    permission_classes = [IsOwnerConsoleUser]
    required_permissions = {"GET": "platform.infrastructure.view", "POST": "platform.infrastructure.manage"}

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

    def post(self, request):
        tenant = get_object_or_404(Tenant, id=request.data.get("tenant_id"))
        policy = getattr(tenant, "backup_policy", None)
        if policy is None or not policy.enabled or policy.provider == BackupRecord.Status.NOT_CONFIGURED:
            record = BackupRecord.objects.create(
                tenant=tenant,
                provider=BackupRecord.Status.NOT_CONFIGURED,
                region=tenant.region,
                status=BackupRecord.Status.NOT_CONFIGURED,
                started_at=timezone.now(),
                finished_at=timezone.now(),
                safe_error_summary="Backup provider is not configured.",
            )
            record_owner_audit(request, "BACKUP_SKIPPED", resource_type="BackupRecord", resource_id=str(record.id), after=backup_record_summary(record), result="FAILURE", failure_reason="backup_provider_not_configured")
            return validation_error("Backup provider is not configured for this tenant.", "BACKUP_PROVIDER_NOT_CONFIGURED", status.HTTP_409_CONFLICT)
        if policy.provider != "LOCAL_METADATA":
            return validation_error("Configured backup provider is not available in this environment.", "BACKUP_PROVIDER_UNAVAILABLE", status.HTTP_409_CONFLICT)
        now = timezone.now()
        record = BackupRecord.objects.create(
            tenant=tenant,
            provider=policy.provider,
            region=policy.region or tenant.region,
            status=BackupRecord.Status.HEALTHY,
            started_at=now,
            finished_at=now,
            size_bytes=0,
            restore_point_reference=f"metadata:{tenant.id}:{int(now.timestamp())}",
        )
        record_owner_audit(request, "BACKUP_CREATED", resource_type="BackupRecord", resource_id=str(record.id), after=backup_record_summary(record))
        return JsonResponse({"backup": backup_record_summary(record)}, status=status.HTTP_201_CREATED)


class OwnerBackupPolicyView(APIView):
    throttle_scope = "admin_api"
    permission_classes = [IsOwnerConsoleUser]
    required_permission = "platform.infrastructure.manage"

    def put(self, request, tenant_id):
        tenant = get_object_or_404(Tenant, id=tenant_id)
        provider = str(request.data.get("provider", "NOT_CONFIGURED")).strip() or "NOT_CONFIGURED"
        policy, _created = BackupPolicy.objects.update_or_create(
            tenant=tenant,
            defaults={
                "provider": provider,
                "retention_days": int(request.data.get("retention_days", 30) or 30),
                "region": str(request.data.get("region", tenant.region)).strip(),
                "enabled": provider != "NOT_CONFIGURED" and bool_from_request(request.data.get("enabled"), False),
            },
        )
        record_owner_audit(request, "BACKUP_POLICY_UPDATED", resource_type="BackupPolicy", resource_id=str(policy.id), after=backup_policy_summary(policy, tenant))
        return JsonResponse({"policy": backup_policy_summary(policy, tenant)})


class OwnerRestoreListCreateView(APIView):
    throttle_scope = "admin_api"
    permission_classes = [IsOwnerConsoleUser]
    required_permissions = {"GET": "platform.infrastructure.view", "POST": "platform.infrastructure.manage"}

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


class OwnerRestoreActionView(APIView):
    throttle_scope = "admin_api"
    permission_classes = [IsOwnerConsoleUser]
    required_permission = "platform.infrastructure.manage"

    def post(self, request, restore_id, action):
        restore_request = get_object_or_404(RestoreRequest.objects.select_related("tenant", "backup", "requested_by", "approved_by"), id=restore_id)
        before = restore_request_summary(restore_request)
        if action == "approve":
            restore_request.status = RestoreRequest.Status.APPROVED
            restore_request.approved_by = request.user
            restore_request.approved_at = timezone.now()
            restore_request.safe_error_summary = ""
            restore_request.save(update_fields=["status", "approved_by", "approved_at", "safe_error_summary", "updated_at"])
            record_owner_audit(request, "RESTORE_APPROVED", resource_type="RestoreRequest", resource_id=str(restore_request.id), before=before, after=restore_request_summary(restore_request))
            return JsonResponse({"restore_request": restore_request_summary(restore_request)})
        if action != "execute":
            return validation_error("Unsupported restore action.", "UNKNOWN_ACTION", status.HTTP_404_NOT_FOUND)
        if restore_request.status != RestoreRequest.Status.APPROVED:
            return validation_error("Restore must be approved before execution.", "RESTORE_APPROVAL_REQUIRED", status.HTTP_409_CONFLICT)
        backup = restore_request.backup
        if backup is None or backup.status != BackupRecord.Status.HEALTHY:
            return fail_restore(request, restore_request, before, "A healthy backup is required before restore execution.", "RESTORE_BACKUP_REQUIRED")
        if backup.provider != "LOCAL_METADATA":
            return fail_restore(request, restore_request, before, "Configured restore provider is not available in this environment.", "RESTORE_PROVIDER_UNAVAILABLE")
        restore_request.status = RestoreRequest.Status.COMPLETED
        restore_request.safe_error_summary = ""
        restore_request.save(update_fields=["status", "safe_error_summary", "updated_at"])
        record_owner_audit(request, "RESTORE_COMPLETED", resource_type="RestoreRequest", resource_id=str(restore_request.id), before=before, after=restore_request_summary(restore_request))
        return JsonResponse({"restore_request": restore_request_summary(restore_request)})


class OwnerServiceHealthView(APIView):
    throttle_scope = "admin_api"
    permission_classes = [IsOwnerConsoleUser]
    required_permission = "platform.infrastructure.view"

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
        return {"tenant_id": str(tenant.id), "tenant": tenant.display_name, "current_version": "", "target_version": tenant_migration_target_version(), "status": "BLOCKED", "safe_error_summary": "Tenant database is not configured."}
    target_version = tenant_migration_target_version()
    status_value = "CURRENT" if database.migration_version == target_version and target_version else "PENDING"
    if database.provisioning_status == TenantDatabase.ProvisioningStatus.FAILED:
        status_value = "FAILED"
    return {"tenant_id": str(tenant.id), "tenant": tenant.display_name, "current_version": database.migration_version, "target_version": target_version, "status": status_value, "started_at": None, "finished_at": None, "safe_error_summary": database.safe_error_summary}


def tenant_migration_target_version() -> str:
    versions = []
    for app_label in sorted(getattr(settings, "LATTICE_TENANT_APPS", [])):
        try:
            migrations_module = import_module(f"{app_label}.migrations")
        except ModuleNotFoundError:
            continue
        migrations_path = Path(migrations_module.__file__).parent
        names = sorted(path.stem for path in migrations_path.glob("[0-9][0-9][0-9][0-9]_*.py"))
        if names:
            versions.append(f"{app_label}.{names[-1]}")
    return ",".join(versions)


def fail_restore(request, restore_request: RestoreRequest, before: dict, message: str, code: str):
    restore_request.status = RestoreRequest.Status.FAILED
    restore_request.safe_error_summary = message
    restore_request.save(update_fields=["status", "safe_error_summary", "updated_at"])
    OwnerNotification.objects.create(
        notification_type=OwnerNotification.NotificationType.BACKUP_FAILED,
        title="Restore execution failed",
        message=f"Restore failed for {restore_request.tenant.display_name}.",
        source_type="RestoreRequest",
        source_id=str(restore_request.id),
    )
    record_owner_audit(request, "RESTORE_FAILED", resource_type="RestoreRequest", resource_id=str(restore_request.id), before=before, after=restore_request_summary(restore_request), result="FAILURE", failure_reason=code.lower())
    return validation_error(message, code, status.HTTP_409_CONFLICT)
