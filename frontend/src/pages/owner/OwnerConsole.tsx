import { CheckCircle2, Database, Eye, HardDrive, PauseCircle, Pencil, PlayCircle, Plus, RefreshCw, Server, ShieldAlert, Users } from 'lucide-react';
import { FormEvent, ReactNode, useCallback, useEffect, useState } from 'react';
import { apiFetch, LatticeApiError } from '../../api/client';
import { AppShell, Badge, Button, Card, DataTable, Dialog, DialogClose, ErrorState, FormField, Input, LoadingState, PageHeader, StatCard, StatusBadge } from '../../design-system';
import type { CurrentUser } from '../../types';

type Health = {
  status: string;
};

type OwnerDashboard = {
  generated_at: string;
  summary: {
    total_tenants: number;
    active_tenants: number;
    suspended_tenants: number;
    ready_databases: number;
    healthy_databases: number;
    database_warnings: number;
    migration_warnings: number;
    backup_warnings: number | null;
    backup_status: string;
    license_count: number;
    active_users: number;
    roles: number;
    permissions: number;
    security_alerts: number;
    active_support_grants: number;
  };
  infrastructure: {
    database_health: string;
    storage_usage: string;
    backup_status: string;
    migration_status: string;
    service_health: string;
  };
  tenant_health: TenantRecord[];
  platform_health: Record<string, ServiceStatus>;
  recent_security_events: AuditEventRecord[];
  recent_activity: AuditEventRecord[];
  subscription_license_attention: LicenseAttention[];
  provisioning_activity: TenantRecord[];
};

type TenantRecord = {
  id: string;
  tenant_code: string;
  display_name: string;
  legal_name: string;
  license_number: string;
  status: string;
  primary_domain: string;
  region: string;
  timezone: string;
  default_language: string;
  subscription_plan: string;
  subscription_status: string;
  created_at: string;
  database: {
    alias: string;
    host_reference: string;
    port: number;
    name: string;
    runtime_role: string;
    sslmode: string;
    provisioning_status: string;
    health_status: string;
    migration_version: string;
    last_health_check: string | null;
  } | null;
};

type ServiceStatus = {
  status: string;
  detail: string;
};

type AuditEventRecord = {
  event_id: string;
  timestamp: string;
  action: string;
  result: string;
  resource_type: string;
  request_id: string;
  failure_reason: string;
};

type LicenseAttention = {
  tenant: string;
  tenant_code: string;
  license_number: string;
  subscription_status: string;
};

type OwnerRoute =
  | 'dashboard'
  | 'tenants'
  | 'tenants/new'
  | 'plans'
  | 'subscriptions'
  | 'licenses'
  | 'modules'
  | 'features'
  | 'users'
  | 'roles'
  | 'permissions'
  | 'support-access'
  | 'infrastructure/databases'
  | 'infrastructure/migrations'
  | 'infrastructure/backups'
  | 'infrastructure/restore'
  | 'infrastructure/health'
  | 'security/events'
  | 'security/audit'
  | 'security/sessions'
  | 'security/mfa'
  | 'reports'
  | 'settings'
  | 'settings/security'
  | 'settings/authentication'
  | 'settings/provisioning'
  | 'settings/notifications'
  | 'settings/branding'
  | 'profile'
  | 'security-settings';

const ownerRouteMeta: Record<OwnerRoute, { title: string; description: string; href: string }> = {
  dashboard: {
    title: 'Platform Dashboard',
    description: 'SaaS platform health, tenant attention, and control-plane signals.',
    href: '/owner/dashboard',
  },
  tenants: {
    title: 'Tenants',
    description: 'Tenant lifecycle, license, provisioning, database, and subscription status.',
    href: '/owner/tenants',
  },
  'tenants/new': {
    title: 'Create Tenant',
    description: 'Provision new tenant control-plane records and database mappings.',
    href: '/owner/tenants/new',
  },
  plans: {
    title: 'Plans',
    description: 'Commercial plan definitions, limits, modules, and support tiers.',
    href: '/owner/plans',
  },
  subscriptions: {
    title: 'Subscriptions',
    description: 'Tenant subscription state, renewal posture, and plan assignments.',
    href: '/owner/subscriptions',
  },
  licenses: {
    title: 'Licenses',
    description: 'Tenant license status, renewals, expiry, and revocation controls.',
    href: '/owner/licenses',
  },
  modules: {
    title: 'Modules',
    description: 'Global WMS module definitions and activation state.',
    href: '/owner/modules',
  },
  features: {
    title: 'Feature Flags',
    description: 'Global feature flags and tenant override state.',
    href: '/owner/features',
  },
  users: {
    title: 'Platform Users',
    description: 'Platform users, MFA posture, and session counts.',
    href: '/owner/users',
  },
  roles: {
    title: 'Roles',
    description: 'Platform roles and assigned permission codes.',
    href: '/owner/roles',
  },
  permissions: {
    title: 'Permissions',
    description: 'Grouped platform permission registry.',
    href: '/owner/permissions',
  },
  'support-access': {
    title: 'Support Access',
    description: 'Time-bounded owner-approved tenant support access grants.',
    href: '/owner/support-access',
  },
  'infrastructure/databases': {
    title: 'Tenant Databases',
    description: 'Safe tenant database metadata, health, migration, and provisioning state.',
    href: '/owner/infrastructure/databases',
  },
  'infrastructure/migrations': {
    title: 'Migrations',
    description: 'Tenant migration status and attention items.',
    href: '/owner/infrastructure/migrations',
  },
  'infrastructure/backups': {
    title: 'Backups',
    description: 'Backup policies and provider status without fake backup success.',
    href: '/owner/infrastructure/backups',
  },
  'infrastructure/restore': {
    title: 'Restore Requests',
    description: 'Controlled restore requests and provider-dependent execution state.',
    href: '/owner/infrastructure/restore',
  },
  'infrastructure/health': {
    title: 'Service Health',
    description: 'Backend, PostgreSQL, Redis, Celery, and tenant database health checks.',
    href: '/owner/infrastructure/health',
  },
  'security/events': {
    title: 'Security Events',
    description: 'Denied and failed control-plane events with safe request details.',
    href: '/owner/security/events',
  },
  'security/audit': {
    title: 'Audit Logs',
    description: 'Append-only owner audit history and mutation records.',
    href: '/owner/security/audit',
  },
  'security/sessions': {
    title: 'Sessions',
    description: 'Platform security sessions and revocation state.',
    href: '/owner/security/sessions',
  },
  'security/mfa': {
    title: 'MFA Compliance',
    description: 'Privileged platform user MFA compliance posture.',
    href: '/owner/security/mfa',
  },
  reports: {
    title: 'Reports',
    description: 'Control-plane operational reports and exported platform summaries.',
    href: '/owner/reports',
  },
  settings: {
    title: 'General Settings',
    description: 'Platform display name, defaults, domain, and support metadata.',
    href: '/owner/settings',
  },
  'settings/security': {
    title: 'Security Settings',
    description: 'Persisted platform security policy values.',
    href: '/owner/settings/security',
  },
  'settings/authentication': {
    title: 'Authentication Settings',
    description: 'Password, MFA, session, and future federation policy metadata.',
    href: '/owner/settings/authentication',
  },
  'settings/provisioning': {
    title: 'Provisioning Settings',
    description: 'Safe tenant provisioning defaults and migration policy metadata.',
    href: '/owner/settings/provisioning',
  },
  'settings/notifications': {
    title: 'Notification Settings',
    description: 'Owner notification policy and unread operational alerts.',
    href: '/owner/settings/notifications',
  },
  'settings/branding': {
    title: 'Branding Settings',
    description: 'Safe Lattice branding metadata without arbitrary CSS or JavaScript.',
    href: '/owner/settings/branding',
  },
  profile: {
    title: 'Profile',
    description: 'Signed-in platform account, role posture, and console access.',
    href: '/owner/profile',
  },
  'security-settings': {
    title: 'Security Settings',
    description: 'MFA posture, secure session behavior, and account protections.',
    href: '/owner/security-settings',
  },
};

export function OwnerConsole({
  user,
  onAuthorizationLost,
  onLogout,
}: {
  user: CurrentUser;
  onAuthorizationLost: () => void;
  onLogout: () => void;
}) {
  const activeRoute = useOwnerRoute();
  const [health, setHealth] = useState<string>('checking');
  const [dashboard, setDashboard] = useState<OwnerDashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string>('');
  const [selectedTenantId, setSelectedTenantId] = useState<string>('');

  const refresh = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const [healthData, dashboardData] = await Promise.all([apiFetch<Health>('/health/live'), apiFetch<OwnerDashboard>('/api/v1/control/owner/dashboard/')]);
      setHealth(healthData.status);
      setDashboard(dashboardData);
    } catch (caught: unknown) {
      setDashboard(null);
      if (caught instanceof LatticeApiError) {
        if (caught.status === 401 || caught.status === 403) {
          onAuthorizationLost();
          return;
        }
        setError(`${caught.code}: ${caught.message}`);
        return;
      }
      setError('Unable to reach Lattice backend.');
    } finally {
      setLoading(false);
    }
  }, [onAuthorizationLost]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const profileName = getDisplayName(user);
  const profileLabel = getInitials(user);
  const routeMeta = ownerRouteMeta[activeRoute];
  const data = dashboard;

  useEffect(() => {
    const animationFrame = window.requestAnimationFrame(() => scrollConsoleToTop());
    return () => window.cancelAnimationFrame(animationFrame);
  }, [activeRoute, data?.generated_at]);

  if (!data) {
    return (
      <OwnerPageShell
        user={user}
        profileLabel={profileLabel}
        profileName={profileName}
        activeHref={routeMeta.href}
        onLogout={onLogout}
      >
        <PageHeader
          title={routeMeta.title}
          description={routeMeta.description}
          actions={
            <Button variant="secondary" icon={<RefreshCw size={16} />} onClick={refresh}>
              Retry
            </Button>
          }
        />
        {loading ? <LoadingState title="Loading owner console" /> : null}
        {error ? <ErrorState title={error} /> : null}
      </OwnerPageShell>
    );
  }

  const tenantDbIssues = Math.max(data.summary.total_tenants - data.summary.ready_databases, 0);
  const backupIssues = data.summary.backup_warnings;
  const migrationIssues = data.summary.migration_warnings;
  const selectedTenant = data.tenant_health.find((tenant) => tenant.id === selectedTenantId) ?? data.tenant_health[0] ?? null;
  const changeTenantStatus = async (tenant: TenantRecord, action: 'activate' | 'suspend') => {
    setLoading(true);
    setError('');
    try {
      await apiFetch(`/api/v1/control/owner/tenants/${tenant.id}/${action}/`, { method: 'POST' });
      await refresh();
    } catch (caught) {
      if (caught instanceof LatticeApiError) {
        setError(`${caught.code}: ${caught.message}`);
        return;
      }
      setError('Unable to update tenant status.');
    } finally {
      setLoading(false);
    }
  };
  const tenantRows = buildTenantRows(data, {
    onActivate: (tenant) => changeTenantStatus(tenant, 'activate'),
    onSelect: (tenant) => setSelectedTenantId(tenant.id),
    onSuspend: (tenant) => changeTenantStatus(tenant, 'suspend'),
  });
  const refreshAfterMutation = async () => {
    await refresh();
    scrollConsoleToTop();
  };

  return (
    <OwnerPageShell
      user={user}
      profileLabel={profileLabel}
      profileName={profileName}
      activeHref={routeMeta.href}
      onLogout={onLogout}
    >
      <PageHeader
        title={routeMeta.title}
        description={routeMeta.description}
        actions={
          <>
            <Button variant="secondary" icon={<RefreshCw size={16} />} onClick={refresh}>
              Refresh
            </Button>
            {activeRoute === 'tenants' ? <CreateTenantDialog onCreated={refreshAfterMutation} /> : null}
          </>
        }
      />

      {loading ? <LoadingState title={`Loading ${routeMeta.title.toLowerCase()}`} /> : null}
      {error ? <ErrorState title={error} /> : null}

      {activeRoute === 'dashboard' ? (
        <OwnerDashboardPage data={data} health={health} tenantDbIssues={tenantDbIssues} backupIssues={backupIssues} migrationIssues={migrationIssues} tenantRows={tenantRows} />
      ) : (
        <OwnerSectionPage route={activeRoute} data={data} health={health} onTenantMutated={refreshAfterMutation} selectedTenant={selectedTenant} tenantRows={tenantRows} user={user} />
      )}
    </OwnerPageShell>
  );
}

function OwnerPageShell({
  activeHref,
  children,
  onLogout,
  profileLabel,
  profileName,
  user,
}: {
  activeHref: string;
  children: ReactNode;
  onLogout: () => void;
  profileLabel: string;
  profileName: string;
  user: CurrentUser;
}) {
  return (
    <AppShell
      title="Owner Console"
      mode="owner"
      profileLabel={profileLabel}
      profileName={profileName}
      profileDescription={user.is_platform_admin ? 'Platform Admin' : 'Owner Console'}
      activeHref={activeHref}
      onLogout={onLogout}
    >
      {children}
    </AppShell>
  );
}

function OwnerDashboardPage({
  data,
  health,
  tenantDbIssues,
  backupIssues,
  migrationIssues,
  tenantRows,
}: {
  data: OwnerDashboard;
  health: string;
  tenantDbIssues: number;
  backupIssues: number | null;
  migrationIssues: number;
  tenantRows: Array<Record<string, ReactNode>>;
}) {
  return (
    <>
      <section className="owner-kpi-grid" aria-label="Platform health KPIs">
        <StatCard variant="glass" icon={<Users size={18} />} label="Total Tenants" value={data.summary.total_tenants} />
        <StatCard variant="glass" tone="success" icon={<CheckCircle2 size={18} />} label="Active Tenants" value={data.summary.active_tenants} />
        <StatCard variant="glass" tone={tenantDbIssues ? 'warning' : 'success'} icon={<Database size={18} />} label="Tenant DB Health" value={`${data.summary.healthy_databases}/${data.summary.total_tenants}`} />
        <StatCard variant="glass" tone={data.summary.security_alerts ? 'danger' : 'success'} icon={<ShieldAlert size={18} />} label="Security Alerts" value={data.summary.security_alerts} />
        <StatCard variant="glass" tone={backupIssues ? 'warning' : 'info'} icon={<HardDrive size={18} />} label="Backup Issues" value={backupIssues ?? 0} />
        <StatCard variant="glass" tone={migrationIssues ? 'warning' : 'success'} icon={<Server size={18} />} label="Migration Issues" value={migrationIssues} />
      </section>

      <div className="owner-dashboard-grid">
        <section className="owner-panel owner-panel--primary">
          <div className="owner-panel__header">
            <div>
              <h2>Tenant Health</h2>
              <p>Current control-plane status by tenant.</p>
            </div>
            <Badge variant={tenantDbIssues ? 'warning' : 'success'}>{tenantDbIssues ? 'Attention' : 'Healthy'}</Badge>
          </div>
          <TenantHealthTable rows={tenantRows} />
        </section>

        <Card title="Platform Health" variant="glass">
          <div className="owner-status-stack">
            <StatusLine label="Backend" status={data.platform_health.backend?.status ?? (health === 'ok' ? 'OK' : 'CHECKING')} />
            <StatusLine label="PostgreSQL" status={data.platform_health.postgresql?.status ?? 'UNKNOWN'} />
            <StatusLine label="Redis" status={data.platform_health.redis?.status ?? 'UNKNOWN'} />
            <StatusLine label="Celery" status={data.platform_health.celery?.status ?? 'UNKNOWN'} />
            <StatusLine label="Tenant databases" status={tenantDbIssues ? 'WARNING' : 'HEALTHY'} />
          </div>
        </Card>

        <Card title="Recent Security Events" variant="glass">
          <div className="owner-attention">
            <ShieldAlert size={20} aria-hidden="true" />
            <div>
              <strong>{data.summary.security_alerts}</strong>
              <span>Denied or failed control-plane events</span>
            </div>
          </div>
          <RecentSecurityEvents events={data.recent_security_events} limit={4} />
        </Card>

        <Card title="Subscription / License Attention" variant="glass">
          <div className="owner-status-stack">
            <StatusLine label="Licenses issued" status={String(data.summary.license_count)} />
            <StatusLine label="Unassigned subscriptions" status={String(data.subscription_license_attention.length)} />
            <StatusLine label="Active users" status={String(data.summary.active_users)} />
            <StatusLine label="Support grants" status={String(data.summary.active_support_grants)} />
          </div>
        </Card>

        <Card title="Provisioning / Migration Activity" variant="glass">
          <div className="owner-status-stack">
            <StatusLine label="Ready databases" status={`${data.summary.ready_databases}/${data.summary.total_tenants}`} />
            <StatusLine label="Migration status" status={data.infrastructure.migration_status} />
            <StatusLine label="Backup status" status={data.infrastructure.backup_status} />
            <StatusLine label="Recent activity" status={String(data.recent_activity.length)} />
          </div>
        </Card>
      </div>
    </>
  );
}

function OwnerSectionPage({
  route,
  data,
  health,
  onTenantMutated,
  selectedTenant,
  tenantRows,
  user,
}: {
  route: OwnerRoute;
  data: OwnerDashboard;
  health: string;
  onTenantMutated: () => Promise<void>;
  selectedTenant: TenantRecord | null;
  tenantRows: Array<Record<string, ReactNode>>;
  user: CurrentUser;
}) {
  if (route === 'profile') {
    return <ProfilePage user={user} mode="owner" />;
  }

  if (route === 'security-settings') {
    return <SecuritySettingsPage user={user} mode="owner" />;
  }

  if (route === 'tenants') {
    return (
      <section className="owner-page-grid owner-page-grid--management">
        <Card title="Tenant Management" variant="glass">
          <TenantHealthTable rows={tenantRows} searchable showActions />
        </Card>
        <Card title="Tenant Detail" variant="glass">
          {selectedTenant ? <TenantDetail tenant={selectedTenant} onUpdated={onTenantMutated} /> : <p className="owner-page-note">Create a tenant to review lifecycle and database status.</p>}
        </Card>
      </section>
    );
  }

  if (route === 'infrastructure/health') {
    const tenantDbIssues = Math.max(data.summary.total_tenants - data.summary.ready_databases, 0);
    return (
      <section className="owner-page-grid">
        <Card title="Service Health" variant="glass">
          <div className="owner-status-stack">
            <StatusLine label="Backend" status={data.platform_health.backend?.status ?? (health === 'ok' ? 'OK' : 'CHECKING')} />
            <StatusLine label="PostgreSQL" status={data.platform_health.postgresql?.status ?? 'UNKNOWN'} />
            <StatusLine label="Redis" status={data.platform_health.redis?.status ?? 'UNKNOWN'} />
            <StatusLine label="Celery" status={data.platform_health.celery?.status ?? 'UNKNOWN'} />
            <StatusLine label="Tenant databases" status={tenantDbIssues ? 'WARNING' : 'HEALTHY'} />
          </div>
        </Card>
        <Card title="Database Estate" variant="glass">
          <div className="owner-status-stack">
            <StatusLine label="Ready databases" status={`${data.summary.ready_databases}/${data.summary.total_tenants}`} />
            <StatusLine label="Healthy databases" status={`${data.summary.healthy_databases}/${data.summary.total_tenants}`} />
            <StatusLine label="Database warnings" status={String(data.summary.database_warnings)} />
            <StatusLine label="Storage usage" status={data.infrastructure.storage_usage} />
          </div>
        </Card>
        <Card title="Migrations & Backup" variant="glass">
          <div className="owner-status-stack">
            <StatusLine label="Migration status" status={data.infrastructure.migration_status} />
            <StatusLine label="Migration warnings" status={String(data.summary.migration_warnings)} />
            <StatusLine label="Backup status" status={data.infrastructure.backup_status} />
            <StatusLine label="Backup warnings" status={String(data.summary.backup_warnings ?? 0)} />
          </div>
        </Card>
      </section>
    );
  }

  if (route === 'security/events') {
    return (
      <section className="owner-page-grid">
        <Card title="Security Events" variant="glass">
          <div className="owner-status-stack">
            <StatusLine label="Alerts" status={String(data.summary.security_alerts)} />
            <StatusLine label="Active support grants" status={String(data.summary.active_support_grants)} />
          </div>
        </Card>
        <Card title="Recent Events" variant="glass">
          <RecentSecurityEvents events={data.recent_security_events} limit={6} />
        </Card>
      </section>
    );
  }

  if (route === 'subscriptions') {
    return (
      <section className="owner-page-grid">
        <Card title="License Summary" variant="glass">
          <div className="owner-status-stack">
            <StatusLine label="Licenses issued" status={String(data.summary.license_count)} />
            <StatusLine label="Subscription attention" status={String(data.subscription_license_attention.length)} />
            <StatusLine label="Active tenants" status={String(data.summary.active_tenants)} />
            <StatusLine label="Suspended tenants" status={String(data.summary.suspended_tenants)} />
          </div>
        </Card>
        <Card title="Attention" variant="glass">
          <DataTable
            columns={[
              { key: 'tenant', header: 'Tenant' },
              { key: 'license', header: 'License' },
              { key: 'status', header: 'Status' },
            ]}
            rows={data.subscription_license_attention.map((item) => ({
              tenant: item.tenant,
              license: item.license_number,
              status: <StatusBadge status={item.subscription_status} variant={variantForStatus(item.subscription_status)} />,
            }))}
            emptyMessage="No subscription attention items."
          />
        </Card>
      </section>
    );
  }

  if (route === 'tenants/new') {
    return (
      <section className="owner-page-grid">
        <Card title="Tenant Provisioning" variant="glass">
          <CreateTenantDialog onCreated={onTenantMutated} />
          <p className="owner-page-note">Tenant creation persists control-plane metadata today. Dedicated database provisioning remains a controlled backend workflow and is never selected from browser-supplied database names.</p>
        </Card>
      </section>
    );
  }

  return <OwnerApiResourcePage route={route} />;
}

const ownerApiResources: Partial<Record<OwnerRoute, { endpoint: string; collection: string; title: string }>> = {
  plans: { endpoint: '/api/v1/control/owner/plans/', collection: 'plans', title: 'Plans' },
  licenses: { endpoint: '/api/v1/control/owner/licenses/', collection: 'licenses', title: 'Licenses' },
  modules: { endpoint: '/api/v1/control/owner/modules/', collection: 'modules', title: 'Modules' },
  features: { endpoint: '/api/v1/control/owner/features/', collection: 'features', title: 'Feature Flags' },
  users: { endpoint: '/api/v1/control/owner/users/', collection: 'users', title: 'Platform Users' },
  roles: { endpoint: '/api/v1/control/owner/roles/', collection: 'roles', title: 'Roles' },
  permissions: { endpoint: '/api/v1/control/owner/permissions/', collection: 'permissions', title: 'Permissions' },
  'support-access': { endpoint: '/api/v1/control/owner/support-access/', collection: 'support_access', title: 'Support Access' },
  'infrastructure/databases': { endpoint: '/api/v1/control/owner/infrastructure/databases/', collection: 'databases', title: 'Tenant Databases' },
  'infrastructure/migrations': { endpoint: '/api/v1/control/owner/infrastructure/migrations/', collection: 'migrations', title: 'Migrations' },
  'infrastructure/backups': { endpoint: '/api/v1/control/owner/infrastructure/backups/', collection: 'backups', title: 'Backups' },
  'infrastructure/restore': { endpoint: '/api/v1/control/owner/infrastructure/restore/', collection: 'restore_requests', title: 'Restore Requests' },
  'security/audit': { endpoint: '/api/v1/control/owner/security/audit/', collection: 'audit_logs', title: 'Audit Logs' },
  'security/sessions': { endpoint: '/api/v1/control/owner/security/sessions/', collection: 'sessions', title: 'Sessions' },
  'security/mfa': { endpoint: '/api/v1/control/owner/security/mfa/', collection: 'mfa_compliance', title: 'MFA Compliance' },
  reports: { endpoint: '/api/v1/control/owner/reports/', collection: 'rows', title: 'Owner Reports' },
  settings: { endpoint: '/api/v1/control/owner/settings/', collection: 'settings', title: 'General Settings' },
  'settings/security': { endpoint: '/api/v1/control/owner/settings/', collection: 'settings', title: 'Security Settings' },
  'settings/authentication': { endpoint: '/api/v1/control/owner/settings/', collection: 'settings', title: 'Authentication Settings' },
  'settings/provisioning': { endpoint: '/api/v1/control/owner/settings/', collection: 'settings', title: 'Provisioning Settings' },
  'settings/notifications': { endpoint: '/api/v1/control/owner/notifications/', collection: 'notifications', title: 'Notifications' },
  'settings/branding': { endpoint: '/api/v1/control/owner/settings/', collection: 'settings', title: 'Branding Settings' },
};

function OwnerApiResourcePage({ route }: { route: OwnerRoute }) {
  const resource = ownerApiResources[route];
  const [payload, setPayload] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    if (!resource) {
      return;
    }
    setLoading(true);
    setError('');
    try {
      setPayload(await apiFetch<Record<string, unknown>>(resource.endpoint));
    } catch (caught) {
      if (caught instanceof LatticeApiError) {
        setError(caught.message);
        return;
      }
      setError('Unable to load owner control-plane data.');
    } finally {
      setLoading(false);
    }
  }, [resource]);

  useEffect(() => {
    load();
  }, [load]);

  if (!resource) {
    return <ErrorState title="Owner page is not configured." />;
  }

  const records = Array.isArray(payload?.[resource.collection]) ? payload[resource.collection] as Array<Record<string, unknown>> : [];
  const rows = records.map(toTableRow);
  const columns = buildColumns(rows);

  return (
    <section className="owner-page-grid">
      <Card title={resource.title} variant="glass">
        {loading ? <LoadingState title={`Loading ${resource.title.toLowerCase()}`} /> : null}
        {error ? <ErrorState title={error} /> : null}
        {!loading && !error ? (
          <DataTable
            searchable
            pagination
            columns={columns.length ? columns : [{ key: 'status', header: 'Status' }]}
            rows={rows.length ? rows : [{ status: 'No records found.' }]}
            emptyMessage="No records found."
          />
        ) : null}
        <div className="owner-form-actions">
          <Button variant="secondary" icon={<RefreshCw size={16} />} onClick={load}>
            Retry
          </Button>
        </div>
      </Card>
    </section>
  );
}

function toTableRow(record: Record<string, unknown>): Record<string, ReactNode> {
  const entries = Object.entries(record).slice(0, 8);
  return Object.fromEntries(entries.map(([key, value]) => [key, renderCellValue(value)]));
}

function buildColumns(rows: Array<Record<string, ReactNode>>) {
  const keys = rows[0] ? Object.keys(rows[0]) : [];
  return keys.map((key) => ({ key, header: titleize(key) }));
}

function renderCellValue(value: unknown): ReactNode {
  if (value === null || value === undefined || value === '') {
    return 'UNASSIGNED';
  }
  if (typeof value === 'boolean') {
    return <StatusBadge status={value ? 'YES' : 'NO'} variant={value ? 'success' : 'warning'} />;
  }
  if (typeof value === 'object') {
    return JSON.stringify(value);
  }
  const text = String(value);
  return text.length > 80 ? `${text.slice(0, 77)}...` : text;
}

function titleize(value: string) {
  return value.replace(/_/g, ' ').replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function ProfilePage({ user, mode }: { user: CurrentUser; mode: 'owner' | 'tenant' }) {
  return (
    <section className="owner-page-grid">
      <Card title="Account Profile" variant="glass">
        <DataTable
          columns={summaryColumns}
          rows={[
            { area: 'Name', value: getDisplayName(user), status: <StatusBadge status="ACTIVE" variant="success" /> },
            { area: 'Email', value: user.email, status: <StatusBadge status="VERIFIED" variant="success" /> },
            { area: 'Portal', value: mode === 'owner' ? 'Owner Console' : 'Tenant Portal', status: <StatusBadge status={mode.toUpperCase()} variant="info" /> },
            { area: 'Platform admin', value: user.is_platform_admin ? 'Yes' : 'No', status: <StatusBadge status={user.is_platform_admin ? 'ENABLED' : 'LIMITED'} variant={user.is_platform_admin ? 'success' : 'warning'} /> },
            { area: 'Staff access', value: user.is_staff ? 'Yes' : 'No', status: <StatusBadge status={user.is_staff ? 'ALLOWED' : 'TENANT'} variant={user.is_staff ? 'success' : 'info'} /> },
          ]}
        />
      </Card>
      <Card title="Access Boundary" variant="glass">
        <p className="owner-page-note">
          This profile page uses authenticated control-plane identity data. It does not expose tenant database credentials or query tenant WMS transaction data.
        </p>
      </Card>
    </section>
  );
}

function SecuritySettingsPage({ user, mode }: { user: CurrentUser; mode: 'owner' | 'tenant' }) {
  return (
    <section className="owner-page-grid">
      <Card title="Security Posture" variant="glass">
        <DataTable
          columns={summaryColumns}
          rows={[
            { area: 'Authenticated session', value: 'Backend cookie session', status: <StatusBadge status="ACTIVE" variant="success" /> },
            { area: 'Browser token storage', value: 'No access token stored', status: <StatusBadge status="PROTECTED" variant="success" /> },
            { area: 'MFA', value: user.is_platform_admin ? 'Required for platform administrators' : 'Available through security enrollment', status: <StatusBadge status={user.is_platform_admin ? 'REQUIRED' : 'AVAILABLE'} variant="warning" /> },
            { area: 'Portal scope', value: mode === 'owner' ? 'Control-plane operations' : 'Tenant-scoped operations', status: <StatusBadge status="SERVER ENFORCED" variant="success" /> },
          ]}
        />
      </Card>
      <Card title="Session Controls" variant="glass">
        <p className="owner-page-note">
          Logout revokes the backend security session and returns this browser to the login screen for the current portal.
        </p>
      </Card>
    </section>
  );
}

const summaryColumns = [
  { key: 'area', header: 'Area' },
  { key: 'value', header: 'Value' },
  { key: 'status', header: 'Status' },
] satisfies { key: 'area' | 'value' | 'status'; header: string }[];

function TenantHealthTable({
  rows,
  searchable = false,
  showActions = false,
}: {
  rows: Array<Record<string, ReactNode>>;
  searchable?: boolean;
  showActions?: boolean;
}) {
  const columns = [
    { key: 'tenant', header: 'Tenant' },
    { key: 'status', header: 'Status' },
    { key: 'dbHealth', header: 'DB Health' },
    { key: 'migration', header: 'Migration' },
    { key: 'backup', header: 'Backup' },
    { key: 'subscription', header: 'Subscription' },
    ...(showActions ? [{ key: 'actions', header: 'Actions' }] : []),
  ];

  return (
    <DataTable
      searchable={searchable}
      columns={columns}
      rows={rows}
    />
  );
}

function CreateTenantDialog({ onCreated }: { onCreated: () => Promise<void> }) {
  const [form, setForm] = useState({
    tenant_code: '',
    display_name: '',
    legal_name: '',
    region: 'us-east-1',
    timezone: 'UTC',
    subscription_plan: '',
  });
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState('');

  const updateForm = (field: keyof typeof form, value: string) => {
    setForm((current) => ({ ...current, [field]: value }));
  };

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setSaving(true);
    setMessage('');
    try {
      await apiFetch('/api/v1/control/owner/tenants/', {
        body: JSON.stringify(form),
        method: 'POST',
      });
      setForm({
        tenant_code: '',
        display_name: '',
        legal_name: '',
        region: 'us-east-1',
        timezone: 'UTC',
        subscription_plan: '',
      });
      setMessage('Tenant created. Database provisioning remains backend-controlled.');
      await onCreated();
    } catch (caught) {
      if (caught instanceof LatticeApiError) {
        setMessage(`${caught.code}: ${caught.message}`);
        return;
      }
      setMessage('Unable to create tenant.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog
      title="Create Tenant"
      description="Creates control-plane tenant metadata. Tenant database provisioning remains a backend-controlled workflow."
      trigger={
        <Button icon={<Plus size={16} />}>
          Create Tenant
        </Button>
      }
    >
      <form className="owner-form-grid" onSubmit={submit}>
        <FormField label="Tenant code">
          <Input required value={form.tenant_code} onChange={(event) => updateForm('tenant_code', event.target.value)} />
        </FormField>
        <FormField label="Display name">
          <Input required value={form.display_name} onChange={(event) => updateForm('display_name', event.target.value)} />
        </FormField>
        <FormField label="Legal name">
          <Input value={form.legal_name} onChange={(event) => updateForm('legal_name', event.target.value)} />
        </FormField>
        <FormField label="Region">
          <Input value={form.region} onChange={(event) => updateForm('region', event.target.value)} />
        </FormField>
        <FormField label="Timezone">
          <Input required value={form.timezone} onChange={(event) => updateForm('timezone', event.target.value)} />
        </FormField>
        <FormField label="Subscription plan">
          <Input value={form.subscription_plan} onChange={(event) => updateForm('subscription_plan', event.target.value)} />
        </FormField>
        {message ? <p className="owner-form-message">{message}</p> : null}
        <div className="owner-form-actions">
          <DialogClose>
            <Button variant="secondary" type="button">
              Close
            </Button>
          </DialogClose>
          <Button disabled={saving} type="submit">
            {saving ? 'Creating' : 'Create Tenant'}
          </Button>
        </div>
      </form>
    </Dialog>
  );
}

function EditTenantDialog({ tenant, onUpdated }: { tenant: TenantRecord; onUpdated: () => Promise<void> }) {
  const [form, setForm] = useState({
    display_name: tenant.display_name,
    legal_name: tenant.legal_name,
    region: tenant.region,
    timezone: tenant.timezone,
    default_language: tenant.default_language,
    subscription_plan: tenant.subscription_plan === 'Unassigned' ? '' : tenant.subscription_plan,
  });
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState('');

  useEffect(() => {
    setForm({
      display_name: tenant.display_name,
      legal_name: tenant.legal_name,
      region: tenant.region,
      timezone: tenant.timezone,
      default_language: tenant.default_language,
      subscription_plan: tenant.subscription_plan === 'Unassigned' ? '' : tenant.subscription_plan,
    });
    setMessage('');
  }, [tenant]);

  const updateForm = (field: keyof typeof form, value: string) => {
    setForm((current) => ({ ...current, [field]: value }));
  };

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setSaving(true);
    setMessage('');
    try {
      await apiFetch(`/api/v1/control/owner/tenants/${tenant.id}/`, {
        body: JSON.stringify(form),
        method: 'PATCH',
      });
      setMessage('Tenant updated.');
      await onUpdated();
    } catch (caught) {
      if (caught instanceof LatticeApiError) {
        setMessage(`${caught.code}: ${caught.message}`);
        return;
      }
      setMessage('Unable to update tenant.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog
      title="Edit Tenant"
      description="Updates control-plane tenant metadata only. Tenant data remains isolated in tenant databases."
      trigger={
        <Button variant="secondary" icon={<Pencil size={16} />}>
          Edit Tenant
        </Button>
      }
    >
      <form className="owner-form-grid" onSubmit={submit}>
        <FormField label="Display name">
          <Input required value={form.display_name} onChange={(event) => updateForm('display_name', event.target.value)} />
        </FormField>
        <FormField label="Legal name">
          <Input value={form.legal_name} onChange={(event) => updateForm('legal_name', event.target.value)} />
        </FormField>
        <FormField label="Region">
          <Input value={form.region} onChange={(event) => updateForm('region', event.target.value)} />
        </FormField>
        <FormField label="Timezone">
          <Input required value={form.timezone} onChange={(event) => updateForm('timezone', event.target.value)} />
        </FormField>
        <FormField label="Default language">
          <Input required value={form.default_language} onChange={(event) => updateForm('default_language', event.target.value)} />
        </FormField>
        <FormField label="Subscription plan">
          <Input value={form.subscription_plan} onChange={(event) => updateForm('subscription_plan', event.target.value)} />
        </FormField>
        {message ? <p className="owner-form-message">{message}</p> : null}
        <div className="owner-form-actions">
          <DialogClose>
            <Button variant="secondary" type="button">
              Close
            </Button>
          </DialogClose>
          <Button disabled={saving} type="submit">
            {saving ? 'Saving' : 'Save Changes'}
          </Button>
        </div>
      </form>
    </Dialog>
  );
}

function TenantDetail({ tenant, onUpdated }: { tenant: TenantRecord; onUpdated: () => Promise<void> }) {
  return (
    <div className="owner-detail-stack">
      <div className="owner-detail-actions">
        <EditTenantDialog tenant={tenant} onUpdated={onUpdated} />
        <ConfigureTenantDatabaseDialog tenant={tenant} onUpdated={onUpdated} />
      </div>
      <StatusLine label="Tenant code" status={tenant.tenant_code} />
      <StatusLine label="License" status={tenant.license_number} />
      <StatusLine label="Lifecycle" status={tenant.status} />
      <StatusLine label="Subscription" status={tenant.subscription_status} />
      <StatusLine label="Plan" status={tenant.subscription_plan} />
      <StatusLine label="Domain" status={tenant.primary_domain || 'UNASSIGNED'} />
      <StatusLine label="Region" status={tenant.region || 'UNASSIGNED'} />
      <StatusLine label="Timezone" status={tenant.timezone} />
      <StatusLine label="Database" status={tenant.database?.provisioning_status ?? 'MISSING'} />
      <StatusLine label="DB alias" status={tenant.database?.alias || 'UNASSIGNED'} />
      <StatusLine label="DB host reference" status={tenant.database?.host_reference || 'UNASSIGNED'} />
      <StatusLine label="DB name" status={tenant.database?.name || 'UNASSIGNED'} />
      <StatusLine label="Runtime role" status={tenant.database?.runtime_role || 'UNASSIGNED'} />
      <StatusLine label="DB health" status={tenant.database?.health_status ?? 'MISSING'} />
      <StatusLine label="Migration" status={tenant.database?.migration_version || 'NOT RECORDED'} />
    </div>
  );
}

function ConfigureTenantDatabaseDialog({ tenant, onUpdated }: { tenant: TenantRecord; onUpdated: () => Promise<void> }) {
  const existingDatabase = Boolean(tenant.database?.alias);
  const [form, setForm] = useState(() => getDatabaseFormDefaults(tenant));
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState('');

  useEffect(() => {
    setForm(getDatabaseFormDefaults(tenant));
    setMessage('');
  }, [tenant]);

  const updateForm = (field: keyof ReturnType<typeof getDatabaseFormDefaults>, value: string) => {
    setForm((current) => ({ ...current, [field]: value }));
  };

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setSaving(true);
    setMessage('');
    const payload: Record<string, string | number> = {
      database_alias: form.database_alias,
      database_host_reference: form.database_host_reference,
      port: Number(form.port || 5432),
      database_name: form.database_name,
      runtime_role_name: form.runtime_role_name,
      sslmode: form.sslmode,
      migration_version: form.migration_version,
      provisioning_status: form.provisioning_status,
      health_status: form.health_status,
    };
    if (form.secret_reference || !existingDatabase) {
      payload.secret_reference = form.secret_reference;
    }
    try {
      await apiFetch(`/api/v1/control/owner/tenants/${tenant.id}/database/`, {
        body: JSON.stringify(payload),
        method: 'PUT',
      });
      setMessage('Tenant database mapping saved. Runtime selection remains server-side.');
      await onUpdated();
    } catch (caught) {
      if (caught instanceof LatticeApiError) {
        setMessage(`${caught.code}: ${caught.message}`);
        return;
      }
      setMessage('Unable to save tenant database mapping.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog
      title="Database Config"
      description="Registers the trusted control-plane database mapping for this tenant. Submit a secret reference, never a raw password."
      trigger={
        <Button variant="secondary" icon={<Database size={16} />}>
          Database Config
        </Button>
      }
    >
      <form className="owner-form-grid" onSubmit={submit}>
        <FormField label="Database alias">
          <Input required value={form.database_alias} onChange={(event) => updateForm('database_alias', event.target.value)} />
        </FormField>
        <FormField label="Host reference">
          <Input required value={form.database_host_reference} onChange={(event) => updateForm('database_host_reference', event.target.value)} />
        </FormField>
        <FormField label="Port">
          <Input required min={1} max={65535} type="number" value={form.port} onChange={(event) => updateForm('port', event.target.value)} />
        </FormField>
        <FormField label="Database name">
          <Input required value={form.database_name} onChange={(event) => updateForm('database_name', event.target.value)} />
        </FormField>
        <FormField label="Runtime role">
          <Input required value={form.runtime_role_name} onChange={(event) => updateForm('runtime_role_name', event.target.value)} />
        </FormField>
        <FormField label={existingDatabase ? 'Secret reference replacement' : 'Secret reference'}>
          <Input
            required={!existingDatabase}
            value={form.secret_reference}
            onChange={(event) => updateForm('secret_reference', event.target.value)}
            placeholder={existingDatabase ? 'Leave blank to keep current reference' : 'env:TENANT_CODE_DB_PASSWORD'}
          />
        </FormField>
        <FormField label="SSL mode">
          <Input required value={form.sslmode} onChange={(event) => updateForm('sslmode', event.target.value)} />
        </FormField>
        <FormField label="Provisioning status">
          <Input required list="tenant-provisioning-statuses" value={form.provisioning_status} onChange={(event) => updateForm('provisioning_status', event.target.value)} />
        </FormField>
        <FormField label="Health status">
          <Input required list="tenant-health-statuses" value={form.health_status} onChange={(event) => updateForm('health_status', event.target.value)} />
        </FormField>
        <FormField label="Migration version">
          <Input value={form.migration_version} onChange={(event) => updateForm('migration_version', event.target.value)} />
        </FormField>
        <datalist id="tenant-provisioning-statuses">
          <option value="PENDING" />
          <option value="PROVISIONING" />
          <option value="READY" />
          <option value="FAILED" />
        </datalist>
        <datalist id="tenant-health-statuses">
          <option value="UNKNOWN" />
          <option value="HEALTHY" />
          <option value="DEGRADED" />
          <option value="UNAVAILABLE" />
        </datalist>
        {message ? <p className="owner-form-message">{message}</p> : null}
        <div className="owner-form-actions">
          <DialogClose>
            <Button variant="secondary" type="button">
              Close
            </Button>
          </DialogClose>
          <Button disabled={saving} type="submit">
            {saving ? 'Saving' : 'Save Database'}
          </Button>
        </div>
      </form>
    </Dialog>
  );
}

function getDatabaseFormDefaults(tenant: TenantRecord) {
  const normalizedCode = tenant.tenant_code.replace(/[^a-zA-Z0-9_]/g, '_').toLowerCase();
  return {
    database_alias: tenant.database?.alias || `tenant_${normalizedCode}`,
    database_host_reference: tenant.database?.host_reference || 'postgres',
    port: String(tenant.database?.port || 5432),
    database_name: tenant.database?.name || `lattice_${normalizedCode}`,
    runtime_role_name: tenant.database?.runtime_role || `lattice_${normalizedCode}_app`,
    secret_reference: '',
    sslmode: tenant.database?.sslmode || 'prefer',
    provisioning_status: tenant.database?.provisioning_status && tenant.database.provisioning_status !== 'MISSING' ? tenant.database.provisioning_status : 'PENDING',
    health_status: tenant.database?.health_status && tenant.database.health_status !== 'MISSING' ? tenant.database.health_status : 'UNKNOWN',
    migration_version: tenant.database?.migration_version || '',
  };
}

function RecentSecurityEvents({ events, limit }: { events: AuditEventRecord[]; limit: number }) {
  return (
    <div className="owner-status-stack">
      {events.length ? (
        events.slice(0, limit).map((event) => <StatusLine label={event.action} status={event.result} key={event.event_id} />)
      ) : (
        <StatusLine label="Recent security events" status="0" />
      )}
    </div>
  );
}

function StatusLine({ label, status }: { label: string; status: string }) {
  return (
    <div className="status-line">
      <span>{label}</span>
      <StatusBadge status={status} variant={variantForStatus(status)} />
    </div>
  );
}

function buildTenantRows(
  data: OwnerDashboard,
  actions?: {
    onActivate: (tenant: TenantRecord) => void;
    onSelect: (tenant: TenantRecord) => void;
    onSuspend: (tenant: TenantRecord) => void;
  },
) {
  return data.tenant_health.map((tenant) => ({
    tenant: (
      <div className="owner-tenant-cell">
        <strong>{tenant.display_name}</strong>
        <span>{tenant.license_number}</span>
      </div>
    ),
    status: <StatusBadge status={tenant.status} variant={variantForStatus(tenant.status)} />,
    dbHealth: <StatusBadge status={tenant.database?.health_status ?? 'MISSING'} variant={variantForStatus(tenant.database?.health_status ?? 'MISSING')} />,
    migration: <StatusBadge status={tenant.database?.migration_version || 'NOT RECORDED'} variant={tenant.database?.migration_version ? 'success' : 'warning'} />,
    backup: <StatusBadge status={data.infrastructure.backup_status} variant={variantForStatus(data.infrastructure.backup_status)} />,
    subscription: tenant.subscription_plan,
    actions: actions ? (
      <div className="owner-row-actions">
        <Button variant="secondary" icon={<Eye size={15} />} onClick={() => actions.onSelect(tenant)}>
          View
        </Button>
        {tenant.status === 'ACTIVE' ? (
          <Button variant="danger" icon={<PauseCircle size={15} />} onClick={() => actions.onSuspend(tenant)}>
            Suspend
          </Button>
        ) : (
          <Button icon={<PlayCircle size={15} />} onClick={() => actions.onActivate(tenant)}>
            Activate
          </Button>
        )}
      </div>
    ) : null,
  }));
}

function getDisplayName(user: CurrentUser) {
  const name = [user.first_name, user.last_name].filter(Boolean).join(' ').trim();
  return name || user.email;
}

function getInitials(user: CurrentUser) {
  const name = [user.first_name, user.last_name].filter(Boolean).join(' ').trim() || user.email;
  const parts = name.split(/[.\s@_-]+/).filter(Boolean);
  return parts.slice(0, 2).map((part) => part[0]?.toUpperCase()).join('') || 'LU';
}

function useOwnerRoute() {
  const [route, setRoute] = useState<OwnerRoute>(() => getOwnerRouteFromLocation());

  useEffect(() => {
    const onRouteChange = () => {
      setRoute(getOwnerRouteFromLocation());
      scrollConsoleToTop();
    };
    window.addEventListener('popstate', onRouteChange);
    window.addEventListener('hashchange', onRouteChange);
    onRouteChange();
    return () => {
      window.removeEventListener('popstate', onRouteChange);
      window.removeEventListener('hashchange', onRouteChange);
    };
  }, []);

  return route;
}

function scrollConsoleToTop() {
  document.querySelector('.lattice-content')?.scrollTo({ top: 0, left: 0 });
  window.scrollTo({ top: 0, left: 0 });
}

function getOwnerRouteFromLocation(): OwnerRoute {
  const hashRoute = window.location.hash.replace('#', '');
  const pathRoute = window.location.pathname.replace(/^\/owner\/?/, '').replace(/\/$/, '');
  const candidate = (pathRoute || hashRoute || 'dashboard') as OwnerRoute;
  const route = candidate in ownerRouteMeta ? candidate : 'dashboard';
  if (window.location.hash && route in ownerRouteMeta) {
    window.history.replaceState(null, '', ownerRouteMeta[route].href);
  }
  if (window.location.pathname === '/' && !window.location.hash) {
    window.history.replaceState(null, '', ownerRouteMeta.dashboard.href);
  }
  return route;
}

function variantForStatus(status: string) {
  if (['0', 'ACTIVE', 'CURRENT', 'HEALTHY', 'OK', 'READY', 'VERIFIED'].includes(status)) {
    return 'success';
  }
  if (['FAILED', 'DENIED', 'MISSING', 'UNAVAILABLE'].includes(status)) {
    return 'danger';
  }
  return 'warning';
}
