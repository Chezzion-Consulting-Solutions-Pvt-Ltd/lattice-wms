from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from tenancy.provisioning import build_provisioning_sql, build_tenant_database_plan


class Command(BaseCommand):
    help = "Provision a tenant database and runtime role. Dry-run by default."

    def add_arguments(self, parser):
        parser.add_argument("tenant_code")
        parser.add_argument("--secret-reference", required=True)
        parser.add_argument("--execute", action="store_true", help="Actually execute against PostgreSQL admin connection.")

    def handle(self, *args, **options):
        plan = build_tenant_database_plan(options["tenant_code"], options["secret_reference"])
        statements = build_provisioning_sql(plan)
        if options["execute"]:
            raise CommandError("Execution requires a dedicated admin connector implementation and is intentionally not wired to runtime credentials.")
        self.stdout.write(f"Tenant database plan for {options['tenant_code']}:")
        self.stdout.write(f"database={plan.database_name}")
        self.stdout.write(f"role={plan.runtime_role_name}")
        self.stdout.write(f"secret_reference={plan.secret_reference}")
        for statement in statements:
            self.stdout.write(statement.replace("PASSWORD %s", "PASSWORD <redacted>"))
