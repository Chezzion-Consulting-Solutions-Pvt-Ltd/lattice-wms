from django.urls import path

from control.api.access import (
    OwnerMfaComplianceView,
    OwnerPermissionListView,
    OwnerPlatformUserDetailView,
    OwnerPlatformUserListCreateView,
    OwnerRoleDetailView,
    OwnerRoleListCreateView,
    OwnerSessionRevokeView,
    OwnerSessionsView,
    OwnerSupportAccessListCreateView,
    OwnerSupportAccessRevokeView,
)
from control.api.commercial import (
    OwnerLicenseActionView,
    OwnerLicenseListView,
    OwnerPlanDetailView,
    OwnerPlanListCreateView,
    OwnerSubscriptionDetailView,
    OwnerSubscriptionListCreateView,
)
from control.api.infrastructure import (
    OwnerBackupPolicyView,
    OwnerBackupsView,
    OwnerDatabaseHealthCheckView,
    OwnerDatabasesView,
    OwnerMigrationsView,
    OwnerRestoreListCreateView,
    OwnerServiceHealthView,
)
from control.api.modules import (
    OwnerFeatureDetailView,
    OwnerFeatureListCreateView,
    OwnerModuleDetailView,
    OwnerModuleListCreateView,
    OwnerTenantFeatureView,
    OwnerTenantModuleView,
)
from control.api.reports import OwnerReportsView
from control.api.security import OwnerAuditLogsView, OwnerSecurityEventsView
from control.api.settings import OwnerNotificationReadView, OwnerNotificationsMarkAllReadView, OwnerNotificationsView, OwnerSettingsView
from control.views import OwnerDashboardView, OwnerTenantDatabaseView, OwnerTenantDetailView, OwnerTenantListCreateView, OwnerTenantStatusView

urlpatterns = [
    path("owner/dashboard/", OwnerDashboardView.as_view(), name="owner-dashboard"),
    path("owner/tenants/", OwnerTenantListCreateView.as_view(), name="owner-tenants"),
    path("owner/tenants/<uuid:tenant_id>/", OwnerTenantDetailView.as_view(), name="owner-tenant-detail"),
    path("owner/tenants/<uuid:tenant_id>/database/", OwnerTenantDatabaseView.as_view(), name="owner-tenant-database"),
    path("owner/tenants/<uuid:tenant_id>/modules/", OwnerTenantModuleView.as_view(), name="owner-tenant-modules"),
    path("owner/tenants/<uuid:tenant_id>/features/", OwnerTenantFeatureView.as_view(), name="owner-tenant-features"),
    path("owner/tenants/<uuid:tenant_id>/<slug:action>/", OwnerTenantStatusView.as_view(), name="owner-tenant-status"),
    path("owner/plans/", OwnerPlanListCreateView.as_view(), name="owner-plans"),
    path("owner/plans/<int:plan_id>/", OwnerPlanDetailView.as_view(), name="owner-plan-detail"),
    path("owner/subscriptions/", OwnerSubscriptionListCreateView.as_view(), name="owner-subscriptions"),
    path("owner/subscriptions/<int:subscription_id>/", OwnerSubscriptionDetailView.as_view(), name="owner-subscription-detail"),
    path("owner/licenses/", OwnerLicenseListView.as_view(), name="owner-licenses"),
    path("owner/licenses/<uuid:license_id>/<slug:action>/", OwnerLicenseActionView.as_view(), name="owner-license-action"),
    path("owner/modules/", OwnerModuleListCreateView.as_view(), name="owner-modules"),
    path("owner/modules/<int:module_id>/", OwnerModuleDetailView.as_view(), name="owner-module-detail"),
    path("owner/features/", OwnerFeatureListCreateView.as_view(), name="owner-features"),
    path("owner/features/<int:feature_id>/", OwnerFeatureDetailView.as_view(), name="owner-feature-detail"),
    path("owner/users/", OwnerPlatformUserListCreateView.as_view(), name="owner-users"),
    path("owner/users/<uuid:user_id>/", OwnerPlatformUserDetailView.as_view(), name="owner-user-detail"),
    path("owner/roles/", OwnerRoleListCreateView.as_view(), name="owner-roles"),
    path("owner/roles/<int:role_id>/", OwnerRoleDetailView.as_view(), name="owner-role-detail"),
    path("owner/permissions/", OwnerPermissionListView.as_view(), name="owner-permissions"),
    path("owner/support-access/", OwnerSupportAccessListCreateView.as_view(), name="owner-support-access"),
    path("owner/support-access/<int:grant_id>/revoke/", OwnerSupportAccessRevokeView.as_view(), name="owner-support-access-revoke"),
    path("owner/infrastructure/databases/", OwnerDatabasesView.as_view(), name="owner-databases"),
    path("owner/infrastructure/databases/<uuid:tenant_id>/health-check/", OwnerDatabaseHealthCheckView.as_view(), name="owner-database-health-check"),
    path("owner/infrastructure/migrations/", OwnerMigrationsView.as_view(), name="owner-migrations"),
    path("owner/infrastructure/backups/", OwnerBackupsView.as_view(), name="owner-backups"),
    path("owner/infrastructure/backups/<uuid:tenant_id>/policy/", OwnerBackupPolicyView.as_view(), name="owner-backup-policy"),
    path("owner/infrastructure/restore/", OwnerRestoreListCreateView.as_view(), name="owner-restore"),
    path("owner/infrastructure/health/", OwnerServiceHealthView.as_view(), name="owner-service-health"),
    path("owner/security/events/", OwnerSecurityEventsView.as_view(), name="owner-security-events"),
    path("owner/security/audit/", OwnerAuditLogsView.as_view(), name="owner-audit-logs"),
    path("owner/security/sessions/", OwnerSessionsView.as_view(), name="owner-sessions"),
    path("owner/security/sessions/<uuid:session_id>/revoke/", OwnerSessionRevokeView.as_view(), name="owner-session-revoke"),
    path("owner/security/mfa/", OwnerMfaComplianceView.as_view(), name="owner-mfa-compliance"),
    path("owner/reports/", OwnerReportsView.as_view(), name="owner-reports"),
    path("owner/settings/", OwnerSettingsView.as_view(), name="owner-settings"),
    path("owner/notifications/", OwnerNotificationsView.as_view(), name="owner-notifications"),
    path("owner/notifications/mark-all-read/", OwnerNotificationsMarkAllReadView.as_view(), name="owner-notifications-mark-all-read"),
    path("owner/notifications/<uuid:notification_id>/read/", OwnerNotificationReadView.as_view(), name="owner-notification-read"),
]
