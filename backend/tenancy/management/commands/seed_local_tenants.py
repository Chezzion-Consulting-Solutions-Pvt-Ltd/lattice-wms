from __future__ import annotations

import os

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from control.models import Tenant, TenantDatabase, TenantDomain


class Command(BaseCommand):
    help = "Create local Tenant Alpha and Tenant Beta control-plane metadata."

    def handle(self, *args, **options):
        for code, host in (("alpha", "alpha.localhost"), ("beta", "beta.localhost")):
            tenant, _ = Tenant.objects.update_or_create(
                tenant_code=code,
                defaults={
                    "display_name": f"Tenant {code.title()}",
                    "status": Tenant.Status.ACTIVE,
                    "activated_at": timezone.now(),
                },
            )
            TenantDomain.objects.update_or_create(
                hostname=host,
                defaults={"tenant": tenant, "verified": True, "is_primary": True},
            )
            TenantDatabase.objects.update_or_create(
                tenant=tenant,
                defaults={
                    "database_alias": f"tenant_{code}",
                    "database_host_reference": getattr(settings, "POSTGRES_HOST", os.environ.get("POSTGRES_HOST", "postgres")),
                    "database_name": f"lattice_{code}",
                    "runtime_role_name": f"lattice_{code}_app",
                    "secret_reference": f"env:TENANT_{code.upper()}_DB_PASSWORD",
                    "sslmode": os.environ.get("POSTGRES_SSLMODE", "prefer"),
                    "provisioning_status": TenantDatabase.ProvisioningStatus.READY,
                },
            )
            self.stdout.write(self.style.SUCCESS(f"Seeded tenant_{code}"))
