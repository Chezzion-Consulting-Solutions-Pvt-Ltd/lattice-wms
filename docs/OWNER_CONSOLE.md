# Lattice Owner Console

The Owner Console is delivered page-by-page. A page is complete only when the UI is backed by real APIs, server-side authorization, validation, persistence where applicable, audit coverage for mutations, error handling, tests, and Docker validation.

## Current Page Status

| Page | Status | Notes |
| --- | --- | --- |
| Dashboard | FUNCTIONAL | Uses real control-plane API data and explicit API error states |
| Tenant List | PARTIAL | API-backed existing table; advanced filters and dedicated page split pending |
| Create Tenant | PARTIAL | Persists tenant and license records; full database provisioning workflow pending |
| Tenant Detail | PARTIAL | API-backed metadata/database panel; tabbed detail APIs pending |
| Plans | PARTIAL | Control-plane create/update/list API and route exist |
| Subscriptions | PARTIAL | Control-plane upsert/update/list API and route exist |
| Licenses | PARTIAL | Dedicated license records, list, renew, revoke, and reactivate APIs exist |
| Platform Users | PARTIAL | Safe list/create/update API and route exist |
| Roles | PARTIAL | Role create/update/list and permission assignment API exist |
| Permissions | PARTIAL | Default owner permission registry API exists |
| Support Access | PARTIAL | Owner-approved grant list/create/revoke API exists |
| Modules | PARTIAL | Global module definitions and tenant override API exist |
| Feature Flags | PARTIAL | Global definitions and tenant override API exist |
| Tenant Databases | PARTIAL | Safe metadata list and health-check action exist |
| Migrations | PARTIAL | Real status list exists; execution orchestration pending |
| Backups | PARTIAL | Metadata and policy API exists; local provider truthfully reports `NOT_CONFIGURED` |
| Restore | PARTIAL | Restore request persistence exists; provider execution pending |
| Service Health | PARTIAL | Dedicated real health API exists |
| Security Events | PARTIAL | Filterable denied/failed audit event API exists |
| Audit Logs | PARTIAL | Append-only audit browsing API exists |
| Sessions | PARTIAL | Platform session list and revoke API exist |
| MFA Compliance | PARTIAL | Privileged user compliance API exists |
| Reports | PARTIAL | Real control-plane report queries and CSV export exist |
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

Current limitations remain explicit: tenant database provisioning, migration execution, and backup/restore provider execution are not faked. Local backup state is `NOT_CONFIGURED` unless a real provider is attached.
