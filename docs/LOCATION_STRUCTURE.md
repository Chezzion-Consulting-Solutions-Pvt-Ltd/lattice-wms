# Location Structure

Location configuration is tenant database master data only.

Implemented APIs:

- `GET/POST /api/v1/tenant/zones/`
- `GET/PATCH /api/v1/tenant/zones/<id>/`
- `GET/POST /api/v1/tenant/storage-types/`
- `GET/PATCH /api/v1/tenant/storage-types/<id>/`
- `GET/POST /api/v1/tenant/storage-sections/`
- `GET/PATCH /api/v1/tenant/storage-sections/<id>/`
- `GET/POST /api/v1/tenant/bins/`
- `GET/PATCH /api/v1/tenant/bins/<id>/`
- `GET /api/v1/tenant/hierarchy/`

Bins support block/unblock through `is_blocked`; blocking sets the location status to `BLOCKED`. Inventory balances and transactions are not stored on Bin records in this milestone.
