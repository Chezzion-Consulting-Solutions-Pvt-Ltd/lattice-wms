from __future__ import annotations

from django.http import JsonResponse
from rest_framework.views import APIView

from audit.models import AuditEvent
from control.api.common import IsOwnerConsoleUser, csv_response, record_owner_audit
from control.models import BackupRecord, License, Subscription, Tenant, TenantDatabase, TenantModule
from identity.models import PlatformTenantAccessGrant


class OwnerReportsView(APIView):
    throttle_scope = "admin_api"
    permission_classes = [IsOwnerConsoleUser]

    def get_required_permission(self, request):
        return "platform.reports.export" if request.GET.get("export") == "csv" or request.GET.get("format") == "csv" else "platform.reports.view"

    def get(self, request):
        report_type = request.GET.get("type", "tenant-status")
        rows = build_report(report_type)
        if request.GET.get("export") == "csv" or request.GET.get("format") == "csv":
            record_owner_audit(request, "EXPORT_CREATED", resource_type="OwnerReport", resource_id=report_type, after={"rows": len(rows)})
            headers = list(rows[0].keys()) if rows else ["status"]
            return csv_response(f"{report_type}.csv", headers, rows)
        return JsonResponse({"report_type": report_type, "rows": rows, "count": len(rows)})


def build_report(report_type: str) -> list[dict]:
    if report_type == "subscription":
        return [
            {"tenant": item.tenant.display_name, "tenant_code": item.tenant.tenant_code, "plan": item.plan.name, "status": item.status, "renews_at": item.renews_at or ""}
            for item in Subscription.objects.select_related("tenant", "plan").order_by("tenant__tenant_code")
        ]
    if report_type == "license-expiry":
        return [
            {"tenant": item.tenant.display_name, "tenant_code": item.tenant.tenant_code, "license_number": item.license_number, "status": item.status, "expires_at": item.expires_at or ""}
            for item in License.objects.select_related("tenant").order_by("expires_at", "tenant__tenant_code")
        ]
    if report_type == "module-adoption":
        return [
            {"tenant": item.tenant.display_name, "tenant_code": item.tenant.tenant_code, "module_code": item.module_code, "enabled": item.enabled, "source": item.source}
            for item in TenantModule.objects.select_related("tenant").order_by("tenant__tenant_code", "module_code")
        ]
    if report_type == "database-health":
        return [
            {"tenant": item.tenant.display_name, "tenant_code": item.tenant.tenant_code, "database": item.database_name, "health": item.health_status, "provisioning": item.provisioning_status}
            for item in TenantDatabase.objects.select_related("tenant").order_by("tenant__tenant_code")
        ]
    if report_type == "migration-compliance":
        return [
            {"tenant": item.tenant.display_name, "tenant_code": item.tenant.tenant_code, "migration_version": item.migration_version or "PENDING", "status": "CURRENT" if item.migration_version else "PENDING"}
            for item in TenantDatabase.objects.select_related("tenant").order_by("tenant__tenant_code")
        ]
    if report_type == "backup-compliance":
        return [
            {"tenant": tenant.display_name, "tenant_code": tenant.tenant_code, "status": latest.status if latest else BackupRecord.Status.NOT_CONFIGURED}
            for tenant, latest in ((tenant, tenant.backup_records.order_by("-finished_at", "-created_at").first()) for tenant in Tenant.objects.prefetch_related("backup_records").order_by("tenant_code"))
        ]
    if report_type == "platform-user-access":
        from django.contrib.auth import get_user_model

        return [{"email": user.email, "active": user.is_active, "staff": user.is_staff, "platform_admin": user.is_platform_admin, "mfa_required": user.mfa_required} for user in get_user_model().objects.order_by("email")]
    if report_type == "security-event":
        return [{"timestamp": item.timestamp, "action": item.action, "result": item.result, "request_id": item.request_id} for item in AuditEvent.objects.filter(result__in=[AuditEvent.Result.DENIED, AuditEvent.Result.FAILURE])[:100]]
    if report_type == "support-access":
        return [{"support_user": item.user.email, "tenant": item.tenant.display_name, "expires_at": item.expires_at, "revoked_at": item.revoked_at or ""} for item in PlatformTenantAccessGrant.objects.select_related("user", "tenant")[:100]]
    return [{"tenant": tenant.display_name, "tenant_code": tenant.tenant_code, "status": tenant.status, "region": tenant.region, "created_at": tenant.created_at} for tenant in Tenant.objects.order_by("tenant_code")]
