# Warehouse Configuration

Warehouse configuration is stored in tenant databases, not the control database.

Implemented configuration models:

| Model | Table |
| --- | --- |
| Plant | `lattice_plant` |
| Warehouse | `lattice_whs` |
| StorageType | `lattice_stype` |
| Zone | `lattice_zone` |
| StorageSection | `lattice_section` |
| Bay | `lattice_bay` |
| HoldingUnit | `lattice_hu` |
| Pallet | `lattice_pall` |
| Machine | `lattice_mach` |
| PeopleResource | `lattice_ppl` |
| SkuGrouping | `lattice_skugrp` |
| InventoryCategory | `lattice_invcat` |
| OperationDefinition | `lattice_oper` |
| MissionDefinition | `lattice_misn` |
| MissionGroup | `lattice_grp` |
| ZoneQueue | `lattice_zq` |
| SequenceNumber | `lattice_seq` |
| StatusDefinition | `lattice_status` |
| WarehouseControl | `lattice_whscnt` |
| WarehouseLog | `lattice_log` |

All parent-child references are validated inside the active tenant database context.
