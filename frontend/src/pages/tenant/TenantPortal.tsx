import { Building2, Database, Eye, Map, Plus, RefreshCw, Save, Settings, Shield, Warehouse } from 'lucide-react';
import type { FormEvent, ReactNode } from 'react';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { apiFetch, LatticeApiError } from '../../api/client';
import { AppShell, Button, Card, DataTable, Dialog, DialogClose, ErrorState, FormField, Input, LoadingState, PageHeader, StatusBadge } from '../../design-system';
import type { CurrentUser, TenantContext } from '../../types';

type TenantRoute =
  | 'dashboard'
  | 'product-categories'
  | 'plants'
  | 'warehouses'
  | 'zones'
  | 'storage-types'
  | 'storage-sections'
  | 'bins'
  | 'hierarchy'
  | 'users-access'
  | 'settings'
  | 'profile'
  | 'security-settings';
type Row = Record<string, ReactNode>;
type SummaryRow = Record<'area' | 'value' | 'status', ReactNode>;

type ResourceConfig = {
  route: TenantRoute;
  title: string;
  description: string;
  endpoint: string;
  codeKey: string;
  nameKey: string;
  createFields: Array<{ key: string; label: string; required?: boolean; type?: string }>;
};

const routeMeta: Record<TenantRoute, { title: string; description: string; href: string }> = {
  dashboard: { title: 'Tenant Dashboard', description: 'Configuration health, access scope, and tenant administration readiness.', href: '/tenant/dashboard' },
  'product-categories': { title: 'Product Categories', description: 'Maintain reusable hierarchical SKU category master data in this tenant database.', href: '/tenant/product-categories' },
  plants: { title: 'Plants / Sites', description: 'Create and maintain tenant plant or site records.', href: '/tenant/plants' },
  warehouses: { title: 'Warehouses', description: 'Configure tenant warehouses with optional plant assignment.', href: '/tenant/warehouses' },
  zones: { title: 'Zones', description: 'Maintain warehouse zones and lifecycle status.', href: '/tenant/zones' },
  'storage-types': { title: 'Storage Types', description: 'Configure physical storage characteristics per warehouse.', href: '/tenant/storage-types' },
  'storage-sections': { title: 'Storage Sections', description: 'Create optional sections for aisles, rows, blocks, and areas.', href: '/tenant/storage-sections' },
  bins: { title: 'Bins / Locations', description: 'Maintain lowest-level physical locations without inventory balances.', href: '/tenant/bins' },
  hierarchy: { title: 'Hierarchy Browser', description: 'Browse the real plant, warehouse, zone, section, and bin structure.', href: '/tenant/hierarchy' },
  'users-access': { title: 'Users & Access', description: 'Tenant membership, role, permission, MFA, and warehouse scope summary.', href: '/tenant/users-access' },
  settings: { title: 'Settings', description: 'Tenant profile, modules, and workspace settings.', href: '/tenant/settings' },
  profile: { title: 'Profile', description: 'Signed-in tenant account, membership, and portal access.', href: '/tenant/profile' },
  'security-settings': { title: 'Security Settings', description: 'MFA posture, session handling, and tenant access protections.', href: '/tenant/security-settings' },
};

const resourceConfigs: Partial<Record<TenantRoute, ResourceConfig>> = {
  'product-categories': {
    route: 'product-categories',
    title: 'Product Categories',
    description: 'Category code must be unique inside this tenant database. Parent category is optional.',
    endpoint: '/api/v1/tenant/product-categories/',
    codeKey: 'category_code',
    nameKey: 'name',
    createFields: [
      { key: 'category_code', label: 'Category Code', required: true },
      { key: 'name', label: 'Name', required: true },
      { key: 'description', label: 'Description' },
      { key: 'parent_category_id', label: 'Parent Category ID' },
    ],
  },
  plants: {
    route: 'plants',
    title: 'Plants / Sites',
    description: 'Plant code must be unique inside this tenant database.',
    endpoint: '/api/v1/tenant/plants/',
    codeKey: 'plant_code',
    nameKey: 'name',
    createFields: [
      { key: 'plant_code', label: 'Plant Code', required: true },
      { key: 'name', label: 'Name', required: true },
      { key: 'city', label: 'City' },
      { key: 'country', label: 'Country' },
      { key: 'timezone', label: 'Timezone' },
    ],
  },
  warehouses: {
    route: 'warehouses',
    title: 'Warehouses',
    description: 'Warehouse can be direct-to-tenant or assigned to a plant.',
    endpoint: '/api/v1/tenant/warehouses/',
    codeKey: 'warehouse_code',
    nameKey: 'name',
    createFields: [
      { key: 'code', label: 'Warehouse Code', required: true },
      { key: 'name', label: 'Name', required: true },
      { key: 'plant_id', label: 'Plant ID' },
      { key: 'warehouse_type', label: 'Warehouse Type' },
      { key: 'timezone', label: 'Timezone' },
    ],
  },
  zones: {
    route: 'zones',
    title: 'Zones',
    description: 'Zones belong to a warehouse and use controlled zone types.',
    endpoint: '/api/v1/tenant/zones/',
    codeKey: 'zone_code',
    nameKey: 'name',
    createFields: [
      { key: 'warehouse_id', label: 'Warehouse ID', required: true },
      { key: 'zone_code', label: 'Zone Code', required: true },
      { key: 'name', label: 'Name', required: true },
      { key: 'zone_type', label: 'Zone Type' },
      { key: 'sequence', label: 'Sequence', type: 'number' },
    ],
  },
  'storage-types': {
    route: 'storage-types',
    title: 'Storage Types',
    description: 'Storage types belong to a warehouse and stay configurable.',
    endpoint: '/api/v1/tenant/storage-types/',
    codeKey: 'storage_type_code',
    nameKey: 'name',
    createFields: [
      { key: 'warehouse_id', label: 'Warehouse ID', required: true },
      { key: 'storage_type_code', label: 'Storage Type Code', required: true },
      { key: 'name', label: 'Name', required: true },
    ],
  },
  'storage-sections': {
    route: 'storage-sections',
    title: 'Storage Sections',
    description: 'Sections must reference hierarchy records from the same warehouse.',
    endpoint: '/api/v1/tenant/storage-sections/',
    codeKey: 'section_code',
    nameKey: 'name',
    createFields: [
      { key: 'warehouse_id', label: 'Warehouse ID', required: true },
      { key: 'zone_id', label: 'Zone ID', required: true },
      { key: 'storage_type_id', label: 'Storage Type ID' },
      { key: 'section_code', label: 'Section Code', required: true },
      { key: 'name', label: 'Name', required: true },
      { key: 'sequence', label: 'Sequence', type: 'number' },
    ],
  },
  bins: {
    route: 'bins',
    title: 'Bins / Locations',
    description: 'Bins are location master data only; no stock quantities are stored here.',
    endpoint: '/api/v1/tenant/bins/',
    codeKey: 'bin_code',
    nameKey: 'barcode',
    createFields: [
      { key: 'warehouse_id', label: 'Warehouse ID', required: true },
      { key: 'zone_id', label: 'Zone ID', required: true },
      { key: 'storage_type_id', label: 'Storage Type ID' },
      { key: 'section_id', label: 'Section ID' },
      { key: 'bin_code', label: 'Bin Code', required: true },
      { key: 'barcode', label: 'Barcode' },
      { key: 'aisle', label: 'Aisle' },
      { key: 'bay', label: 'Bay' },
      { key: 'level', label: 'Level' },
      { key: 'position', label: 'Position' },
    ],
  },
};

export function TenantPortal({ user, onLogout }: { user: CurrentUser; onLogout: () => void }) {
  const activeRoute = useTenantRoute();
  const meta = routeMeta[activeRoute];
  const [context, setContext] = useState<TenantContext | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const loadContext = async () => {
    setLoading(true);
    setError('');
    try {
      setContext(await apiFetch<TenantContext>('/api/v1/tenant/context/'));
    } catch {
      setContext(null);
      setError('Tenant access could not be verified for this domain and session.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadContext();
  }, []);

  return (
    <AppShell title={context?.tenant.display_name ?? 'Tenant Portal'} mode="client" profileLabel={getInitials(user)} profileName={getDisplayName(user)} profileDescription="Tenant user" activeHref={meta.href} onLogout={onLogout}>
      <PageHeader title={meta.title} description={meta.description} actions={<Button variant="secondary" icon={<RefreshCw size={16} />} onClick={loadContext}>Refresh</Button>} />
      {loading ? <LoadingState title="Loading tenant context" /> : null}
      {!loading && error ? <ErrorState title={error} /> : null}
      {!loading && context ? <TenantRouteContent route={activeRoute} context={context} user={user} /> : null}
    </AppShell>
  );
}

function TenantRouteContent({ route, context, user }: { route: TenantRoute; context: TenantContext; user: CurrentUser }) {
  const config = resourceConfigs[route];
  if (config) return <ResourcePage config={config} />;
  if (route === 'hierarchy') return <HierarchyPage />;
  if (route === 'users-access') return <UsersAccessPage context={context} />;
  if (route === 'settings') return <SettingsPage context={context} />;
  if (route === 'profile') return <TenantProfilePage context={context} user={user} />;
  if (route === 'security-settings') return <TenantSecuritySettingsPage context={context} user={user} />;
  return <TenantDashboard context={context} />;
}

function ResourcePage({ config }: { config: ResourceConfig }) {
  const [rows, setRows] = useState<Array<Record<string, unknown>>>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const loadRows = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const payload = await apiFetch<{ results: Array<Record<string, unknown>> }>(config.endpoint);
      setRows(payload.results);
    } catch (caught) {
      setRows([]);
      setError(caught instanceof LatticeApiError ? `${caught.code}: ${caught.message}` : 'Unable to load records.');
    } finally {
      setLoading(false);
    }
  }, [config.endpoint]);

  useEffect(() => {
    void loadRows();
  }, [loadRows]);

  const tableRows = useMemo<Row[]>(
    () => rows.map((row) => ({
      code: String(row[config.codeKey] ?? ''),
      name: String(row[config.nameKey] ?? row.name ?? ''),
      status: <StatusBadge status={String(row.status ?? 'ACTIVE')} variant={String(row.status ?? 'ACTIVE') === 'ACTIVE' ? 'success' : 'warning'} />,
      id: <code>{String(row.id ?? '')}</code>,
    })),
    [config.codeKey, config.nameKey, rows],
  );

  return (
    <section className="tenant-page-stack">
      <Card title={config.title} description={config.description} actions={<CreateRecordDialog config={config} onCreated={() => void loadRows()} />} variant="glass">
        {loading ? <LoadingState title="Loading records" /> : null}
        {!loading && error ? <ErrorState title={error} /> : null}
        {!loading && !error ? (
          <DataTable rows={tableRows} columns={[{ key: 'code', header: 'Code' }, { key: 'name', header: 'Name' }, { key: 'status', header: 'Status' }, { key: 'id', header: 'ID' }]} searchable pagination emptyMessage="No records created yet." />
        ) : null}
      </Card>
    </section>
  );
}

function CreateRecordDialog({ config, onCreated }: { config: ResourceConfig; onCreated: () => void }) {
  const [form, setForm] = useState<Record<string, string>>({ status: 'ACTIVE', timezone: 'UTC', zone_type: 'STORAGE' });
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setSaving(true);
    setError('');
    try {
      const payload = Object.fromEntries(Object.entries(form).filter(([, value]) => value !== '').map(([key, value]) => [key, key === 'sequence' ? Number(value) : value]));
      await apiFetch(config.endpoint, { body: JSON.stringify(payload), method: 'POST' });
      setForm({ status: 'ACTIVE', timezone: 'UTC', zone_type: 'STORAGE' });
      onCreated();
    } catch (caught) {
      setError(caught instanceof LatticeApiError ? `${caught.code}: ${caught.message}` : 'Unable to save record.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog title={`Create ${config.title}`} description="Saved through the tenant API into the current tenant database." trigger={<Button icon={<Plus size={16} />}>Create</Button>}>
      <form className="owner-form-grid" onSubmit={submit}>
        {config.createFields.map((field) => (
          <FormField label={field.label} key={field.key}>
            <Input required={field.required} type={field.type ?? 'text'} value={form[field.key] ?? ''} onChange={(event) => setForm((current) => ({ ...current, [field.key]: event.target.value }))} />
          </FormField>
        ))}
        <FormField label="Status">
          <Input value={form.status ?? 'ACTIVE'} onChange={(event) => setForm((current) => ({ ...current, status: event.target.value }))} />
        </FormField>
        {error ? <div className="login-error">{error}</div> : null}
        <div className="lattice-dialog__actions">
          <DialogClose><Button variant="secondary" type="button">Cancel</Button></DialogClose>
          <Button disabled={saving} icon={<Save size={16} />} type="submit">{saving ? 'Saving' : 'Save'}</Button>
        </div>
      </form>
    </Dialog>
  );
}

function HierarchyPage() {
  const [tree, setTree] = useState<{ plants: Array<Record<string, unknown>>; direct_warehouses: Array<Record<string, unknown>> } | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    apiFetch<{ plants: Array<Record<string, unknown>>; direct_warehouses: Array<Record<string, unknown>> }>('/api/v1/tenant/hierarchy/')
      .then(setTree)
      .catch((caught) => setError(caught instanceof LatticeApiError ? `${caught.code}: ${caught.message}` : 'Unable to load hierarchy.'));
  }, []);

  if (error) return <ErrorState title={error} />;
  if (!tree) return <LoadingState title="Loading hierarchy" />;
  return (
    <Card title="Hierarchy Browser" variant="glass">
      <div className="tenant-hierarchy-browser">
        {tree.plants.map((plant) => (
          <HierarchyNode icon={<Building2 size={16} />} label={String(plant.name)} meta={String(plant.plant_code)} key={String(plant.id)}>
            {Array.isArray(plant.warehouses) ? plant.warehouses.map((warehouse) => <WarehouseNode warehouse={warehouse as Record<string, unknown>} key={String((warehouse as Record<string, unknown>).id)} />) : null}
          </HierarchyNode>
        ))}
        {tree.direct_warehouses.map((warehouse) => <WarehouseNode warehouse={warehouse} key={String(warehouse.id)} />)}
      </div>
    </Card>
  );
}

function WarehouseNode({ warehouse }: { warehouse: Record<string, unknown> }) {
  return (
    <HierarchyNode icon={<Warehouse size={16} />} label={String(warehouse.name)} meta={String(warehouse.warehouse_code)}>
      {Array.isArray(warehouse.zones) ? warehouse.zones.map((zone) => <HierarchyNode icon={<Map size={16} />} label={String((zone as Record<string, unknown>).name)} meta={String((zone as Record<string, unknown>).zone_code)} key={String((zone as Record<string, unknown>).id)} />) : null}
      {Array.isArray(warehouse.sections) ? warehouse.sections.map((section) => <HierarchyNode icon={<Database size={16} />} label={String((section as Record<string, unknown>).name)} meta={String((section as Record<string, unknown>).section_code)} key={String((section as Record<string, unknown>).id)} />) : null}
      {Array.isArray(warehouse.bins) ? warehouse.bins.map((bin) => <HierarchyNode icon={<Eye size={16} />} label={String((bin as Record<string, unknown>).bin_code)} meta={String((bin as Record<string, unknown>).status)} key={String((bin as Record<string, unknown>).id)} />) : null}
    </HierarchyNode>
  );
}

function HierarchyNode({ icon, label, meta, children }: { icon: ReactNode; label: string; meta: string; children?: ReactNode }) {
  return (
    <details className="tenant-hierarchy-node" open>
      <summary><span>{icon}</span><strong>{label}</strong><code>{meta}</code></summary>
      {children ? <div className="tenant-hierarchy-node__children">{children}</div> : null}
    </details>
  );
}

function TenantDashboard({ context }: { context: TenantContext }) {
  return (
    <section className="tenant-page-stack">
      <div className="tenant-portal-grid">
        <MetricCard icon={<Building2 size={18} />} title="Plants" value={context.counts.plants} />
        <MetricCard icon={<Warehouse size={18} />} title="Warehouses" value={context.counts.warehouses} />
        <MetricCard icon={<Database size={18} />} title="Zones" value={context.counts.zones} />
        <MetricCard icon={<Database size={18} />} title="Bins" value={context.counts.bins} />
        <MetricCard icon={<Shield size={18} />} title="Active Users" value={context.counts.active_users} />
        <MetricCard icon={<Settings size={18} />} title="Enabled Modules" value={context.counts.enabled_modules} />
      </div>
      <Card title="Tenant Administration Health" variant="glass">
        <DataTable rows={tenantHealthRows(context)} columns={summaryColumns} />
      </Card>
    </section>
  );
}

function UsersAccessPage({ context }: { context: TenantContext }) {
  return (
    <Card title="Access Summary" variant="glass">
      <DataTable rows={[
        { area: 'Active users', value: context.counts.active_users, status: <StatusBadge status="CONTROL DB" variant="info" /> },
        { area: 'Roles', value: context.authorization.roles.join(', ') || 'No roles assigned', status: <StatusBadge status="TENANT SCOPED" variant="success" /> },
        { area: 'Permissions', value: context.authorization.permissions.length, status: <StatusBadge status="EFFECTIVE" variant="success" /> },
        { area: 'MFA', value: context.session.mfa_enabled ? 'Enabled' : 'Not enrolled', status: <StatusBadge status={context.session.mfa_enabled ? 'OK' : 'ATTENTION'} variant={context.session.mfa_enabled ? 'success' : 'warning'} /> },
      ]} columns={summaryColumns} />
    </Card>
  );
}

function SettingsPage({ context }: { context: TenantContext }) {
  return (
    <section className="tenant-page-stack">
      <Card title="Tenant Profile" variant="glass"><DataTable rows={tenantProfileRows(context)} columns={summaryColumns} /></Card>
      <Card title="Enabled Modules" variant="glass"><DataTable rows={context.modules.map((module) => ({ area: module, value: 'Enabled', status: <StatusBadge status="ACTIVE" variant="success" /> }))} columns={summaryColumns} emptyMessage="No modules are enabled for this tenant yet." /></Card>
    </section>
  );
}

function TenantProfilePage({ context, user }: { context: TenantContext; user: CurrentUser }) {
  return (
    <section className="tenant-page-stack">
      <Card title="Account Profile" variant="glass">
        <DataTable
          rows={[
            { area: 'Name', value: getDisplayName(user), status: <StatusBadge status="ACTIVE" variant="success" /> },
            { area: 'Email', value: user.email, status: <StatusBadge status="VERIFIED" variant="success" /> },
            { area: 'Tenant', value: context.tenant.display_name, status: <StatusBadge status={context.tenant.status} variant="success" /> },
            { area: 'Membership', value: context.authorization.membership_id, status: <StatusBadge status="ACTIVE" variant="success" /> },
            { area: 'Roles', value: context.authorization.roles.join(', ') || 'No roles assigned', status: <StatusBadge status="TENANT SCOPED" variant="success" /> },
          ]}
          columns={summaryColumns}
        />
      </Card>
      <Card title="Access Boundary" variant="glass">
        <DataTable
          rows={[
            { area: 'Warehouse scope', value: context.authorization.warehouses.length, status: <StatusBadge status="SERVER ENFORCED" variant="success" /> },
            { area: 'Active warehouse', value: context.session.active_warehouse ?? 'Not selected', status: <StatusBadge status="SESSION" variant="info" /> },
            { area: 'Permissions', value: context.authorization.permissions.length, status: <StatusBadge status="EFFECTIVE" variant="success" /> },
          ]}
          columns={summaryColumns}
        />
      </Card>
    </section>
  );
}

function TenantSecuritySettingsPage({ context, user }: { context: TenantContext; user: CurrentUser }) {
  return (
    <section className="tenant-page-stack">
      <Card title="Security Posture" variant="glass">
        <DataTable
          rows={[
            { area: 'MFA', value: context.session.mfa_enabled ? 'Enabled' : 'Not enrolled', status: <StatusBadge status={context.session.mfa_enabled ? 'OK' : 'ATTENTION'} variant={context.session.mfa_enabled ? 'success' : 'warning'} /> },
            { area: 'Session', value: 'Backend cookie session', status: <StatusBadge status="ACTIVE" variant="success" /> },
            { area: 'Browser token storage', value: 'No access token stored', status: <StatusBadge status="PROTECTED" variant="success" /> },
            { area: 'Tenant database selection', value: 'Resolved by server-side tenant context', status: <StatusBadge status="FAIL CLOSED" variant="success" /> },
          ]}
          columns={summaryColumns}
        />
      </Card>
      <Card title="Signed-In Account" variant="glass">
        <DataTable
          rows={[
            { area: 'Email', value: user.email, status: <StatusBadge status="AUTHENTICATED" variant="success" /> },
            { area: 'Tenant', value: context.tenant.tenant_code, status: <StatusBadge status="VERIFIED DOMAIN" variant="success" /> },
          ]}
          columns={summaryColumns}
        />
      </Card>
    </section>
  );
}

function MetricCard({ icon, title, value }: { icon: ReactNode; title: string; value: number | string }) {
  return <Card title={title} variant="glass"><div className="tenant-portal-card"><span className="tenant-portal-card__icon">{icon}</span><strong>{value}</strong></div></Card>;
}

const summaryColumns = [
  { key: 'area', header: 'Area' },
  { key: 'value', header: 'Value' },
  { key: 'status', header: 'Status' },
] satisfies { key: keyof SummaryRow; header: string }[];

function tenantHealthRows(context: TenantContext): SummaryRow[] {
  const warehouseStatus = context.authorization.warehouses.length > 0 ? 'READY' : 'ATTENTION';
  return [
    { area: 'Tenant', value: context.tenant.display_name, status: <StatusBadge status={context.tenant.status} variant="success" /> },
    { area: 'License', value: context.tenant.license_number, status: <StatusBadge status="ISSUED" variant="success" /> },
    { area: 'Warehouse scope', value: context.authorization.warehouses.length, status: <StatusBadge status={warehouseStatus} variant={warehouseStatus === 'READY' ? 'success' : 'warning'} /> },
    { area: 'Active warehouse', value: context.session.active_warehouse ?? 'Not selected', status: <StatusBadge status="SESSION" variant="info" /> },
  ];
}

function tenantProfileRows(context: TenantContext): SummaryRow[] {
  return [
    { area: 'Tenant code', value: context.tenant.tenant_code, status: <StatusBadge status="VERIFIED" variant="success" /> },
    { area: 'Tenant status', value: context.tenant.status, status: <StatusBadge status={context.tenant.status} variant="success" /> },
    { area: 'Membership', value: context.authorization.membership_id, status: <StatusBadge status="ACTIVE" variant="success" /> },
  ];
}

function useTenantRoute() {
  const [route, setRoute] = useState<TenantRoute>(() => getTenantRouteFromLocation());
  useEffect(() => {
    const onRouteChange = () => setRoute(getTenantRouteFromLocation());
    window.addEventListener('popstate', onRouteChange);
    return () => window.removeEventListener('popstate', onRouteChange);
  }, []);
  return route;
}

function getTenantRouteFromLocation(): TenantRoute {
  const pathRoute = window.location.pathname.replace(/^\/tenant\/?/, '').replace(/\/$/, '');
  const candidate = (pathRoute || 'dashboard') as TenantRoute;
  const route = candidate in routeMeta ? candidate : 'dashboard';
  if (window.location.pathname === '/tenant' || window.location.pathname === '/tenant/') window.history.replaceState(null, '', routeMeta.dashboard.href);
  return route;
}

function getDisplayName(user: CurrentUser) {
  return [user.first_name, user.last_name].filter(Boolean).join(' ').trim() || user.email;
}

function getInitials(user: CurrentUser) {
  const parts = getDisplayName(user).split(/[.\s@_-]+/).filter(Boolean);
  return parts.slice(0, 2).map((part) => part[0]?.toUpperCase()).join('') || 'LU';
}
