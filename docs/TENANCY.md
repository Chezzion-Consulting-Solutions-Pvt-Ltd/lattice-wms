# Lattice Tenancy

Lattice uses database-per-client tenancy.

## Control Database

The control database, normally named `lattice_control`, stores:

- Tenants
- Tenant domains
- Tenant database metadata
- Secret references
- Plans and subscriptions
- Feature flags
- Minimal global identity
- Tenant memberships
- Control-plane audit events

It must not store WMS transaction data.

## Tenant Databases

Each tenant database stores only that tenant's operational WMS data. Cross-database foreign keys are prohibited. Tenant data may reference global users by immutable UUID.

Example local test tenants:

| Tenant | Database | Runtime Role |
| --- | --- | --- |
| tenant_alpha | lattice_alpha | lattice_alpha_app |
| tenant_beta | lattice_beta | lattice_beta_app |

## Resolution

Tenant resolution is performed by backend code using verified hostnames and authenticated memberships. A browser may request business resources, but it never chooses the physical database.

## Context

Tenant context is backed by Python `ContextVar` storage so synchronous requests, ASGI execution, and Celery tasks can isolate context. Code that touches tenant models without context raises `TenantContextError`.

## Routing

Control-plane Django apps always use `default`. Tenant Django apps must use the current tenant database alias. Missing tenant context never falls back to `default`.
