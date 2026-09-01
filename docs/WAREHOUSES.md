# Warehouses

Warehouses are tenant-database records and may optionally belong to a Plant.

Implemented APIs:

- `GET /api/v1/tenant/warehouses/`
- `POST /api/v1/tenant/warehouses/`
- `GET /api/v1/tenant/warehouses/<id>/`
- `PATCH /api/v1/tenant/warehouses/<id>/`
- `POST /api/v1/tenant/context/warehouse/`

The active warehouse context endpoint verifies the tenant session, active membership, active Warehouse, and active `WarehouseAssignment` before writing selected warehouse context to the session.
