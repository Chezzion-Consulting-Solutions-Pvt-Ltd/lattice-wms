# ADR-005: Audit Architecture

## Context

Enterprise WMS operations require investigation-grade audit trails.

## Decision

Use structured append-only audit records with request IDs, tenant IDs, global user IDs, resource metadata, result, and safe before/after summaries.

## Alternatives

- Rely on application logs only
- Store unstructured text audit records

## Consequences

Sensitive operations must identify audit requirements during implementation.

## Security Implications

Audit records must never store secrets or full sensitive payloads.
