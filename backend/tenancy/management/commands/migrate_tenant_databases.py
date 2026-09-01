from __future__ import annotations

from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.conf import settings

from control.models import TenantDatabase
from tenancy.connections import register_tenant_database


class Command(BaseCommand):
    help = "Run tenant-plane migrations for ready tenant databases registered in the control plane."

    def add_arguments(self, parser):
        parser.add_argument("--tenant-code", help="Limit migration to one tenant code.")

    def handle(self, *args, **options):
        databases = TenantDatabase.objects.select_related("tenant").filter(
            provisioning_status=TenantDatabase.ProvisioningStatus.READY,
        )
        if options.get("tenant_code"):
            databases = databases.filter(tenant__tenant_code=options["tenant_code"])

        for tenant_database in databases.order_by("tenant__tenant_code"):
            alias = register_tenant_database(tenant_database)
            self.stdout.write(f"Migrating {tenant_database.tenant.tenant_code} using alias {alias}")
            for app_label in sorted(settings.LATTICE_TENANT_APPS):
                call_command("migrate", app_label, database=alias, verbosity=options["verbosity"])
