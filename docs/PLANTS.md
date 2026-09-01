# Plants / Sites

Plants are optional tenant-database master records.

Implemented fields include code, name, description, status, address fields, timezone, coordinates, contact fields, timestamps, and immutable actor UUID references.

Implemented APIs:

- `GET /api/v1/tenant/plants/`
- `POST /api/v1/tenant/plants/`
- `GET /api/v1/tenant/plants/<id>/`
- `PATCH /api/v1/tenant/plants/<id>/`

Plant codes are unique within the tenant database. Normal lifecycle uses status changes such as `ACTIVE`, `INACTIVE`, `BLOCKED`, and `ARCHIVED`; referenced plants should not be hard-deleted.
