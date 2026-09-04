# Tenant API

Tenant APIs live under `/api/v1/tenant/` and operate only against the server-resolved tenant database for warehouse configuration data.

Current APIs:

- `/dashboard/`, `/context/`, `/context/warehouse/`
- `/plants/`, `/warehouses/`, `/storage-types/`, `/zones/`, `/storage-sections/`, `/bays/`
- `/bays/bulk/`, `/bays/import/`, `/bays/export/`
- `/configuration/holding-units/`, `/pallets/`, `/machines/`, `/resources/`, `/sku-groups/`, `/inventory-categories/`, `/operations/`, `/missions/`, `/mission-groups/`, `/zone-queues/`, `/sequences/`, `/statuses/`, `/warehouse-control/`
- `/configuration/transport/trucks/`, `/containers/`, `/vehicles/`
- `/users/`, `/roles/`, `/permissions/`, `/warehouse-assignments/`, `/settings/`

Tenant APIs do not accept database aliases, database names, schemas, connection strings, or tenant IDs from the browser for routing.
