# Lattice Implementation Status

## 2026-09-03

### Implemented

- Expanded the Owner Console control-plane data model with dedicated license records, module definitions, backup policy/record metadata, restore requests, platform settings, and owner notifications.
- Added owner API modules under `control/api/` for commercial administration, modules/features, platform access, infrastructure, security/audit, reports, settings, and notifications.
- Added clean `/api/v1/control/owner/` routes for plans, subscriptions, licenses, modules, feature flags, platform users, roles, permissions, support access, tenant databases, migrations, backups, restore, service health, security events, audit logs, sessions, MFA compliance, reports, settings, and notifications.
- Updated tenant creation to create a first-class `License` record and to audit with the requested `TENANT_CREATED`, `TENANT_UPDATED`, `TENANT_ACTIVATED`, and `TENANT_SUSPENDED` names.
- Replaced Owner Console grouped placeholder routes with direct page routes backed by real owner APIs.
- Updated the Owner navigation and notification bell so Owner links resolve to functional data-backed pages.
- Changed local backup reporting from `NOT_IMPLEMENTED` to truthful `NOT_CONFIGURED` metadata unless a real backup provider exists.

### Validation Executed

- `.venv\Scripts\python.exe backend\manage.py check`: passed.
- `.venv\Scripts\python.exe backend\manage.py makemigrations --check`: passed with no model changes pending; local Postgres credential check still warns.
- `frontend npm.cmd run build`: passed.
- `frontend npm.cmd run lint`: passed.
- Focused owner pytest was attempted but blocked before assertions because local PostgreSQL rejects `lattice_control_app` credentials.

### Known Limitations

- Owner Console is not complete. Full tenant provisioning, domain verification, migration orchestration, backup provider execution, restore execution, advanced table filters, confirmation dialogs on every sensitive action, and comprehensive owner tests remain in progress.
- Local database-backed validation is blocked until the PostgreSQL credentials/runtime are repaired.
- Tenant Admin hierarchy, master data expansion, inbound, inventory, and outbound remain out of scope for this Owner Console milestone.

## 2026-09-01

### Implemented

- Began the Lattice Tenant Master Data Foundation with Product Categories as the first page-by-page area.
- Added tenant database `ProductCategory` model with UUID identity, unique category code, name, description, optional parent category, lifecycle status, and actor UUID fields.
- Added tenant migration `warehouse.0005_productcategory` and applied it to Tenant Alpha and Tenant Beta databases.
- Added Product Category tenant APIs under `/api/v1/tenant/product-categories/` with list, search, create, detail, update, status change, validation, permission checks, and audit events.
- Added tenant portal Product Categories navigation and page using the existing API-backed resource page pattern.
- Added `masters.categories.view` and `masters.categories.manage` permissions to the local tenant-admin seed role.
- Added DB-backed Product Category tests for CRUD, duplicate category rejection, hierarchy validation, unauthorized mutation denial, cross-tenant denial through existing tenant session checks, and audit creation.
- Updated Docker Compose so PostgreSQL and Redis stay on the private Compose network and are not published to the host.
- Kept backend and Celery wired to Docker service DNS: `POSTGRES_HOST=postgres` and `REDIS_URL=redis://redis:6379/0`.
- Added per-build-context `.dockerignore` files so Docker builds do not package local caches.
- Added `migrate_tenant_databases` to apply tenant-plane migrations from trusted control-plane `TenantDatabase` registrations.
- Added `show_tenant_databases` to print safe tenant database registration metadata without secret values.
- Updated local tenant seeding so Alpha/Beta registrations use Docker-compatible SSL mode from `POSTGRES_SSLMODE`.
- Expanded DB-backed tenant isolation acceptance tests for reciprocal PostgreSQL credential denial, Alpha/Beta object separation, and browser-supplied DB selector rejection.
- Added unique control-plane tenant license numbers.
- Added the Lattice Owner Console dashboard UI as the active frontend surface.
- Refined the Owner Dashboard into page 1 of the page-by-page Owner Console delivery: concise platform-health overview only, backed by the real control-plane dashboard API with no frontend mock/fallback tenant data.
- Added a login-first frontend entry so anonymous visitors see the Lattice sign-in screen before any Owner Console shell or protected dashboard request is rendered.
- Wired frontend logout through the backend session endpoint and kept authentication token handling out of browser localStorage.
- Added JWT access/refresh authentication for login and MFA completion, with Bearer-token API support, HttpOnly token cookies, refresh endpoint, and token families bound to the tracked `SecuritySession` registry.
- Added Owner Console tenant management actions for control-plane create, inspect, edit, activate, and suspend flows with responsive Tenants-page UI controls.
- Added owner navigation for Dashboard, Tenants, Subscriptions, Modules, Users & Access, Infrastructure, Security, Reports, and Settings.
- Added a control-plane owner dashboard API under `/api/v1/control/owner/dashboard/`.
- Added control-plane tenant lifecycle APIs under `/api/v1/control/owner/tenants/` with owner authorization and audit records for create, update, activate, and suspend actions.
- Added owner-only tenant database configuration under `/api/v1/control/owner/tenants/<tenant_id>/database/`, allowing trusted control-plane database alias, host reference, database name, runtime role, secret reference, SSL mode, provisioning, health, and migration metadata updates without accepting raw passwords or connection strings.
- Added tenant-aware login context under `/api/v1/auth/login/context/` so tenant hosts display safe tenant identity before sign-in without exposing database metadata.
- Hardened `/api/v1/auth/login/` so verified tenant domains require active tenant status and active `TenantMembership` for the authenticated `GlobalUser` before creating a tenant-bound `SecuritySession`.
- Added `TenantDomain.is_active`, `verification_method`, and `verified_at` metadata so tenant resolution trusts only active verified registered domains.
- Added tenant-bound `SecuritySession` support and tenant API middleware enforcement so an Alpha-bound session cannot access Beta tenant APIs even if the user has multiple memberships.
- Added `/api/v1/tenant/context/` for safe tenant display data, effective tenant roles/permissions, warehouse assignments, modules, and configuration/master counts.
- Replaced the placeholder Tenant Portal with a separate context-backed Tenant Dashboard, Organization, Warehouses, Users & Access, and Settings experience.
- Added tenant hierarchy APIs for plants, warehouses, zones, storage types, storage sections, bins, active warehouse context selection, and hierarchy browsing under `/api/v1/tenant/`.
- Added tenant hierarchy audit events for create/update/status/block/unblock and active warehouse selection.
- Added tenant database actor UUID references for hierarchy records without cross-database foreign keys.
- Added real tenant admin frontend routes for Plants, Warehouses, Zones, Storage Types, Sections, Bins, and Hierarchy with API-backed create/list flows.
- Hardened the owner dashboard API with owner/staff authorization, real control-plane tenant counts, database-health summaries, migration-warning counts, active support grant counts, recent audit/security activity, and safe serialization that excludes tenant DB secret references.
- Updated tenant database runtime registration to use the trusted control-plane `database_host_reference` instead of browser-provided selectors.
- Promoted `control.GlobalUser` to the custom Django authentication user model.
- Added Identity app models for permissions, roles, membership role assignments, warehouse assignments, tracked security sessions, MFA devices, hashed recovery codes, and explicit time-limited platform support tenant access grants.
- Added auth APIs for login, logout, current user, sessions, session revocation, MFA setup/verify/disable, and recovery-code regeneration.
- Added authorization helpers for tenant membership, module-gated permissions, warehouse access, and platform support grants.
- Added secure password-reset request/confirm APIs with generic request responses, hashed one-time tokens, expiry, password validation, session revocation, and audit events.
- Added login abuse controls with per-IP throttling, per-user failed-login counters, configurable temporary lockout, recovery after lockout, and suspicious-login audit hooks.
- Added API security-session enforcement middleware so revoked and expired tracked sessions cannot access APIs.
- Replaced signed-only MFA secret storage for new devices with a keyed encrypted envelope; recovery codes remain one-way hashed and single-use.
- Added Docker healthchecks for backend, frontend, and Celery.
- Updated the backend image to run Django/Celery as a dedicated non-root application user.

### Validation Executed

- `docker compose config`: passed; services are on `wms_saas_default`, with only backend `8000` and frontend `5173` published.
- `docker compose up -d --build`: passed.
- `docker compose ps`: backend, Celery, frontend, PostgreSQL, and Redis are up; PostgreSQL and Redis are healthy.
- Control-plane migrations: no pending migrations.
- Tenant Alpha and Tenant Beta control-plane registrations: READY.
- Tenant database migrations for `tenant_alpha` and `tenant_beta`: applied through `warehouse.0002_plant_warehouse_address_line_1_and_more`.
- `python manage.py check`: passed.
- `python manage.py check --deploy` with production-style local settings: passed.
- Redis connectivity: `redis-cli ping` returned `PONG`.
- Celery connectivity: `celery -A lattice inspect ping` returned `pong`.
- Complete Docker test suite with `LATTICE_RUN_DB_ISOLATION=1`: 69 passed, 0 failed, 0 skipped.
- Owner Console + Platform IAM foundation test suite with `LATTICE_RUN_DB_ISOLATION=1`: 36 passed, 0 failed, 0 skipped.
- Owner Console hardening + Platform IAM security suite with `LATTICE_RUN_DB_ISOLATION=1`: 44 passed, 0 failed, 0 skipped.
- Owner tenant database configuration suite with `LATTICE_RUN_DB_ISOLATION=1`: 52 passed, 0 failed, 0 skipped.
- Frontend `npm.cmd run build`: passed.
- Frontend `npm.cmd run lint`: passed.
- Docker frontend `npm run build`: passed.
- Docker frontend `npm run lint`: passed.
- Docker frontend health: `http://localhost:5173` returned `200 OK`.
- Tenant portal health: `http://localhost:5173/tenant/dashboard` returned `200 OK`.
- Backend Docker `python manage.py check`: passed.
- Log secret scan for known local database passwords: no matches.
- Docker health after rebuild: backend, frontend, Celery, PostgreSQL, and Redis healthy.
- Product Category schema location check: `warehouse_productcategory` is absent from the control database and present in Tenant Alpha/Beta databases.
- Product Category targeted DB-backed suite: `warehouse/tests/test_hierarchy_api.py` passed with 8 passed, 0 failed.
- JWT authentication targeted suite: `identity/tests/test_authentication.py` passed with 33 passed, 0 failed.
- Full Docker backend suite after tenant-login/JWT fixes with `LATTICE_RUN_DB_ISOLATION=1`: 77 passed, 0 failed, 0 skipped.

### Security Decisions

- Local test database creation uses the PostgreSQL admin role and does not grant `CREATEDB` to runtime application roles.
- Tenant runtime roles remain non-superuser and cannot connect across Alpha/Beta tenant databases.
- Tenant database connections are registered only from trusted control-plane metadata.
- Tenant login never selects a tenant/database from request body, query parameters, arbitrary headers, database aliases, database names, schemas, or connection strings.
- Tenant sessions are bound to a specific resolved tenant and tenant APIs re-check domain, active membership, tenant status, and session binding on each request.
- Owner Console normal operations use control-plane metadata and do not query tenant WMS transaction data.
- Owner Dashboard no longer renders hardcoded fallback dashboard data; API failure and permission denial are shown as explicit error states.
- Platform support tenant-data access requires explicit expiring grants and is not implied by staff status.
- Password-reset tokens, passwords, MFA secrets, recovery codes, and tenant database credentials are not written to audit summaries or application logs by the implemented flows.
- Session revocation is enforced with real API requests through the authoritative `SecuritySession` registry.
- JWT authentication reuses the same `SecuritySession` row as the browser session, so logout, password reset, expiry, and session revocation apply consistently to cookie and Bearer-token access.
- Tenant login is evaluated independently from platform owner-console authorization; tenant users must have active membership in the resolved tenant, while owner APIs still deny tenant-only accounts.

### Known Limitations

- Complete Owner Console admin CRUD APIs for platform users, roles, permissions, plans, subscriptions, modules, and feature flags remain in progress.
- Tenant invitation onboarding, active warehouse selector endpoint, generic tenant discovery, and custom-domain DNS/TLS verification workflows remain in progress.
- Full WMS operational modules are not started.
- Tenant Master Data Foundation is not complete; only Product Categories are implemented so far.
- Redis is private to the Compose network locally, but does not require authentication; production must use private networking plus managed authentication/TLS where available.
- The MFA envelope uses configured secret material in this local stack; production should source `MFA_SECRET_ENCRYPTION_KEY` from the platform secret manager or KMS.

## 2026-08-31

### Implemented

- Initialized the Lattice repository foundation.
- Added permanent engineering rules in `AGENTS.md`.
- Added roadmap, security architecture, tenancy, threat model, security checklist, ADRs, Docker, backend, frontend, CI, and test scaffolding.
- Added Django control-plane and tenancy infrastructure skeleton.
- Added Lattice design-system documentation and a centralized frontend token/component structure.
- Added local Python virtual environment workflow support via `.gitignore`.
- Added short PostgreSQL connection timeout settings so unavailable databases fail clearly.
- Expanded tenant resolver tests for Alpha membership allow, Beta membership denial, and missing tenant database mapping.
- Fixed strict TypeScript API error typing and added frontend dependency lockfile through local install.

### Migrations Created

- Initial control-plane migrations for tenants, tenant domains, tenant database metadata, plans, subscriptions, modules, feature flags, global users, tenant memberships, and audit events.
- Fixed initial control-plane migration drift by adding the missing `FeatureFlag.id` field.

### APIs Created

- Health endpoints: `/health/live`, `/health/ready`.
- Tenant-aware demo endpoint used by isolation tests: `/api/v1/tenant/probe/`.

### Tests Added

- Tenant context fail-closed and cleanup tests.
- Tenant resolver tests for host-based resolution and forged header/query attacks.
- Tenant resolver tests for Alpha allowed membership, Beta denied membership, and missing database mapping.
- Database router tests for missing tenant context.
- Provisioning SQL generation tests for tenant database and role isolation.
- Celery context isolation unit test.

### Validation Executed

- `npm.cmd install --no-audit --no-fund` from `frontend/`: passed.
- `npm.cmd run build` from `frontend/`: passed.
- `npm.cmd run lint` from `frontend/`: passed.
- `python -m venv .venv`: passed.
- `.venv` backend dependency install: passed.
- `python manage.py check`: passed.
- `python manage.py check --deploy` with a production-shaped local secret: passed.
- `python manage.py makemigrations --check --dry-run`: passed with no model changes detected; warned that PostgreSQL was unavailable for migration-history check.
- Fast tenant/security tests: 7 passed.
- Full tenant test suite: 7 passed, 2 skipped, 7 DB-backed resolver tests errored because PostgreSQL is not reachable.
- `Test-NetConnection localhost:5432`: TCP failed.
- `Test-NetConnection localhost:6379`: TCP failed.
- Docker Compose service config: passed.
- Docker engine/Compose runtime: blocked; Docker Desktop engine calls hang or return HTTP 500.

### Security Decisions

- Database-per-client is the primary tenant boundary.
- Tenant database selection is never based on client-supplied database parameters.
- Control-plane stores tenant secret references, not plaintext credentials.
- Tenant database routing fails closed when context is unavailable.
- The approved Figma design controls presentation only; frontend permission-aware visibility does not replace backend authorization.

### Known Limitations

- Frontend dependencies are installed locally and frontend build/lint pass.
- Backend dependencies are installed locally in `.venv`; Django system checks pass.
- Docker Desktop remains unhealthy in this environment: Docker engine calls hang or return HTTP 500, so Docker Compose startup/build validation cannot complete.
- Local PostgreSQL and Redis are not listening on ports 5432/6379, so migrations, DB-backed resolver tests, Redis connectivity, Celery broker connectivity, and real database-role isolation tests are blocked.
- Tenant provisioning command is implemented with a dry-run mode and guarded SQL generator; production execution requires PostgreSQL admin credentials supplied out of band.
- Authentication, MFA, RBAC, and WMS modules are not started.
- Figma MCP inspection returned `INVALID_ARGUMENT`; current frontend tokens are centralized provisional values derived from the supplied screenshot and must be replaced with exact Figma values once access works.

### Next Tasks

- Restore Docker Desktop/PostgreSQL/Redis availability.
- Run migrations and the full tenant isolation suite against real control and tenant databases.
- After tenant isolation passes, implement local authentication, tenant membership enforcement, MFA TOTP/recovery codes, granular RBAC, warehouse-scope checks, and audit middleware.
