from django.urls import path

from tenancy.views import TenantProbeView

urlpatterns = [
    path("probe/", TenantProbeView.as_view(), name="tenant-probe"),
]
