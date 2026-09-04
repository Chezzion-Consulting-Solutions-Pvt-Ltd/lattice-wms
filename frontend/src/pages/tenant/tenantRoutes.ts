export type TenantRoute =
  | 'dashboard'
  | 'plants'
  | 'warehouses'
  | 'storage-types'
  | 'zones'
  | 'storage-sections'
  | 'bays'
  | 'hierarchy'
  | 'configuration/holding-units'
  | 'configuration/pallets'
  | 'configuration/machines'
  | 'configuration/resources'
  | 'configuration/sku-groups'
  | 'configuration/inventory-categories'
  | 'configuration/operations'
  | 'configuration/missions'
  | 'configuration/mission-groups'
  | 'configuration/zone-queues'
  | 'configuration/sequences'
  | 'configuration/statuses'
  | 'configuration/transport'
  | 'configuration/warehouse-control'
  | 'users'
  | 'roles'
  | 'warehouse-assignments'
  | 'settings'
  | 'profile'
  | 'security-settings';

export type TenantFieldConfig = { key: string; label: string; required?: boolean; type?: string };

export type TenantResourceConfig = {
  route: TenantRoute;
  title: string;
  description: string;
  endpoint: string;
  codeKey: string;
  nameKey: string;
  fields: TenantFieldConfig[];
};

export const tenantRouteMeta: Record<TenantRoute, { title: string; description: string; href: string }> = {
  dashboard: { title: 'Tenant Dashboard', description: 'Warehouse configuration readiness and tenant administration health.', href: '/tenant/dashboard' },
  plants: { title: 'Plants', description: 'Maintain plant and site records inside the current tenant database.', href: '/tenant/plants' },
  warehouses: { title: 'Warehouses', description: 'Configure warehouses and optional plant assignment.', href: '/tenant/warehouses' },
  'storage-types': { title: 'Storage Types', description: 'Configure storage behavior and capacity flags.', href: '/tenant/storage-types' },
  zones: { title: 'Zones', description: 'Maintain warehouse zones and lifecycle state.', href: '/tenant/zones' },
  'storage-sections': { title: 'Sections', description: 'Optional warehouse structure between zone and bay.', href: '/tenant/storage-sections' },
  bays: { title: 'Bays', description: 'Maintain physical inventory bay configuration without stock execution.', href: '/tenant/bays' },
  hierarchy: { title: 'Hierarchy Browser', description: 'Browse Plant -> Warehouse -> Storage Type -> Zone -> Section -> Bay.', href: '/tenant/hierarchy' },
  'configuration/holding-units': { title: 'Holding Units', description: 'Holding unit type and capacity configuration.', href: '/tenant/configuration/holding-units' },
  'configuration/pallets': { title: 'Pallets', description: 'Pallet type and dimension configuration.', href: '/tenant/configuration/pallets' },
  'configuration/machines': { title: 'Machines', description: 'Machine and equipment configuration.', href: '/tenant/configuration/machines' },
  'configuration/resources': { title: 'Resources', description: 'People and resource capability configuration.', href: '/tenant/configuration/resources' },
  'configuration/sku-groups': { title: 'SKU Groups', description: 'SKU grouping rule metadata.', href: '/tenant/configuration/sku-groups' },
  'configuration/inventory-categories': { title: 'Inventory Categories', description: 'Inventory category definitions.', href: '/tenant/configuration/inventory-categories' },
  'configuration/operations': { title: 'Operations', description: 'Operation definition metadata only.', href: '/tenant/configuration/operations' },
  'configuration/missions': { title: 'Missions', description: 'Mission definition metadata only.', href: '/tenant/configuration/missions' },
  'configuration/mission-groups': { title: 'Mission Groups', description: 'Mission grouping configuration metadata.', href: '/tenant/configuration/mission-groups' },
  'configuration/zone-queues': { title: 'Zone Queues', description: 'Zone queue configuration metadata.', href: '/tenant/configuration/zone-queues' },
  'configuration/sequences': { title: 'Sequences', description: 'Tenant number range definitions.', href: '/tenant/configuration/sequences' },
  'configuration/statuses': { title: 'Statuses', description: 'Configurable status definitions.', href: '/tenant/configuration/statuses' },
  'configuration/transport': { title: 'Transport', description: 'Truck, container, and vehicle configuration.', href: '/tenant/configuration/transport' },
  'configuration/warehouse-control': { title: 'Warehouse Control', description: 'Tenant, plant, warehouse, and process configuration rules.', href: '/tenant/configuration/warehouse-control' },
  users: { title: 'Tenant Users', description: 'Membership, MFA posture, roles, and warehouse scope.', href: '/tenant/users' },
  roles: { title: 'Tenant Roles', description: 'Tenant-scoped role and permission definitions.', href: '/tenant/roles' },
  'warehouse-assignments': { title: 'Warehouse Assignments', description: 'Server-enforced warehouse access scope.', href: '/tenant/warehouse-assignments' },
  settings: { title: 'Tenant Settings', description: 'Tenant profile and measurement defaults.', href: '/tenant/settings' },
  profile: { title: 'Profile', description: 'Signed-in tenant account and access context.', href: '/tenant/profile' },
  'security-settings': { title: 'Security Settings', description: 'MFA, session, and tenant access protections.', href: '/tenant/security-settings' },
};

export const tenantResourceConfigs: Partial<Record<TenantRoute, TenantResourceConfig>> = {
  plants: resource('plants', 'Plants', '/api/v1/tenant/plants/', 'plant_code', 'name', ['plant_code*', 'name*', 'description', 'city', 'country', 'timezone']),
  warehouses: resource('warehouses', 'Warehouses', '/api/v1/tenant/warehouses/', 'warehouse_code', 'name', ['code*', 'name*', 'plant_id', 'warehouse_type', 'timezone']),
  'storage-types': resource('storage-types', 'Storage Types', '/api/v1/tenant/storage-types/', 'storage_type_code', 'name', ['warehouse_id*', 'storage_type_code*', 'name*', 'storage_behavior', 'capacity_method']),
  zones: resource('zones', 'Zones', '/api/v1/tenant/zones/', 'zone_code', 'name', ['warehouse_id*', 'zone_code*', 'name*', 'zone_type', 'sequence:number']),
  'storage-sections': resource('storage-sections', 'Sections', '/api/v1/tenant/storage-sections/', 'section_code', 'name', ['warehouse_id*', 'zone_id*', 'storage_type_id', 'section_code*', 'name*', 'aisle_from', 'aisle_to']),
  bays: resource('bays', 'Bays', '/api/v1/tenant/bays/', 'bay_code', 'name', ['warehouse_id*', 'zone_id*', 'storage_type_id', 'section_id', 'bay_code*', 'barcode', 'aisle', 'rack', 'level', 'position']),
  'configuration/holding-units': resource('configuration/holding-units', 'Holding Units', '/api/v1/tenant/configuration/holding-units/', 'hu_code', 'name', ['hu_code*', 'name*', 'hu_type', 'description']),
  'configuration/pallets': resource('configuration/pallets', 'Pallets', '/api/v1/tenant/configuration/pallets/', 'pallet_code', 'name', ['pallet_code*', 'name*', 'pallet_type', 'length:number', 'width:number', 'height:number']),
  'configuration/machines': resource('configuration/machines', 'Machines', '/api/v1/tenant/configuration/machines/', 'machine_code', 'name', ['warehouse_id*', 'machine_code*', 'name*', 'machine_type', 'zone_id']),
  'configuration/resources': resource('configuration/resources', 'Resources', '/api/v1/tenant/configuration/resources/', 'resource_code', 'name', ['warehouse_id*', 'resource_code*', 'name*', 'resource_type', 'user_id']),
  'configuration/sku-groups': resource('configuration/sku-groups', 'SKU Groups', '/api/v1/tenant/configuration/sku-groups/', 'group_code', 'name', ['group_code*', 'name*', 'grouping_type', 'priority:number']),
  'configuration/inventory-categories': resource('configuration/inventory-categories', 'Inventory Categories', '/api/v1/tenant/configuration/inventory-categories/', 'category_code', 'name', ['category_code*', 'name*', 'category_type']),
  'configuration/operations': resource('configuration/operations', 'Operations', '/api/v1/tenant/configuration/operations/', 'operation_code', 'name', ['operation_code*', 'name*', 'operation_type', 'sequence:number']),
  'configuration/missions': resource('configuration/missions', 'Missions', '/api/v1/tenant/configuration/missions/', 'mission_code', 'name', ['mission_code*', 'name*', 'mission_type', 'code_pattern']),
  'configuration/mission-groups': resource('configuration/mission-groups', 'Mission Groups', '/api/v1/tenant/configuration/mission-groups/', 'group_code', 'name', ['group_code*', 'name*', 'grouping_strategy', 'priority:number']),
  'configuration/zone-queues': resource('configuration/zone-queues', 'Zone Queues', '/api/v1/tenant/configuration/zone-queues/', 'queue_code', 'name', ['warehouse_id*', 'zone_id*', 'queue_code*', 'name*', 'priority:number']),
  'configuration/sequences': resource('configuration/sequences', 'Sequences', '/api/v1/tenant/configuration/sequences/', 'sequence_code', 'name', ['sequence_code*', 'name*', 'entity_type*', 'prefix', 'padding:number', 'current_value:number']),
  'configuration/statuses': resource('configuration/statuses', 'Statuses', '/api/v1/tenant/configuration/statuses/', 'status_code', 'name', ['status_code*', 'name*', 'entity_type*', 'display_order:number']),
  'configuration/warehouse-control': resource('configuration/warehouse-control', 'Warehouse Control', '/api/v1/tenant/configuration/warehouse-control/', 'scope', 'process', ['scope*', 'process', 'name']),
  users: resource('users', 'Tenant Users', '/api/v1/tenant/users/', 'email', 'status', ['email*']),
  roles: resource('roles', 'Tenant Roles', '/api/v1/tenant/roles/', 'code', 'name', ['code*', 'name*']),
};

function resource(route: TenantRoute, title: string, endpoint: string, codeKey: string, nameKey: string, fields: string[]): TenantResourceConfig {
  return {
    route,
    title,
    endpoint,
    codeKey,
    nameKey,
    description: tenantRouteMeta[route].description,
    fields: fields.map((field) => {
      const [rawKey, type] = field.replace('*', '').split(':');
      const key = rawKey ?? field.replace('*', '');
      return type ? { key, label: toLabel(key), required: field.includes('*'), type } : { key, label: toLabel(key), required: field.includes('*') };
    }),
  };
}

function toLabel(key: string) {
  return key.split('_').map((part) => part.slice(0, 1).toUpperCase() + part.slice(1)).join(' ');
}
