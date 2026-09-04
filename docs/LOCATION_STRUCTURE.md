# Location Structure

Location configuration is tenant database master data only.

Implemented APIs:

- `GET/POST /api/v1/tenant/zones/`
- `GET/PATCH /api/v1/tenant/zones/<id>/`
- `GET/POST /api/v1/tenant/storage-types/`
- `GET/PATCH /api/v1/tenant/storage-types/<id>/`
- `GET/POST /api/v1/tenant/storage-sections/`
- `GET/PATCH /api/v1/tenant/storage-sections/<id>/`
- `GET/POST /api/v1/tenant/bays/`
- `GET/PATCH /api/v1/tenant/bays/<id>/`
- `GET /api/v1/tenant/hierarchy/`

Bays support block/unblock through `is_blocked`; blocking sets the location status to `BLOCKED`. Inventory balances and transactions are not stored on Bay records in this milestone.
