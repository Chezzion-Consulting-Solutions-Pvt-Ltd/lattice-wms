# Lattice Security Architecture

Lattice is designed around defense in depth. The first security boundary is tenant isolation: each client receives a dedicated PostgreSQL database and runtime database identity. Application logic adds request-local tenant context, authorization, audit logging, throttling, and safe error handling on top of that boundary.

## Trust Boundaries

- Browser to gateway: only HTTPS traffic is accepted in production.
- Gateway to Django: request IDs, host validation, size limits, security headers, and CSRF controls apply.
- Django control plane: stores SaaS metadata, global identity, tenant memberships, tenant database metadata, and secret references.
- Owner Console: reads and manages control-plane metadata only during normal platform-management operations.
- Django tenant plane: accesses tenant WMS data only through a resolved tenant context and strict database router.
- Redis/Celery: tasks must receive explicit tenant metadata and must clear context after execution.
- PostgreSQL: each tenant runtime role is restricted to that tenant database.
- Secret manager: tenant database passwords and external credentials are fetched through an abstraction by secret reference.
- Identity security: password-reset tokens are stored only as hashes; MFA secrets are stored in an encrypted envelope using configured secret material; recovery codes are stored only as password hashes.

## Required Request Flow

1. Assign a request ID.
2. Apply security middleware.
3. Authenticate the user.
4. Verify the tracked security session is present, unrevoked, and unexpired for API requests.
5. Verify tenant membership.
6. Resolve tenant from trusted server-side information.
7. Check tenant status.
8. Establish immutable tenant context.
9. Authorize the requested function and object.
10. Route tenant models to the tenant database.
11. Execute inside a transaction when state changes.
12. Create audit events for sensitive actions.
13. Clear tenant context.

Any missing or inconsistent tenant information fails closed.

## Owner Console Rules

- Owner dashboard pages must not directly query tenant WMS transaction databases.
- Tenant management, provisioning status, license numbers, plans, subscriptions, modules, feature flags, platform users, roles, permissions, MFA/security, audit logs, and service health are control-plane concerns.
- Platform support tenant-data access must use explicit grants with expiry and audit trails.
- No platform role grants a hidden bypass to tenant operational data.

## Client Input Rules

The following values are untrusted and must not select a database:

- `?database=...`
- `?db=...`
- `X-Database`
- `X-Tenant-ID`
- Request-body database names, aliases, hosts, usernames, schemas, or connection strings

## Error Handling

External API errors return a safe message, stable error code, and request ID. Internal logs may include technical details and tenant identifiers but must not include secrets.

## Login And Recovery Controls

- Password reset request responses are generic and do not reveal whether a user exists.
- Reset tokens are random, expire, are single-use, and are invalidated after successful reset.
- Successful password reset revokes the user's active tracked sessions.
- Login abuse protection combines per-IP throttling with per-user counters and temporary lockout for known users only.
- Attacker-controlled nonexistent usernames do not create permanent user lockouts.
