# Lattice Tenant Authentication And Experience

Lattice tenant access is domain-aware, but the domain is only a tenant candidate. Access is granted only after the backend verifies the authenticated user, active tenant membership, active tenant status, MFA policy, authoritative security session state, and tenant database routing.

## Runtime Path

Implemented tenant login path:

1. Browser opens a registered tenant host such as `alpha.localhost`.
2. `GET /api/v1/auth/login/context/` resolves only active verified `TenantDomain` records and returns safe display metadata.
3. `POST /api/v1/auth/login/` rejects browser-supplied database selectors, authenticates `GlobalUser`, verifies active tenant membership for the resolved tenant, enforces tenant role MFA policy, creates a `SecuritySession`, and binds the session to the tenant.
4. Tenant APIs under `/api/v1/tenant/` resolve the request host again, verify active membership again, verify the tracked session is bound to the same tenant, register the tenant database only from trusted control-plane `TenantDatabase`, establish request-local context, and clear context in `finally`.
5. `GET /api/v1/tenant/context/` returns safe tenant display data, effective tenant roles and permissions, warehouse assignments, enabled modules, and configuration/master counts.

The frontend keeps the Owner Console and Tenant Portal as separate shells. Tenant routes call tenant APIs and show explicit safe error states if backend tenant access fails.

## Phase 0 Audit

| Item | Status | Evidence |
| --- | --- | --- |
| Tenant login using domain/subdomain | IMPLEMENTED | `identity.views.LoginView`, `LoginContextView`; tests in `identity/tests/test_authentication.py` |
| TenantDomain to Tenant resolution | IMPLEMENTED | `tenancy.resolver.TenantResolver`; tests in `tenancy/tests/test_resolver.py` |
| Verified-domain validation | IMPLEMENTED | `TenantDomain.verified`, `TenantDomain.is_active`, resolver/login checks; tests for unverified domain denial |
| Tenant-aware login page | IMPLEMENTED | `frontend/src/pages/auth/LoginPage.tsx`, `/api/v1/auth/login/context/` |
| GlobalUser authentication | IMPLEMENTED | Custom `control.GlobalUser`, Django auth backend path; authentication tests |
| TenantMembership validation | IMPLEMENTED | Login and tenant middleware membership checks; cross-tenant login tests |
| Inactive membership rejection | IMPLEMENTED | Login rejects non-active membership; resolver rejects non-active membership |
| Suspended tenant rejection | IMPLEMENTED | Login and resolver reject non-active tenants; tests cover suspended tenant denial |
| MFA challenge | IMPLEMENTED | `MfaVerifyView`, TOTP/recovery tests |
| Mandatory MFA for privileged tenant roles | IMPLEMENTED | `Role.requires_mfa` with tenant-scoped login enforcement; test covers `TENANT_ADMIN` |
| SecuritySession creation | IMPLEMENTED | `SecuritySession.tenant`, `_track_session`; tests assert tenant binding |
| Session revocation/expiry enforcement | IMPLEMENTED | `SecuritySessionMiddleware`; session tests |
| Tenant context establishment after login | IMPLEMENTED | Session stores tenant id/code; tenant middleware establishes request-local tenant context |
| Tenant DB routing after authentication | IMPLEMENTED | `TenantResolutionMiddleware`, `register_tenant_database`, `LatticeDatabaseRouter`; DB-backed isolation tests |
| OwnerShell vs TenantShell separation | IMPLEMENTED | `frontend/src/App.tsx`, `AppShell`, `OwnerConsole`, `TenantPortal` |
| Tenant route protection | PARTIAL | Backend tenant APIs are protected; frontend UX route guard exists. Full tenant page CRUD permissions are future work |
| Tenant users accessing Owner Console | IMPLEMENTED | Owner APIs require staff/platform owner; frontend denies owner shell for non-owner |
| Tenant administrator invitation | NOT IMPLEMENTED | Planned next; no production invite endpoint yet |
| One-time invite token | NOT IMPLEMENTED | Planned next |
| Password setup from invite | NOT IMPLEMENTED | Existing password reset is secure and reusable, invite onboarding pending |
| Tenant admin MFA enrollment | PARTIAL | MFA setup/verify exists; invitation-driven enrollment flow pending |
| Tenant dashboard redirect | IMPLEMENTED | Frontend routes tenant users to `/tenant/dashboard` |
| Plant/warehouse assignment checks | PARTIAL | Assignment model/helpers/context response exist; operational warehouse APIs pending |
| Active warehouse context | NOT IMPLEMENTED | `active_warehouse` session placeholder returned; verified selector endpoint pending |
| Custom tenant domains | PARTIAL | Model supports verified active hostnames; DNS/TLS verification workflow pending |
| Generic login/tenant discovery | NOT IMPLEMENTED | Secondary flow intentionally deferred |
| OIDC/SAML readiness | PARTIAL | Architecture rule documented; provider flows not implemented |

## Safe Local URLs

- Owner Console: `http://localhost:5173/owner/dashboard`
- Tenant Alpha portal: `http://alpha.localhost:5173/tenant/dashboard`
- Tenant Beta portal: `http://beta.localhost:5173/tenant/dashboard`

Local tenant URLs require matching `TenantDomain` records, active tenant membership, and a tenant-bound security session.
