# Tenant Master Data

Status: `IN PROGRESS`

The Tenant Master Data Foundation builds reusable tenant-side master data for future WMS operational workflows. These records live in the authorized tenant database and are reached only through server-resolved tenant context.

Implemented:

- Product Categories: tenant database model, migration, API, frontend page, granular permissions, validation, and audit.

Not implemented yet:

- UOM and UOM conversions
- Products / SKU
- Product packaging and barcodes
- Vendors, customers, customer ship-to locations, and carriers
- Handling unit types
- Reason codes
- Inventory statuses
- Product storage rules
- Product warehouse configuration
- Master data import/export

Architecture rules:

- Master-data APIs use `/api/v1/tenant/`.
- Tenant database selection is resolved by the server from verified tenant domain/session context.
- Browser-supplied database names, aliases, schemas, hosts, users, and connection strings are never trusted.
- Control-plane data remains separate from tenant master data.
- Operational WMS transactions such as receiving, GR, putaway execution, inventory balances, picking, packing, loading, and PGI are outside this milestone.

