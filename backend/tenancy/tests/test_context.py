from uuid import uuid4

import pytest

from tenancy.context import clear_tenant_context, get_tenant_context, tenant_context
from tenancy.exceptions import TenantContextError


def test_missing_tenant_context_fails_closed():
    clear_tenant_context()
    with pytest.raises(TenantContextError):
        get_tenant_context()


def test_tenant_context_cleans_up_after_block():
    with tenant_context(
        tenant_id=uuid4(),
        tenant_code="alpha",
        database_alias="tenant_alpha",
        database_name="lattice_alpha",
        runtime_role_name="lattice_alpha_app",
    ):
        assert get_tenant_context().tenant_code == "alpha"
    with pytest.raises(TenantContextError):
        get_tenant_context()
