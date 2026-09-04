# Warehouse Control

`WarehouseControl` stores safe tenant warehouse configuration profiles in tenant databases using table `lattice_whscnt`.

Supported scopes:

- Tenant defaults
- Plant defaults
- Warehouse overrides
- Process-specific configuration metadata

Examples include default category references, mixed SKU/batch flags, capacity checking, scan policy metadata, confirmation policy metadata, and sequence references. Operational execution rules remain later.
