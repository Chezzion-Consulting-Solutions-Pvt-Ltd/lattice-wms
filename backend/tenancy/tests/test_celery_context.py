from uuid import uuid4

import pytest

from tenancy.context import clear_tenant_context, get_tenant_context, tenant_context
from tenancy.exceptions import TenantContextError


def test_celery_like_task_context_does_not_leak_between_tasks():
    with tenant_context(
        tenant_id=uuid4(),
        tenant_code="alpha",
        database_alias="tenant_alpha",
        database_name="lattice_alpha",
        runtime_role_name="lattice_alpha_app",
    ):
        assert get_tenant_context().tenant_code == "alpha"
    clear_tenant_context()
    with tenant_context(
        tenant_id=uuid4(),
        tenant_code="beta",
        database_alias="tenant_beta",
        database_name="lattice_beta",
        runtime_role_name="lattice_beta_app",
    ):
        assert get_tenant_context().tenant_code == "beta"
    with pytest.raises(TenantContextError):
        get_tenant_context()
