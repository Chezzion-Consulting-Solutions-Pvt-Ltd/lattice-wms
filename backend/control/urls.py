from django.urls import path

from control.views import OwnerDashboardView, OwnerTenantDatabaseView, OwnerTenantDetailView, OwnerTenantListCreateView, OwnerTenantStatusView

urlpatterns = [
    path("owner/dashboard/", OwnerDashboardView.as_view(), name="owner-dashboard"),
    path("owner/tenants/", OwnerTenantListCreateView.as_view(), name="owner-tenants"),
    path("owner/tenants/<uuid:tenant_id>/", OwnerTenantDetailView.as_view(), name="owner-tenant-detail"),
    path("owner/tenants/<uuid:tenant_id>/database/", OwnerTenantDatabaseView.as_view(), name="owner-tenant-database"),
    path("owner/tenants/<uuid:tenant_id>/<slug:action>/", OwnerTenantStatusView.as_view(), name="owner-tenant-status"),
]
