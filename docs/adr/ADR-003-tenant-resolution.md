# ADR-003: Trusted Tenant Resolution

## Context

Tenant resolution determines the physical database used by business logic.

## Decision

Resolve tenants only from trusted server-side state such as verified hostnames, authenticated memberships, and signed claims. Ignore arbitrary tenant and database selectors from headers, query parameters, and request bodies.

## Alternatives

- Let clients pass tenant aliases
- Let API callers pass database names

## Consequences

APIs need explicit membership and hostname validation. Local development requires configured tenant domains.

## Security Implications

Forged headers and database parameter attacks cannot switch the active tenant database.
