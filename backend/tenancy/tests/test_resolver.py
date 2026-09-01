import pytest
from django.contrib.auth import get_user_model
from django.test import RequestFactory

from control.models import Tenant, TenantDatabase, TenantDomain, TenantMembership
from tenancy.exceptions import TenantResolutionError, TenantUnavailableError
from tenancy.resolver import TenantResolver


@pytest.mark.django_db
def test_resolves_verified_hostname_to_active_ready_tenant():
    tenant = Tenant.objects.create(tenant_code="alpha", display_name="Tenant Alpha", status=Tenant.Status.ACTIVE)
    TenantDomain.objects.create(tenant=tenant, hostname="alpha.localhost", verified=True, is_primary=True)
    TenantDatabase.objects.create(
        tenant=tenant,
        database_alias="tenant_alpha",
        database_host_reference="local-postgres",
        database_name="lattice_alpha",
        runtime_role_name="lattice_alpha_app",
        secret_reference="env:TENANT_ALPHA_DB_PASSWORD",
        provisioning_status=TenantDatabase.ProvisioningStatus.READY,
    )
    request = RequestFactory().get("/api/v1/tenant/probe/", HTTP_HOST="alpha.localhost")
    resolved = TenantResolver().resolve_request(request)
    assert resolved.tenant.tenant_code == "alpha"
    assert resolved.database.database_name == "lattice_alpha"


@pytest.mark.django_db
def test_alpha_user_is_allowed_for_alpha_tenant_membership():
    user = get_user_model().objects.create_user(email="alpha.user@example.test")
    tenant = Tenant.objects.create(tenant_code="alpha", display_name="Tenant Alpha", status=Tenant.Status.ACTIVE)
    TenantMembership.objects.create(user=user, tenant=tenant, status=TenantMembership.Status.ACTIVE)
    TenantDomain.objects.create(tenant=tenant, hostname="alpha.localhost", verified=True, is_primary=True)
    TenantDatabase.objects.create(
        tenant=tenant,
        database_alias="tenant_alpha",
        database_host_reference="local-postgres",
        database_name="lattice_alpha",
        runtime_role_name="lattice_alpha_app",
        secret_reference="env:TENANT_ALPHA_DB_PASSWORD",
        provisioning_status=TenantDatabase.ProvisioningStatus.READY,
    )
    request = RequestFactory().get("/api/v1/tenant/probe/", HTTP_HOST="alpha.localhost")
    request.global_user = user
    assert TenantResolver().resolve_request(request).tenant == tenant


@pytest.mark.django_db
def test_alpha_user_is_denied_for_beta_tenant_membership():
    user = get_user_model().objects.create_user(email="alpha.user@example.test")
    alpha = Tenant.objects.create(tenant_code="alpha", display_name="Tenant Alpha", status=Tenant.Status.ACTIVE)
    beta = Tenant.objects.create(tenant_code="beta", display_name="Tenant Beta", status=Tenant.Status.ACTIVE)
    TenantMembership.objects.create(user=user, tenant=alpha, status=TenantMembership.Status.ACTIVE)
    TenantDomain.objects.create(tenant=beta, hostname="beta.localhost", verified=True, is_primary=True)
    TenantDatabase.objects.create(
        tenant=beta,
        database_alias="tenant_beta",
        database_host_reference="local-postgres",
        database_name="lattice_beta",
        runtime_role_name="lattice_beta_app",
        secret_reference="env:TENANT_BETA_DB_PASSWORD",
        provisioning_status=TenantDatabase.ProvisioningStatus.READY,
    )
    request = RequestFactory().get("/api/v1/tenant/probe/", HTTP_HOST="beta.localhost")
    request.global_user = user
    with pytest.raises(TenantResolutionError):
        TenantResolver().resolve_request(request)


@pytest.mark.django_db
def test_forged_tenant_header_is_rejected():
    request = RequestFactory().get("/api/v1/tenant/probe/", HTTP_HOST="alpha.localhost", HTTP_X_TENANT_ID="beta")
    with pytest.raises(TenantResolutionError):
        TenantResolver().resolve_request(request)


@pytest.mark.django_db
def test_database_query_parameter_is_rejected():
    request = RequestFactory().get("/api/v1/tenant/probe/?database=lattice_beta", HTTP_HOST="alpha.localhost")
    with pytest.raises(TenantResolutionError):
        TenantResolver().resolve_request(request)


@pytest.mark.django_db
def test_suspended_tenant_is_denied():
    tenant = Tenant.objects.create(tenant_code="alpha", display_name="Tenant Alpha", status=Tenant.Status.SUSPENDED)
    TenantDomain.objects.create(tenant=tenant, hostname="alpha.localhost", verified=True, is_primary=True)
    request = RequestFactory().get("/api/v1/tenant/probe/", HTTP_HOST="alpha.localhost")
    with pytest.raises(TenantUnavailableError):
        TenantResolver().resolve_request(request)


@pytest.mark.django_db
def test_missing_tenant_database_mapping_never_falls_back():
    tenant = Tenant.objects.create(tenant_code="alpha", display_name="Tenant Alpha", status=Tenant.Status.ACTIVE)
    TenantDomain.objects.create(tenant=tenant, hostname="alpha.localhost", verified=True, is_primary=True)
    request = RequestFactory().get("/api/v1/tenant/probe/", HTTP_HOST="alpha.localhost")
    with pytest.raises(TenantUnavailableError):
        TenantResolver().resolve_request(request)
