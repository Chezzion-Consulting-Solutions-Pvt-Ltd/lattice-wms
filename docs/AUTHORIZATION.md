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
