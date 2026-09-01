# Warehouse Access

Warehouse access is enforced server-side.

Tenant membership is stored in the control database. Warehouse records live in tenant databases. `WarehouseAssignment` links an active tenant membership to an authorized warehouse code.

Implemented enforcement:

- Tenant APIs require verified host-based tenant context.
- Tenant APIs require active tenant membership.
- Tenant sessions are bound to the resolved tenant.
- Active warehouse selection verifies the selected warehouse exists in the current tenant DB and that the user has an active assignment for its code.
- Permission checks use tenant-scoped roles and permissions. Mutation endpoints deny by default when required permissions are missing.

Frontend route guards are UX only; backend authorization is authoritative.
