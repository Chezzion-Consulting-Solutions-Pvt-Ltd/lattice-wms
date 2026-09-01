import pytest

from tenancy.context import clear_tenant_context, tenant_context
from tenancy.db_router import LatticeDatabaseRouter
from tenancy.exceptions import TenantContextError
from warehouse.models import Warehouse


def test_tenant_model_without_context_does_not_fall_back_to_default():
    clear_tenant_context()
    router = LatticeDatabaseRouter()
    with pytest.raises(TenantContextError):
        router.db_for_read(Warehouse)


def test_tenant_model_routes_to_active_context():
    router = LatticeDatabaseRouter()
    with tenant_context(
        tenant_id="00000000-0000-0000-0000-000000000001",
        tenant_code="alpha",
        database_alias="tenant_alpha",
        database_name="lattice_alpha",
        runtime_role_name="lattice_alpha_app",
    ):
        assert router.db_for_read(Warehouse) == "tenant_alpha"
