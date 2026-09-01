# Product Master

Status: `IN PROGRESS`

Implemented first:

- Product Category master data with hierarchical parent categories.
- `category_code` uniqueness inside the tenant database.
- Lifecycle status using `ACTIVE`, `INACTIVE`, `BLOCKED`, and `ARCHIVED`.
- Backend validation preventing self-parent and cyclic category hierarchy assignments.
- Audit events for create, update, and status change.

Pending:

- Product / SKU model and pages
- Base UOM assignment
- Product-specific UOM conversions
- Packaging, barcode, tracking, storage-rule, and warehouse-configuration tabs

