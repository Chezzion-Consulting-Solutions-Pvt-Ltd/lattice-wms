# Lattice Engineering Rules

Lattice is a generic enterprise SaaS Warehouse Management System. Do not add customer-specific names, logic, seed data, database names, screenshots, or test fixtures.

## Non-Negotiable Architecture

- Lattice uses database-per-client tenancy.
- Each tenant has a dedicated PostgreSQL database and a dedicated PostgreSQL runtime credential.
- PostgreSQL schemas and `tenant_id` columns in shared WMS tables are not the primary isolation boundary.
- The control database stores SaaS/control-plane data only. It must not store WMS transaction data.
- Tenant database credentials must never be stored as plaintext columns. Store only a secret reference.
- Tenant database roles must not be superusers and must not access other tenant databases.
- Tenant resolution is server-side and trusted. Never select a database from browser-provided database names, aliases, hosts, usernames, schemas, connection strings, request bodies, query parameters, or arbitrary headers.
- Lattice fails closed. Missing, suspended, inconsistent, or unauthorized tenant context must raise a controlled error and must never fall back to another/default tenant database.
- Tenant context must be request-local/task-local, explicitly established, immutable during normal execution, and cleared in `finally` logic.
- Tenant applications must route only to the authorized tenant database. Control-plane applications must route only to the control database.

## Security Rules

- Authorization is enforced on the server. React route guards are UX only.
- Authentication and authorization are separate.
- Use granular permissions, RBAC, warehouse scope checks, module checks, and object authorization.
- Deny by default.
- Every warehouse-scoped API must verify warehouse membership server-side.
- Every object lookup by ID must verify tenant ownership, warehouse authorization where applicable, and permission for the operation.
- Never commit secrets or production credentials.
- Never put sensitive tokens in browser local storage.
- Never log passwords, MFA secrets, recovery codes, database credentials, API tokens, OAuth secrets, JWT signing keys, cloud keys, environment values, or connection strings.
- MFA is mandatory for privileged administrators.
- CSRF protection is required for cookie-authenticated state-changing requests.
- Authenticated production CORS must not use wildcard origins.
- Production must use secure cookies, HSTS, HTTPS redirects where appropriate, frame protection, content-type protections, referrer policy, and a CSP strategy.

## Frontend Design Rules

- The approved Lattice Figma design is the visual source of truth. Frontend implementations must reuse centralized Lattice design tokens/components and must not introduce unrelated visual themes.
- The official frontend stack is React + TypeScript, Tailwind CSS, Radix UI primitives where useful, and the Lattice custom design system.
- Tailwind is an implementation utility, not the visual design system. Figma and Lattice semantic design tokens remain the visual source of truth.
- Radix UI provides accessible behavior primitives only. Wrap Radix primitives inside reusable Lattice components rather than importing them directly across feature pages.
- Do not duplicate colors, spacing, typography, shadows, or radii inside pages. Use the design-system tokens and shared components.
- Hiding navigation or actions in React is UX only. Backend authorization remains mandatory for user, tenant, warehouse, role, permission, and object checks.
- Data-heavy WMS screens should prioritize readable tables, controlled horizontal scrolling, collapsible filters, drawers, and adaptive navigation.
- Preserve accessibility: visible focus states, labels, keyboard navigation, meaningful button names, and non-color status indicators are required.

## WMS Integrity Rules

- Use Decimal for inventory quantities and money. Never use floating point for business quantities.
- Inventory-affecting operations must run in database transactions.
- Receiving/GR and PGI flows must be idempotent.
- Transactional WMS records should normally use status, cancellation, and audit trails rather than hard deletion.
- Cross-database foreign keys are prohibited. Tenant databases may reference global users only by immutable UUID.

## Audit And Observability

- Generate a request/correlation ID for every request.
- Sensitive operations must create structured audit records.
- Audit logs must be append-only in normal application flows.
- Logs and API errors must include safe request IDs but must not expose stack traces, SQL, database aliases, hostnames, secrets, internal paths, or environment variables to clients.
- Centralized logging, metrics, tracing, health checks, backup metadata, and tenant database health state are part of the platform design.

## Testing And Documentation

- Security tests are mandatory for tenant isolation, forged tenant headers, DB parameter attacks, missing tenant context, suspended tenants, warehouse authorization, function authorization, Celery context isolation, secrets logging, login abuse, object enumeration, duplicate GR/PGI, and inventory races.
- Do not mark a phase complete unless implementation, migrations, authorization tests, tenant-isolation tests, documentation, linting/type checks, and relevant security checks pass.
- Keep documentation synchronized with code.
- Maintain `docs/ROADMAP.md`, `docs/IMPLEMENTATION_STATUS.md`, and `docs/SECURITY_CHECKLIST.md` after meaningful work.
