# Lattice Owner Console

The Owner Console is delivered page-by-page. A page is complete only when the UI is backed by real APIs, server-side authorization, validation, persistence where applicable, audit coverage for mutations, error handling, tests, and Docker validation.

## Current Page Status

| Page | Status | Notes |
| --- | --- | --- |
| Dashboard | FUNCTIONAL | Uses real control-plane API data and explicit API error states |
| Tenant List | PARTIAL | API-backed existing table; advanced filters and dedicated page split pending |
| Create Tenant | FUNCTIONAL | Backend provisioning creates tenant/license/domain/database metadata, PostgreSQL DB/role through admin connector, runs tenant migrations, creates default configuration/modules/admin invitation, and marks READY |
| Tenant Detail | FUNCTIONAL | Direct detail/edit URLs plus related-resource API for domains, subscription, license, modules, feature flags, support access, backups, and restores |
| Plans | FUNCTIONAL | Dedicated CRUD page and API support create/read/update/activate/deactivate with filters, pagination, validation, and audit |
| Subscriptions | FUNCTIONAL | Dedicated CRUD page and API support create/read/update/status lifecycle with filters, pagination, validation, and audit |
| Licenses | PARTIAL | Issue/read/update plus renew/revoke/reactivate APIs exist; dedicated UI still pending |
| Platform Users | FUNCTIONAL | Dedicated page plus create/read/update/activate/disable/password-reset/session-revoke APIs, role assignment, and last-admin protection |
| Roles | FUNCTIONAL | Dedicated page plus create/read/update/disable/activate APIs, permission assignment, default roles, and assigned-user counts |
| Permissions | FUNCTIONAL | Dedicated read-only grouped permission registry page and deny-by-default registry |
| Support Access | FUNCTIONAL | Dedicated page plus request/approve/deny/revoke/update lifecycle APIs with expiry-aware status |
| Modules | PARTIAL | Create/read/update/activate/deactivate APIs, tenant override API, and tenant module history exist; dedicated UI still pending |
| Feature Flags | PARTIAL | Create/read/update/activate/deactivate APIs and tenant override API exist; dedicated UI still pending |
| Tenant Databases | FUNCTIONAL | Safe metadata list and health-check action exist without exposing secret references |
| Migrations | FUNCTIONAL | Real status list and trusted tenant migration orchestration endpoint exist |
| Backups | FUNCTIONAL | Metadata, policy, fail-closed unconfigured state, and local metadata provider execution exist |
| Restore | FUNCTIONAL | Restore request, approval, fail-closed provider validation, and local metadata provider execution exist |
| Service Health | PARTIAL | Dedicated real health API exists |
| Security Events | PARTIAL | Filterable denied/failed audit event API exists |
| Audit Logs | PARTIAL | Append-only audit browsing API exists |
| Sessions | PARTIAL | Platform session list and revoke API exist |
| MFA Compliance | PARTIAL | Privileged user compliance API exists |
| Reports | FUNCTIONAL | Dedicated report selector, real control-plane queries, audited CSV export, and CSV formula sanitization |
| Settings | PARTIAL | Persisted validated platform settings API exists |
| Notifications | PARTIAL | Persisted notification list and read-state APIs exist |

## Dashboard

The Dashboard answers: is the Lattice SaaS platform healthy, and what requires attention?

It uses `/api/v1/control/owner/dashboard/` and only control-plane data. It does not query tenant WMS transaction databases and does not expose tenant database passwords, secret references, or connection strings.

Implemented Dashboard data:

- tenant counts
- active and suspended tenant counts
- ready and healthy tenant database counts
- database warning count
- migration warning count from recorded tenant database migration metadata
- backup status as `NOT_CONFIGURED` until a real backup provider exists
- security alert count from append-only audit events
- active support access grant count
- compact tenant health rows
- platform health checks for backend, PostgreSQL, Redis, and Celery
- recent security events
- recent audit activity
- subscription/license attention from control-plane records

Dashboard access is server-authorized for active owner/staff users. Anonymous and non-owner users are denied.

## Owner API Expansion

The Owner API is split into focused modules under `/api/v1/control/owner/` for plans, subscriptions, licenses, modules, features, platform users, roles, permissions, support access, infrastructure, security events, audit logs, sessions, MFA compliance, reports, settings, and notifications.

Current limitations remain explicit: production DNS/HTTP verification and production backup/PITR adapters are not faked. Local backup state is `NOT_CONFIGURED` unless the tenant is configured with the `LOCAL_METADATA` drill provider.

## Implementation Gap Matrix

| Feature | Frontend | API | DB | Auth | Audit | Tests | Gap |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Dashboard | Functional | Functional | Existing control data | Per-permission owner gate | Read-only | Partial | Add dedicated visual regression coverage |
| Tenant List | Functional | Functional | Tenant/TenantDatabase | Per-permission owner gate | Mutations only | Partial | Add deeper UI coverage for every exposed filter |
| Tenant Create | Partial | Partial | Tenant/License | Owner/staff gate | Yes | Partial | Replace simple dialog with provisioning workflow and retryable failed state |
| Tenant Detail | Functional | Functional | Control related resources | Per-permission owner gate | Mutations only | Verified | Add richer tab-level frontend polish |
| Tenant Domains | Functional | Functional | TenantDomain | Resolver enforces verified/active | Yes | Verified | Add production DNS/HTTP verification provider; local-development verify UI/API exists |
| Plans | Functional | Functional | Plan/PlanModule | Per-permission owner gate | Yes | Verified | Add visual regression coverage and deeper feature entitlement tests |
| Subscriptions | Functional | Functional | Subscription | Per-permission owner gate | Yes | Verified | Add tenant-access policy enforcement integration tests where configured |
| Licenses | Functional | Functional | License | Per-permission owner gate | Yes | Verified | Add expiry alert automation |
| Modules | Functional | Functional | ModuleDefinition/TenantModule | Per-permission owner gate | Yes | Verified | Add entitlement enforcement tests in tenant runtime modules as they are built |
| Feature Flags | Functional | Functional | FeatureFlag/TenantFeatureFlag | Per-permission owner gate | Yes | Verified | Add tenant runtime enforcement tests as flagged features are built |
| Platform Users | Functional | Functional | GlobalUser/SecuritySession/PlatformUserRole | Per-permission owner gate | Yes | Verified | Add deeper unauthorized role-escalation tests |
| Roles | Functional | Functional | Role/RolePermission/PlatformUserRole | Per-permission owner gate | Yes | Verified | Add richer assigned-user detail UI |
| Permissions | Functional | Functional | Permission | Per-permission owner gate | Read-only | Verified | Add grouped permission descriptions as permission catalog grows |
| Support Access | Functional | Functional | PlatformTenantAccessGrant | Per-permission owner gate | Yes | Verified | Add tenant-data enforcement tests for every future support-scoped endpoint |
| Databases | Functional | Functional | TenantDatabase | Per-permission owner gate | Health action | Verified | Add production provider health probes |
| Migrations | Functional | Functional | TenantDatabase metadata | Per-permission owner gate | Yes | Verified | Add concurrency locks and canary/batch execution controls |
| Backups | Functional | Functional | BackupPolicy/BackupRecord | Per-permission owner gate | Yes | Verified | Add production object-store/PITR provider adapter |
| Restore | Functional | Functional | RestoreRequest | Per-permission owner gate | Yes | Verified | Add production PITR restore adapter and destructive-operation runbooks |
| Service Health | Functional | Functional | Runtime checks | Per-permission owner gate | Read-only | Partial | Add queue latency and provider-specific tenant DB tests |
| Security Events | Functional | Functional | AuditEvent | Per-permission owner gate | Read-only | Partial | Add safe detail tests |
| Audit Logs | Functional | Functional | AuditEvent | Per-permission owner gate | Append-only | Partial | Add immutable/no-delete tests |
| Sessions | Functional | Functional | SecuritySession | Per-permission owner gate | Revoke | Partial | Add no-token exposure tests |
| MFA Compliance | Functional | Functional | MfaDevice/GlobalUser | Per-permission owner gate | Read-only | Partial | Add force re-enrollment/revoke device workflow |
| Reports | Functional | Functional | Control tables | Per-permission owner gate | CSV export | Verified | Add export row-limit tests and richer report filters |
| Settings | Functional | Functional | PlatformSetting | Per-permission owner gate | Yes | Partial | Add production provider application for supported keys |
| Notifications | Functional | Functional | OwnerNotification | Per-permission owner gate | Read-state only | Partial | Add source links |
| Profile Menu | Partial | Existing auth APIs | SecuritySession/MFA | Authenticated | Logout/session actions | Partial | Add My Profile, Security, MFA, Sessions, Change Password entries |

Phase 1 progress: `OwnerShell`, route metadata, generic resource tables, and CRUD helper components are extracted so Owner pages stay small and reusable. Non-dashboard routes load independently from the dashboard preload, `/owner/tenants/<tenant_id>/` and `/owner/tenants/<tenant_id>/edit` resolve, tenant table View actions navigate to detail URLs, and the tenant list API supports search, pagination, sorting, status, region, plan, and database-health filters.

Phase 1 remaining gaps: add visual regression coverage and continue moving large legacy dashboard/detail sections into smaller route components as UI polish continues.

Phase 2 progress: tenant provisioning now has a backend workflow endpoint and Create Tenant UI wiring. It creates tenant/license/domain/database metadata, resolves only a secret reference, creates PostgreSQL database/runtime role through a configured admin connector, runs tenant migrations through trusted tenant database registration, creates default tenant configuration/module rows, bootstraps the tenant admin membership and hashed admin invitation, and marks READY only after success. Failures persist FAILED state, create an owner notification, audit failure safely, and do not expose passwords. A retry endpoint is available for failed provisioning state. Tenant domain management now has owner APIs and a Tenant Detail UI panel for add, local-development verify, activate/deactivate, and make-primary. Resolver security remains unchanged: only active and verified domains can resolve tenant login. Plans and Subscriptions now have dedicated CRUD pages backed by explicit control-plane APIs with server-side filtering, pagination, validation, lifecycle actions, and audit events.

Phase 2 remaining gaps: production DNS/HTTP domain verification and broader entitlement enforcement tests. Licenses, Modules, and Feature Flags now have functional lifecycle APIs, targeted tests, and dedicated reusable frontend pages.

Access/IAM progress: Platform Users, Roles, Permissions, and Support Access now have dedicated frontend pages backed by lifecycle APIs. Platform users support persisted role assignment, activate/disable, password-reset trigger, revoke-all-sessions, MFA posture, and last Platform Admin protection. Roles support persisted permission assignment and active/disabled lifecycle. Support Access supports requested, approved/active, denied, revoked, and expired status without permanent hidden access.

Reporting progress: Owner reports have a dedicated selector and audited CSV export using `export=csv`; exported values are sanitized against spreadsheet formula injection.

Final gap-closure progress: Owner APIs now enforce explicit per-permission platform roles instead of a broad staff-only gate. Tenant detail related-resource tabs, migration orchestration, local metadata backup execution, restore approval/execution, and safe provider-failure paths are implemented and covered by Docker-backed tests. Production backup/PITR providers remain intentionally explicit follow-up adapters rather than simulated success.
