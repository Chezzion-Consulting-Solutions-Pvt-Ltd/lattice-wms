from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from control.models import Tenant, TenantMembership, TenantModule
from identity.models import MembershipRole, Permission, PlatformUserRole, Role, RolePermission, WarehouseAssignment


OWNER_EMAIL = "owner@lattice.local"
OWNER_PASSWORD = "LocalOwnerPass123!"
TENANT_PASSWORD = "LocalTenantPass123!"

TENANT_PERMISSION_CODES = (
    ("tenant.dashboard.view", "View tenant dashboard."),
    ("tenant.plants.view", "View tenant plants."),
    ("tenant.plants.manage", "Manage tenant plants."),
    ("tenant.warehouses.view", "View tenant warehouses."),
    ("tenant.warehouses.manage", "Manage tenant warehouses."),
    ("tenant.storage_types.view", "View tenant storage types."),
    ("tenant.storage_types.manage", "Manage tenant storage types."),
    ("tenant.zones.view", "View tenant zones."),
    ("tenant.zones.manage", "Manage tenant zones."),
    ("tenant.sections.view", "View tenant sections."),
    ("tenant.sections.manage", "Manage tenant sections."),
    ("tenant.bays.view", "View inventory bays."),
    ("tenant.bays.manage", "Manage inventory bays."),
    ("tenant.bays.bulk_create", "Bulk create inventory bays."),
    ("tenant.bays.import", "Import inventory bays."),
    ("tenant.bays.export", "Export inventory bays."),
    ("tenant.configuration.view", "View warehouse configuration."),
    ("tenant.configuration.manage", "Manage warehouse configuration."),
    ("tenant.users.view", "View tenant users."),
    ("tenant.users.manage", "Manage tenant users."),
    ("tenant.roles.view", "View tenant roles."),
    ("tenant.roles.manage", "Manage tenant roles."),
    ("tenant.settings.view", "View tenant settings."),
    ("tenant.settings.manage", "Manage tenant settings."),
    ("tenant.warehouse_assignments.view", "View tenant warehouse assignments."),
    ("tenant.warehouse_assignments.manage", "Manage tenant warehouse assignments."),
    ("masters.categories.view", "View product categories."),
    ("masters.categories.manage", "Manage product categories."),
    ("organization.hierarchy.view", "View tenant organization hierarchy."),
    ("organization.plants.view", "View plants."),
    ("organization.plants.manage", "Manage plants."),
    ("organization.warehouses.view", "View warehouses."),
    ("organization.warehouses.manage", "Manage warehouses."),
    ("organization.zones.view", "View warehouse zones."),
    ("organization.zones.manage", "Manage warehouse zones."),
    ("organization.storage_types.view", "View storage types."),
    ("organization.storage_types.manage", "Manage storage types."),
    ("organization.sections.view", "View storage sections."),
    ("organization.sections.manage", "Manage storage sections."),
    ("organization.bins.view", "View bins."),
    ("organization.bins.manage", "Manage bins."),
)


class Command(BaseCommand):
    help = "Create deterministic local-only users for owner and tenant portal testing."

    @transaction.atomic
    def handle(self, *args, **options):
        user_model = get_user_model()
        owner = self._create_owner_user(user_model)
        tenant_role = self._create_local_tenant_role()
        tenants = Tenant.objects.filter(tenant_code__in=("alpha", "beta")).order_by("tenant_code")

        if tenants.count() != 2:
            self.stdout.write(self.style.WARNING("Expected local tenants alpha and beta. Run seed_local_tenants first if either account is missing."))

        tenant_accounts: list[tuple[str, str, str]] = []
        for tenant in tenants:
            TenantModule.objects.get_or_create(tenant=tenant, module_code="wms", defaults={"enabled": True})
            email = f"{tenant.tenant_code}.admin@lattice.local"
            user, _ = user_model.objects.update_or_create(
                email=email,
                defaults={
                    "first_name": tenant.display_name,
                    "last_name": "Admin",
                    "is_active": True,
                    "is_staff": False,
                    "is_platform_admin": False,
                    "mfa_required": False,
                },
            )
            user.set_password(TENANT_PASSWORD)
            user.failed_login_count = 0
            user.locked_until = None
            user.save()

            membership, _ = TenantMembership.objects.update_or_create(
                user=user,
                tenant=tenant,
                defaults={"status": TenantMembership.Status.ACTIVE, "is_primary": True},
            )
            MembershipRole.objects.get_or_create(membership=membership, role=tenant_role)
            WarehouseAssignment.objects.update_or_create(
                membership=membership,
                warehouse_code="*",
                defaults={"is_active": True},
            )
            tenant_accounts.append((tenant.display_name, email, TENANT_PASSWORD))

        self.stdout.write(self.style.SUCCESS("Local test users are ready."))
        self.stdout.write(f"Owner Console: {OWNER_EMAIL} / {OWNER_PASSWORD}")
        for tenant_name, email, password in tenant_accounts:
            self.stdout.write(f"{tenant_name}: {email} / {password}")

    def _create_owner_user(self, user_model):
        owner, _ = user_model.objects.update_or_create(
            email=OWNER_EMAIL,
            defaults={
                "first_name": "Platform",
                "last_name": "Owner",
                "is_active": True,
                "is_staff": True,
                "is_platform_admin": False,
                "mfa_required": False,
            },
        )
        owner.set_password(OWNER_PASSWORD)
        owner.failed_login_count = 0
        owner.locked_until = None
        owner.save()
        platform_role = self._create_local_platform_role()
        PlatformUserRole.objects.get_or_create(user=owner, role=platform_role)
        return owner

    def _create_local_platform_role(self) -> Role:
        permissions = [
            "platform.dashboard.view",
            "platform.tenants.view",
            "platform.tenants.create",
            "platform.tenants.edit",
            "platform.tenants.suspend",
            "platform.tenants.provision",
            "platform.domains.view",
            "platform.domains.manage",
            "platform.plans.view",
            "platform.plans.manage",
            "platform.subscriptions.view",
            "platform.subscriptions.manage",
            "platform.licenses.view",
            "platform.licenses.manage",
            "platform.modules.view",
            "platform.modules.manage",
            "platform.features.view",
            "platform.features.manage",
            "platform.users.view",
            "platform.users.manage",
            "platform.roles.view",
            "platform.roles.manage",
            "platform.permissions.view",
            "platform.support_access.view",
            "platform.support_access.manage",
            "platform.infrastructure.view",
            "platform.infrastructure.manage",
            "platform.security.view",
            "platform.audit.view",
            "platform.reports.view",
            "platform.reports.export",
            "platform.settings.view",
            "platform.settings.manage",
            "platform.notifications.view",
            "platform.notifications.manage",
        ]
        role, _ = Role.objects.update_or_create(
            code="PLATFORM_ADMIN",
            defaults={"name": "Platform Admin", "scope": Role.Scope.PLATFORM, "requires_mfa": True, "is_active": True},
        )
        for code in permissions:
            permission, _ = Permission.objects.get_or_create(code=code)
            RolePermission.objects.get_or_create(role=role, permission=permission)
        return role

    def _create_local_tenant_role(self) -> Role:
        role, _ = Role.objects.update_or_create(
            code="LOCAL_TENANT_ADMIN",
            defaults={
                "name": "Local Tenant Admin",
                "scope": Role.Scope.TENANT,
                "requires_mfa": False,
            },
        )
        for code, description in TENANT_PERMISSION_CODES:
            permission, _ = Permission.objects.update_or_create(code=code, defaults={"description": description})
            RolePermission.objects.get_or_create(role=role, permission=permission)
        return role
