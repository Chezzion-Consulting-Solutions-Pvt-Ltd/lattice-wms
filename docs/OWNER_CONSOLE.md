# Lattice Owner Console

The Owner Console is delivered page-by-page. A page is complete only when the UI is backed by real APIs, server-side authorization, validation, persistence where applicable, audit coverage for mutations, error handling, tests, and Docker validation.

## Current Page Status

| Page | Status | Notes |
| --- | --- | --- |
| Dashboard | FUNCTIONAL | Uses real control-plane API data and explicit API error states |
| Tenant List | NOT IMPLEMENTED | Next page |
| Create Tenant | NOT IMPLEMENTED | Must provision end-to-end before completion |
| Tenant Detail | NOT IMPLEMENTED | Must use real tab APIs |
| Plans | NOT IMPLEMENTED | Control-plane CRUD pending |
| Subscriptions | NOT IMPLEMENTED | Control-plane CRUD pending |
| Licenses | NOT IMPLEMENTED | Dedicated license lifecycle pending |
| Platform Users | NOT IMPLEMENTED | Platform IAM CRUD pending |
| Roles | NOT IMPLEMENTED | Role CRUD and permission assignment pending |
| Permissions | NOT IMPLEMENTED | Authoritative permission-definition UI pending |
| Support Access | NOT IMPLEMENTED | Request/approve/revoke workflow pending |
| Modules | NOT IMPLEMENTED | Entitlement administration pending |
| Feature Flags | NOT IMPLEMENTED | Global definitions and tenant overrides pending |
| Tenant Databases | NOT IMPLEMENTED | Safe metadata and health actions pending |
| Migrations | NOT IMPLEMENTED | Controlled migration jobs pending |
| Backups | NOT IMPLEMENTED | Backup provider integration pending |
| Restore | NOT IMPLEMENTED | Controlled restore workflow pending |
| Service Health | NOT IMPLEMENTED | Dedicated service-health page pending |
| Security Events | NOT IMPLEMENTED | Audit/security filters pending |
| Audit Logs | NOT IMPLEMENTED | Append-only audit browsing pending |
| Reports | NOT IMPLEMENTED | Control-plane reports pending |
| Settings | NOT IMPLEMENTED | Persisted validated settings pending |

## Dashboard

The Dashboard answers: is the Lattice SaaS platform healthy, and what requires attention?

It uses `/api/v1/control/owner/dashboard/` and only control-plane data. It does not query tenant WMS transaction databases and does not expose tenant database passwords, secret references, or connection strings.

Implemented Dashboard data:

- tenant counts
- active and suspended tenant counts
- ready and healthy tenant database counts
- database warning count
- migration warning count from recorded tenant database migration metadata
- backup status as `NOT_IMPLEMENTED` until a real backup provider exists
- security alert count from append-only audit events
- active support access grant count
- compact tenant health rows
- platform health checks for backend, PostgreSQL, Redis, and Celery
- recent security events
- recent audit activity
- subscription/license attention from control-plane records

Dashboard access is server-authorized for active owner/staff users. Anonymous and non-owner users are denied.
