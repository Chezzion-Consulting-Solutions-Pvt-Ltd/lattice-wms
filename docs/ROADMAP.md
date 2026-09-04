# Lattice Roadmap

Status values: `NOT STARTED`, `IN PROGRESS`, `BLOCKED`, `COMPLETE`.

| Phase | Scope | Status | Evidence Required |
| --- | --- | --- | --- |
| Phase 0 | Repository, backend, frontend, Docker, CI, linting, tests, docs, AGENTS.md | IN PROGRESS | Scaffold exists and baseline checks run |
| Phase 1 | SaaS control plane: tenants, domains, DB metadata, plans, modules, features, identity membership, control audit | IN PROGRESS | Migrations and model tests pass |
| Phase 2 | Tenant DB infrastructure: provisioning, secrets abstraction, resolver, context, router, migrations, health | COMPLETE | Docker-backed Alpha/Beta tenant isolation suite passes |
| Phase 3 | Owner Console + Platform IAM: dashboard, tenant management, platform users, MFA, RBAC, permissions, warehouse scope, audit, security events | IN PROGRESS | Owner dashboard and IAM security tests pass |
| Phase 4 | Tenant Administration + Organizational Hierarchy: tenant-domain login, tenant shell, plants/sites, warehouses, zones, storage types, storage sections, bins/locations | IN PROGRESS | Tenant-domain auth, hierarchy CRUD, validation, audit, and isolation tests pass |
| Phase 5 | Tenant Master Data Foundation: products, UOM, partners, handling units, reason codes, inventory statuses, import/export | IN PROGRESS | Tenant DB-backed master-data tests pass |
| Phase 6 | Inbound | NOT STARTED | Master data tests pass |
| Phase 7 | Inventory | NOT STARTED | Ledger and race tests pass |
| Phase 8 | Outbound | NOT STARTED | Allocation/PGI idempotency tests pass |
| Phase 9 | Integrations | NOT STARTED | Idempotency, retry, webhook security tests pass |
| Phase 10 | Enterprise capabilities | NOT STARTED | SSO, SIEM, retention, DR automation evidence |

## Current Milestone: Lattice Owner Console Completion

Secure Core is complete and validated locally in Docker. The active milestone is completing the Owner / Platform Console before any additional Tenant Admin, warehouse hierarchy, master data, inbound, inventory, or outbound work.

Completed hardening in this milestone:

- Password-reset request/confirm APIs with generic request responses, hashed one-time expiring tokens, password validation, session revocation, and audit events.
- Login abuse controls with per-IP throttling, per-user counters, configurable temporary lockout, recovery after lockout, and suspicious-login hooks.
- Authoritative API session enforcement for revoked and expired tracked sessions.
- MFA hardening for new TOTP device secrets using encrypted secret envelopes and single-use hashed recovery codes.
- Docker healthchecks for backend, frontend, Celery, PostgreSQL, and Redis.
- Non-root backend/Celery container runtime.

Completed in the Owner Console gap-closure pass:

- Advanced tenant list API filters, tenant related-resource tabs, tenant domain management, and end-to-end provisioning orchestration.
- Platform role assignment UI, custom-role lifecycle, explicit per-permission Owner API enforcement, and missing-permission denial tests.
- Migration orchestration through the trusted tenant migration command with safe success/failure audit.
- Backup and restore execution hooks with fail-closed unconfigured state and verified `LOCAL_METADATA` drill provider.
- Comprehensive Docker-backed Owner Console tests and full backend validation: 103 passed with DB isolation enabled.

Still in progress for Owner Console + Platform IAM:

- Full UI page split from the remaining large legacy sections in `OwnerConsole.tsx`.
- Production DNS/HTTP domain verification provider.
- Production object-store/PITR backup and restore adapters.
- Confirmation dialogs for any remaining sensitive owner mutation surfaces not yet routed through shared lifecycle components.

Completed in the tenant/client authentication foundation:

- Separate Tenant Admin experience from the Platform Owner Console.
- Tenant-aware login context from active verified `TenantDomain`.
- Tenant-domain login with active tenant and active membership enforcement.
- Cross-tenant login denial with safe audit events.
- Tenant-bound `SecuritySession` records and tenant API session binding checks.
- JWT access/refresh login with Bearer-token API support, refresh endpoint, HttpOnly token cookies, and tenant-bound token session enforcement.
- Tenant context API returning safe tenant, module, role, permission, warehouse assignment, MFA, and configuration count data.

Still in progress for tenant/client authentication:

- Tenant invitation onboarding with one-time hashed tokens.
- Tenant admin MFA enrollment flow tied to invitations.
- Active plant/warehouse selector endpoint with backend authorization.
- Custom domain DNS/TLS verification workflow.
- Generic login and tenant discovery flow.
- SSO/OIDC/SAML provider integration readiness beyond current architecture rules.

Completed in the tenant administration and hierarchy milestone:

- Tenant database models and migrations for Plant, Warehouse, Zone, Storage Type, Storage Section, and Bin.
- Tenant-scoped API routes for list/create/detail/update of hierarchy records.
- Server-side hierarchy validation for cross-warehouse Zone, Storage Type, Section, and Bin references.
- Active warehouse context selection with active `WarehouseAssignment` enforcement.
- Tenant hierarchy browser API and frontend page.
- Real tenant admin frontend create/list pages for Plants, Warehouses, Zones, Storage Types, Sections, and Bins.
- Docker-backed hierarchy API tests for duplicate codes, optional Plant, invalid references, Bin block/unblock, cross-tenant denial, permission denial, and audit creation.

## Current Milestone: Lattice Tenant Master Data Foundation

Tenant Administration + Organizational Hierarchy remains in progress, but the next prioritized milestone is now tenant master data before operational WMS workflows.

Completed in the tenant master data foundation:

- Product Category tenant database model and migration.
- Product Category list/create/detail/update API under `/api/v1/tenant/product-categories/`.
- Product Category frontend page under `/tenant/product-categories`.
- Granular `masters.categories.view` and `masters.categories.manage` permissions.
- Product Category validation for duplicate category codes, self-parent, and cyclic parent hierarchy.
- Product Category audit events for create, update, and status changes.

Still pending in tenant master data:

- UOM, Products/SKU, UOM conversions, packaging, barcodes, vendors, customers, carriers, HU types, reason codes, inventory statuses, product storage rules, product warehouse configuration, import, and export.

Inbound, Putaway, Inventory Transactions, Picking, Packing, Outbound, and PGI remain blocked until the Tenant Master Data Foundation is complete.
