# Lattice Security Checklist

Status values: `NOT IMPLEMENTED`, `PARTIAL`, `IMPLEMENTED`, `VERIFIED`.

| Category | Requirement | Status | Evidence |
| --- | --- | --- | --- |
| Architecture | Database per tenant | VERIFIED | Docker-backed Alpha/Beta tenant isolation tests pass |
| Architecture | Control DB contains no WMS transactions | IMPLEMENTED | App ownership rules |
| Authentication | Local auth | VERIFIED | Login/logout/me/session APIs plus Docker-backed tests |
| Authentication | Login-first frontend entry | VERIFIED | Anonymous UI renders sign-in before protected console data requests; session remains cookie-backed |
| Authentication | Tenant-domain login | VERIFIED | Domain-aware login context, active membership validation, tenant-bound sessions, and cross-tenant denial tests |
| Authentication | Password reset | VERIFIED | Generic request, one-time token, expiry, session revocation tests |
| Authentication | Login abuse protection | VERIFIED | Per-IP throttle, per-user lockout, recovery, success-clear tests |
| Authentication | SSO/OIDC architecture | NOT IMPLEMENTED | Phase 9 |
| MFA | TOTP and recovery codes | VERIFIED | Setup, verify, invalid code, encrypted secret, and single-use recovery tests |
| Authorization | RBAC and granular permissions | PARTIAL | Role/permission models and helper tests |
| Authorization | Owner dashboard access | VERIFIED | Anonymous/non-owner denied; owner request allowed |
| Authorization | Warehouse scope | PARTIAL | Assignment model and allow/deny tests |
| Tenant Administration | Hierarchy CRUD | VERIFIED | Tenant DB-backed plant, warehouse, zone, storage type, section, bin API tests pass |
| Tenant Master Data | Product Category CRUD | VERIFIED | Tenant DB-backed Product Category API tests pass; table exists in tenant DBs and not in control DB |
| Tenant Administration | Active warehouse context | VERIFIED | Backend verifies active membership, active warehouse, and active assignment before session context change |
| Session Management | Secure cookie strategy | VERIFIED | Cookie sessions, tracked security-session model, revoked/expired enforcement tests |
| API Security | Versioned APIs | PARTIAL | `/api/v1/auth/login/`, `/api/v1/auth/login/context/`, `/api/v1/tenant/context/`, `/api/v1/tenant/probe/` |
| Application Security | Safe errors | PARTIAL | Exception classes and middleware |
| Tenant Isolation | Header/query DB selector ignored | VERIFIED | Resolver and DB-backed acceptance tests pass |
| Tenant Isolation | Missing tenant context fails closed | VERIFIED | Fast tests pass locally |
| Tenant Isolation | Missing tenant mapping never falls back | VERIFIED | Resolver tests pass in Docker |
| Database Security | One DB role per tenant | VERIFIED | Reciprocal Alpha/Beta PostgreSQL credential denial tests pass |
| Encryption | TLS in production | PARTIAL | Settings and docs |
| Secrets | Secret references, no plaintext tenant DB password columns | IMPLEMENTED | `TenantDatabase.secret_reference` |
| File Security | Upload controls | NOT IMPLEMENTED | Future phase |
| Audit | Structured append-only audit | PARTIAL | Control audit model and identity security events |
| Logging | Request IDs | PARTIAL | Middleware |
| Monitoring | Health checks | VERIFIED | Compose healthchecks for backend, frontend, Celery, PostgreSQL, and Redis |
| Backups | Tenant backup metadata | NOT IMPLEMENTED | Future phase |
| DR | PITR/restore workflow | NOT IMPLEMENTED | Future phase |
| DevSecOps | CI security gates | PARTIAL | GitHub Actions scaffold |
| Dependency Security | pip-audit/npm audit/Trivy | PARTIAL | CI placeholders |
| Cloud/Network Security | Private DB/Redis design | VERIFIED | Compose publishes only backend/frontend ports; Postgres/Redis remain internal |
| Data Residency | Region metadata | PARTIAL | Tenant model region |
| Incident Response | Runbook | PARTIAL | Initial document |
| Penetration Testing | Security test suite | VERIFIED | Docker-backed mandatory security suite: 69 passed, 0 failed, 0 skipped |
| Vendor Risk | Vendor security evidence request | IMPLEMENTED | `docs/VENDOR_SECURITY_EVIDENCE_REQUEST.md` covers checklist, SOC 2 Type II, privacy, ISO, VA/PT, LLM security, mobile PT, DR drill, and backup restore evidence |
| Security Assessment | Current security measures assessment | IMPLEMENTED | `docs/SECURITY_MEASURES_ASSESSMENT.md` separates verified app controls from external evidence gaps |
