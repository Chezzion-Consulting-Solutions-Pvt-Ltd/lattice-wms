"""URL routes for Lattice."""
from django.contrib import admin
from django.urls import include, path

from lattice.views import live, ready

urlpatterns = [
    path("admin/", admin.site.urls),
    path("health/live", live, name="health-live"),
    path("health/ready", ready, name="health-ready"),
    path("api/v1/auth/", include("identity.urls")),
    path("api/v1/control/", include("control.urls")),
    path("api/v1/tenant/", include("tenancy.urls")),
]
