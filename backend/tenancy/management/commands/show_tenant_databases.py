from __future__ import annotations

from django.core.management.base import BaseCommand

from control.models import TenantDatabase


class Command(BaseCommand):
    help = "Print safe tenant database registration metadata."

    def handle(self, *args, **options):
        rows = TenantDatabase.objects.select_related("tenant").order_by("tenant__tenant_code")
        for row in rows:
            self.stdout.write(
                "|".join(
                    [
                        row.tenant.tenant_code,
                        row.tenant.license_number,
                        row.database_alias,
                        row.database_name,
                        row.runtime_role_name,
                        row.secret_reference,
                        row.provisioning_status,
                    ]
                )
            )
