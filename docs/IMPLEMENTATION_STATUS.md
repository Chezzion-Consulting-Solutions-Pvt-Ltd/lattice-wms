# Lattice Implementation Status

## 2026-09-01

### Implemented

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
- Wired frontend logout through the backend session endpoint and kept authentication cookie-based with no browser token storage.
- Added Owner Console tenant management actions for control-plane create, inspect, edit, activate, and suspend flows with responsive Tenants-page UI controls.
- Added owner navigation for Dashboard, Tenants, Subscriptions, Modules, Users & Access, Infrastructure, Security, Reports, and Settings.
- Added a control-plane owner dashboard API under `/api/v1/control/owner/dashboard/`.
- Added control-plane tenant lifecycle APIs under `/api/v1/control/owner/tenants/` with owner authorization and audit records for create, update, activate, and suspend actions.
- Hardened the owner dashboard API with owner/staff authorization, real control-plane tenant counts, database-health summaries, migration-warning counts, active support grant counts, recent audit/security activity, and safe serialization that excludes tenant DB secret references.
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
- Tenant database migrations for `tenant_alpha` and `tenant_beta`: no pending migrations.
- `python manage.py check`: passed.
- `python manage.py check --deploy` with production-style local settings: passed.
- Redis connectivity: `redis-cli ping` returned `PONG`.
- Celery connectivity: `celery -A lattice inspect ping` returned `pong`.
- Complete Docker test suite with `LATTICE_RUN_DB_ISOLATION=1`: 20 passed, 0 failed, 0 skipped.
- Owner Console + Platform IAM foundation test suite with `LATTICE_RUN_DB_ISOLATION=1`: 36 passed, 0 failed, 0 skipped.
- Owner Console hardening + Platform IAM security suite with `LATTICE_RUN_DB_ISOLATION=1`: 44 passed, 0 failed, 0 skipped.
- Owner tenant management suite with `LATTICE_RUN_DB_ISOLATION=1`: 49 passed, 0 failed, 0 skipped.
- Frontend `npm.cmd run build`: passed.
- Frontend `npm.cmd run lint`: passed.
- Docker frontend `npm run build`: passed.
- Docker frontend `npm run lint`: passed.
- Docker frontend health: `http://localhost:5173` returned `200 OK`.
- Backend Docker `python manage.py check`: passed.
- Log secret scan for known local database passwords: no matches.
- Docker health after rebuild: backend, frontend, Celery, PostgreSQL, and Redis healthy.

### Security Decisions

- Local test database creation uses the PostgreSQL admin role and does not grant `CREATEDB` to runtime application roles.
- Tenant runtime roles remain non-superuser and cannot connect across Alpha/Beta tenant databases.
- Tenant database connections are registered only from trusted control-plane metadata.
- Owner Console normal operations use control-plane metadata and do not query tenant WMS transaction data.
- Owner Dashboard no longer renders hardcoded fallback dashboard data; API failure and permission denial are shown as explicit error states.
- Platform support tenant-data access requires explicit expiring grants and is not implied by staff status.
- Password-reset tokens, passwords, MFA secrets, recovery codes, and tenant database credentials are not written to audit summaries or application logs by the implemented flows.
- Session revocation is enforced with real API requests through the authoritative `SecuritySession` registry.

### Known Limitations

- Complete Owner Console admin CRUD APIs for platform users, roles, permissions, tenant administration, plans, subscriptions, modules, and feature flags remain in progress.
- Full WMS operational modules are not started.
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
