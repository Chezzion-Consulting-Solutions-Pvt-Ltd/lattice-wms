"""Celery application for Lattice."""
import os

from celery import Celery
from celery.signals import task_postrun, task_prerun

from tenancy.context import clear_tenant_context, set_tenant_context

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "lattice.settings")

app = Celery("lattice")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()


@task_prerun.connect
def establish_task_tenant_context(task=None, kwargs=None, **_: object) -> None:
    """Set tenant context only when a trusted task envelope includes it."""
    tenant_context = (kwargs or {}).pop("_tenant_context", None)
    if tenant_context:
        set_tenant_context(**tenant_context)


@task_postrun.connect
def clear_task_tenant_context(**_: object) -> None:
    clear_tenant_context()
