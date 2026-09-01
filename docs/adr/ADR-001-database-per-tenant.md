# ADR-001: Database Per Tenant

## Context

Lattice is an enterprise SaaS WMS where tenant isolation is a primary security requirement.

## Decision

Use one PostgreSQL database and one runtime database role per tenant.

## Alternatives

- Shared tables with `tenant_id`
- PostgreSQL schemas per tenant

## Consequences

Provisioning, migrations, health checks, backup, and restore are more complex. The isolation boundary is stronger and easier to reason about for enterprise customers.

## Security Implications

Tenant runtime credentials cannot access another tenant database. Application routing must fail closed when tenant context is missing.
