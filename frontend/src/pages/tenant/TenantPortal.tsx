import { Building2, Database, Eye, Map, Warehouse } from 'lucide-react';
import type { ReactNode } from 'react';
import { useEffect, useState } from 'react';
import { apiFetch, LatticeApiError } from '../../api/client';
import { Card, DataTable, ErrorState, LoadingState, StatusBadge } from '../../design-system';
import type { CurrentUser, TenantContext } from '../../types';
import { TenantResourcePage } from './components/TenantResourcePage';
import { TenantDashboardPage } from './dashboard/TenantDashboardPage';
import { TenantShell } from './layout/TenantShell';
import { tenantResourceConfigs, tenantRouteMeta, type TenantRoute } from './tenantRoutes';

type SummaryRow = Record<'area' | 'value' | 'status', ReactNode>;

export function TenantPortal({ user, onLogout }: { user: CurrentUser; onLogout: () => void }) {
  const activeRoute = useTenantRoute();
  const [context, setContext] = useState<TenantContext | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const loadContext = async () => {
    setLoading(true);
    setError('');
    try {
      setContext(await apiFetch<TenantContext>('/api/v1/tenant/context/'));
    } catch (caught) {
      setContext(null);
      setError(caught instanceof LatticeApiError ? `${caught.code}: ${caught.message}` : 'Tenant access could not be verified for this domain and session.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadContext();
  }, []);

  return (
    <TenantShell context={context} loading={loading} onLogout={onLogout} onRefresh={loadContext} route={activeRoute} user={user}>
      {loading ? <LoadingState title="Loading tenant context" /> : null}
      {!loading && error ? <ErrorState title={error} /> : null}
      {!loading && context ? <TenantRouteContent route={activeRoute} context={context} user={user} /> : null}
    </TenantShell>
  );
}

function TenantRouteContent({ route, context, user }: { route: TenantRoute; context: TenantContext; user: CurrentUser }) {
  if (route === 'dashboard') return <TenantDashboardPage context={context} />;
  if (route === 'hierarchy') return <HierarchyPage />;
  if (route === 'configuration/transport') return <TransportPage />;
  if (route === 'warehouse-assignments') return <WarehouseAssignmentsPage context={context} />;
  if (route === 'settings') return <SettingsPage context={context} />;
  if (route === 'profile') return <ProfilePage context={context} user={user} />;
  if (route === 'security-settings') return <SecurityPage context={context} />;
  const config = tenantResourceConfigs[route];
  return config ? <TenantResourcePage config={config} /> : <TenantDashboardPage context={context} />;
}

function TransportPage() {
  return (
    <section className="tenant-page-stack">
      {(['trucks', 'containers', 'vehicles'] as const).map((type) => (
        <TenantResourcePage
          config={{
            route: 'configuration/transport',
            title: type.slice(0, 1).toUpperCase() + type.slice(1),
            description: `${type} configuration metadata only.`,
            endpoint: `/api/v1/tenant/configuration/transport/${type}/`,
            codeKey: 'code',
            nameKey: 'name',
            fields: [{ key: 'code', label: 'Code', required: true }, { key: 'name', label: 'Name', required: true }, { key: 'configuration_type', label: 'Configuration Type' }],
          }}
          key={type}
        />
      ))}
    </section>
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
      {Array.isArray(warehouse.storage_types) ? warehouse.storage_types.map((item) => <HierarchyNode icon={<Database size={16} />} label={String((item as Record<string, unknown>).name)} meta={String((item as Record<string, unknown>).storage_type_code)} key={String((item as Record<string, unknown>).id)} />) : null}
      {Array.isArray(warehouse.zones) ? warehouse.zones.map((item) => <HierarchyNode icon={<Map size={16} />} label={String((item as Record<string, unknown>).name)} meta={String((item as Record<string, unknown>).zone_code)} key={String((item as Record<string, unknown>).id)} />) : null}
      {Array.isArray(warehouse.sections) ? warehouse.sections.map((item) => <HierarchyNode icon={<Database size={16} />} label={String((item as Record<string, unknown>).name)} meta={String((item as Record<string, unknown>).section_code)} key={String((item as Record<string, unknown>).id)} />) : null}
      {Array.isArray(warehouse.bays) ? warehouse.bays.map((item) => <HierarchyNode icon={<Eye size={16} />} label={String((item as Record<string, unknown>).bay_code)} meta={String((item as Record<string, unknown>).status)} key={String((item as Record<string, unknown>).id)} />) : null}
    </HierarchyNode>
  );
}

function HierarchyNode({ children, icon, label, meta }: { children?: ReactNode; icon: ReactNode; label: string; meta: string }) {
  return (
    <details className="tenant-hierarchy-node" open>
      <summary><span>{icon}</span><strong>{label}</strong><code>{meta}</code></summary>
      {children ? <div className="tenant-hierarchy-node__children">{children}</div> : null}
    </details>
  );
}

function WarehouseAssignmentsPage({ context }: { context: TenantContext }) {
  const warehouses = context.authorization.warehouses.map((item) => typeof item === 'string' ? item : item.warehouse_code);
  return <Card title="Warehouse Assignments" variant="glass"><DataTable rows={[{ area: 'Current scope', value: warehouses.join(', ') || 'No warehouses assigned', status: badge(warehouses.length ? 'SERVER ENFORCED' : 'ATTENTION') }]} columns={summaryColumns} /></Card>;
}

function SettingsPage({ context }: { context: TenantContext }) {
  return <Card title="Tenant Settings" variant="glass"><DataTable rows={profileRows(context)} columns={summaryColumns} /></Card>;
}

function ProfilePage({ context, user }: { context: TenantContext; user: CurrentUser }) {
  return <Card title="Account Profile" variant="glass"><DataTable rows={[...profileRows(context), { area: 'Email', value: user.email, status: badge('AUTHENTICATED') }]} columns={summaryColumns} /></Card>;
}

function SecurityPage({ context }: { context: TenantContext }) {
  return <Card title="Security Posture" variant="glass"><DataTable rows={[{ area: 'MFA', value: context.session.mfa_enabled ? 'Enabled' : 'Not enrolled', status: badge(context.session.mfa_enabled ? 'OK' : 'ATTENTION') }, { area: 'Tenant database selection', value: 'Resolved by server', status: badge('FAIL CLOSED') }, { area: 'Browser token storage', value: 'HTTP-only cookie flow', status: badge('PROTECTED') }]} columns={summaryColumns} /></Card>;
}

function profileRows(context: TenantContext): SummaryRow[] {
  return [
    { area: 'Tenant', value: context.tenant.display_name, status: badge(context.tenant.status) },
    { area: 'Tenant code', value: context.tenant.tenant_code, status: badge('VERIFIED') },
    { area: 'Membership', value: context.authorization.membership_id, status: badge('ACTIVE') },
    { area: 'Roles', value: context.authorization.roles.join(', ') || 'No roles assigned', status: badge('TENANT SCOPED') },
  ];
}

function badge(status: string) {
  return <StatusBadge status={status} variant={['ACTIVE', 'OK', 'VERIFIED', 'AUTHENTICATED', 'TENANT SCOPED', 'PROTECTED', 'FAIL CLOSED', 'SERVER ENFORCED'].includes(status) ? 'success' : 'warning'} />;
}

const summaryColumns = [{ key: 'area', header: 'Area' }, { key: 'value', header: 'Value' }, { key: 'status', header: 'Status' }] satisfies { key: keyof SummaryRow; header: string }[];

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
  const pathRoute = window.location.pathname.replace(/^\/tenant\/?/, '').replace(/\/$/, '') || 'dashboard';
  if (pathRoute === 'bins') {
    window.history.replaceState(null, '', tenantRouteMeta.bays.href);
    return 'bays';
  }
  const route = pathRoute as TenantRoute;
  if (route in tenantRouteMeta) return route;
  if (window.location.pathname === '/tenant' || window.location.pathname === '/tenant/') window.history.replaceState(null, '', tenantRouteMeta.dashboard.href);
  return 'dashboard';
}
