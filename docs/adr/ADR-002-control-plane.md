# ADR-002: Control Plane

## Context

Lattice needs global SaaS metadata before a tenant database can be resolved.

## Decision

Create a control database for tenant metadata, domains, tenant database records, global identity, memberships, plans, feature flags, and control audit events.

## Alternatives

- Store global data in each tenant database
- Store WMS transaction data in the control database

## Consequences

The control plane is a high-value asset and requires strict app ownership rules.

## Security Implications

The control database must not contain tenant WMS transaction data or plaintext tenant DB passwords.
