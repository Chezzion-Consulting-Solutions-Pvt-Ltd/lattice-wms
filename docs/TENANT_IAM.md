# Tenant IAM

Tenant IAM uses the existing `GlobalUser` and `TenantMembership` architecture.

Implemented:

- Tenant users list/invite/update
- Tenant role list/create/update with tenant permission assignment
- Tenant permission listing
- Warehouse assignment listing/update
- Server-side warehouse authorization for scoped configuration APIs

Passwords, password hashes, MFA secrets, recovery codes, tokens, tenant database aliases, and tenant database credentials are not exposed through tenant IAM responses.
