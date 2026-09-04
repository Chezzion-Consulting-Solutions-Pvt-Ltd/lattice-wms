# Bay Configuration

Bay configuration defines physical warehouse locations where inventory may later be held. This phase does not implement inventory balances or movement execution.

Implemented:

- CRUD through `/api/v1/tenant/bays/`
- Unique bay code per warehouse
- Parent validation for warehouse, zone, section, and storage type
- Block/unblock configuration state
- Bulk generation preview/commit with safe token patterns
- JSON import preview/commit
- CSV export
- Tenant audit and warehouse log records

Safe bay code tokens are `{aisle}`, `{rack}`, `{level}`, and `{position}`. Arbitrary expressions are rejected.
