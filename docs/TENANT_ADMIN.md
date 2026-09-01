# Tenant Admin

The Tenant Admin experience is separate from the Platform Owner Console. Tenant pages use `/tenant/*` frontend routes and `/api/v1/tenant/*` backend APIs.

Implemented tenant admin pages:

- `/tenant/dashboard`
- `/tenant/plants`
- `/tenant/warehouses`
- `/tenant/zones`
- `/tenant/storage-types`
- `/tenant/storage-sections`
- `/tenant/bins`
- `/tenant/hierarchy`
- `/tenant/users-access`
- `/tenant/settings`

Tenant admin APIs require authenticated cookie sessions, verified tenant domain resolution, active tenant membership, tenant-bound `SecuritySession`, and granular tenant permissions where mutations are performed.

Operational WMS flows such as receiving, inventory movement, picking, packing, loading, and PGI are intentionally not implemented in this milestone.
