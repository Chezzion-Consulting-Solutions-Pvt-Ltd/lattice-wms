# Lattice Roadmap

Status values: `NOT STARTED`, `IN PROGRESS`, `BLOCKED`, `COMPLETE`.

| Phase | Scope | Status | Evidence Required |
| --- | --- | --- | --- |
| Phase 0 | Repository, backend, frontend, Docker, CI, linting, tests, docs, AGENTS.md | IN PROGRESS | Scaffold exists and baseline checks run |
| Phase 1 | SaaS control plane: tenants, domains, DB metadata, plans, modules, features, identity membership, control audit | IN PROGRESS | Migrations and model tests pass |
| Phase 2 | Tenant DB infrastructure: provisioning, secrets abstraction, resolver, context, router, migrations, health | COMPLETE | Docker-backed Alpha/Beta tenant isolation suite passes |
| Phase 3 | Owner Console + Platform IAM: dashboard, tenant management, platform users, MFA, RBAC, permissions, warehouse scope, audit, security events | IN PROGRESS | Owner dashboard and IAM security tests pass |
| Phase 4 | Tenant Administration + Organizational Hierarchy: tenant admin console, plants/sites, warehouses, zones, storage types, storage sections, bins/locations | IN PROGRESS | Tenant-scoped hierarchy CRUD, validation, audit, and isolation tests pass |
| Phase 5 | Inbound | NOT STARTED | Master data tests pass |
| Phase 6 | Inventory | NOT STARTED | Ledger and race tests pass |
| Phase 7 | Outbound | NOT STARTED | Allocation/PGI idempotency tests pass |
| Phase 8 | Integrations | NOT STARTED | Idempotency, retry, webhook security tests pass |
| Phase 9 | Enterprise capabilities | NOT STARTED | SSO, SIEM, retention, DR automation evidence |

## Current Milestone: Lattice Tenant Administration + Organizational Hierarchy

Secure Core is complete and validated locally in Docker. Owner Console dashboard access now starts from authenticated login. The active milestone is the tenant-side administrative foundation and physical warehouse hierarchy before any operational WMS functionality begins.

Completed hardening in this milestone:

- Password-reset request/confirm APIs with generic request responses, hashed one-time expiring tokens, password validation, session revocation, and audit events.
- Login abuse controls with per-IP throttling, per-user counters, configurable temporary lockout, recovery after lockout, and suspicious-login hooks.
- Authoritative API session enforcement for revoked and expired tracked sessions.
- MFA hardening for new TOTP device secrets using encrypted secret envelopes and single-use hashed recovery codes.
- Docker healthchecks for backend, frontend, Celery, PostgreSQL, and Redis.
- Non-root backend/Celery container runtime.

Still in progress for Owner Console + Platform IAM:

- Platform users, roles, permissions, role assignment, and support access administration APIs/UI.
- Tenant management CRUD and lifecycle screens.
- Plans, subscriptions, modules, feature flags, tenant modules, and tenant feature flag CRUD.
- Real control-plane dashboard tables for tenant health, recent security events, migration status, and backup status.

In progress for Tenant Administration + Organizational Hierarchy:

- Separate Tenant Admin experience from the Platform Owner Console.
- Tenant-scoped plants/sites, warehouses, zones, storage types, storage sections, and bins/locations.
- Tenant database-only storage for physical hierarchy records.
- Warehouse-scoped tenant admin authorization, status transitions, validation, audit events, and isolation tests.

Inbound, Putaway, Inventory Transactions, Picking, Packing, Outbound, and PGI remain blocked until the Tenant Administration + Organizational Hierarchy foundation is complete.
