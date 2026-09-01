# ADR-004: Authentication

## Context

Lattice must support local authentication now and enterprise SSO later.

## Decision

Implement authentication in the control plane with minimal global identity, tenant memberships, secure password hashing, session security, MFA, and audit events.

## Alternatives

- Tenant-local authentication only
- Stateless browser tokens stored in local storage

## Consequences

Authentication can occur before tenant DB resolution. Tenant-specific profiles and warehouse assignments remain in tenant databases.

## Security Implications

MFA is mandatory for privileged administrators. Sensitive browser tokens must not be stored in local storage.
