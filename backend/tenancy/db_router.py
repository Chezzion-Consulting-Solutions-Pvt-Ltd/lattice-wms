from __future__ import annotations

from django.conf import settings

from tenancy.context import get_tenant_context


class LatticeDatabaseRouter:
    """Route control apps to control DB and tenant apps to active tenant DB."""

    def db_for_read(self, model, **hints):
        return self._route(model)

    def db_for_write(self, model, **hints):
        return self._route(model)

    def allow_relation(self, obj1, obj2, **hints):
        if obj1._state.db and obj2._state.db:
            return obj1._state.db == obj2._state.db
        return None

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        if app_label in settings.LATTICE_CONTROL_APPS:
            return db == "default"
        if app_label in settings.LATTICE_TENANT_APPS:
            return db != "default"
        return db == "default"

    def _route(self, model):
        app_label = model._meta.app_label
        if app_label in settings.LATTICE_CONTROL_APPS:
            return "default"
        if app_label in settings.LATTICE_TENANT_APPS:
            return get_tenant_context().database_alias
        return "default"
