# Lattice Authorization

Authorization is enforced server-side and denied by default. Lattice will use granular permission codes, tenant membership, module flags, warehouse assignments, function-level authorization, and object-level authorization.

React route guards are only UX hints and must never be treated as security controls.

Implemented foundation:

- Role, Permission, RolePermission, and MembershipRole models.
- WarehouseAssignment by tenant membership and warehouse code, avoiding cross-database foreign keys.
- Reusable helpers for membership, permission, module, warehouse, and platform support access checks.
- Platform support tenant access grant model with explicit approver, reason, expiry, and revocation fields.
- Module-disabled authorization tests for backend permission helpers.

Platform support accounts do not receive hidden tenant-data access. Tenant access must be explicit, time-limited, and audited.

Pending for Platform IAM completion:

- Owner Console CRUD APIs for platform users, roles, permissions, role assignments, and support access grants.
- Staff/admin authorization policies around those CRUD endpoints.
## Tenant Hierarchy Permissions

Tenant hierarchy APIs deny by default when a required tenant-scoped permission is missing.

Implemented permission codes:

- `organization.hierarchy.view`
- `organization.plants.view`
- `organization.plants.manage`
- `organization.warehouses.view`
- `organization.warehouses.manage`
- `organization.zones.view`
- `organization.zones.manage`
- `organization.storage_types.view`
- `organization.storage_types.manage`
- `organization.sections.view`
- `organization.sections.manage`
- `organization.bins.view`
- `organization.bins.manage`

Active warehouse selection also requires an active `WarehouseAssignment` for the selected warehouse code.
