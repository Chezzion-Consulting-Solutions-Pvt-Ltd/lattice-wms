# Warehouse Hierarchy

Lattice hierarchy:

Tenant -> Plant -> Warehouse -> Storage Type -> Zone -> Section -> Bay

Sections are optional. Bays may reference a section when that organization layer is used.

Validation rules:

- Warehouse references only a plant from the same tenant database.
- Storage types, zones, sections, and bays are warehouse-scoped.
- Sections must reference a zone and optional storage type from the same warehouse.
- Bays must reference warehouse, zone, optional storage type, and optional section consistently.
- Warehouse assignment authorization is enforced server-side.
