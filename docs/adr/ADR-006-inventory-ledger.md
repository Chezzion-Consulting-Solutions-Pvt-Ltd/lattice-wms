# ADR-006: Inventory Ledger

## Context

Inventory correctness is central to WMS trust.

## Decision

Future inventory flows will use an append-oriented movement ledger, Decimal quantities, transaction boundaries, idempotency keys, and database constraints.

## Alternatives

- Update balances directly without ledger
- Use floating-point quantities

## Consequences

Inventory code will be slightly more verbose but auditable and race-resistant.

## Security Implications

Duplicate GR/PGI and inventory race tests are blocking before outbound/inbound flows are considered complete.
