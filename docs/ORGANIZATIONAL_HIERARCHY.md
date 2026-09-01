# Organizational Hierarchy

Lattice stores tenant hierarchy records in each tenant database, not in the control database.

Supported hierarchy:

- Tenant
- optional Plant / Site
- Warehouse
- Zone
- optional Storage Type
- optional Storage Section
- Bin / Location

Plant is optional. A small tenant can operate directly from Tenant to Warehouse, while larger tenants can use Plant to group warehouses.

Server-side validation enforces parent-child consistency. A Section or Bin cannot combine a Warehouse with a Zone, Storage Type, or Section from another Warehouse.
