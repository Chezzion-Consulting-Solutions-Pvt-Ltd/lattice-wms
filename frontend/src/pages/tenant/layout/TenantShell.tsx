import { RefreshCw } from 'lucide-react';
import type { ReactNode } from 'react';
import { AppShell, Button, PageHeader } from '../../../design-system';
import type { CurrentUser, TenantContext } from '../../../types';
import { tenantRouteMeta, type TenantRoute } from '../tenantRoutes';

export function TenantShell({ children, context, loading, onLogout, onRefresh, route, user }: { children: ReactNode; context: TenantContext | null; loading: boolean; onLogout: () => void; onRefresh: () => void; route: TenantRoute; user: CurrentUser }) {
  const meta = tenantRouteMeta[route];
  return (
    <AppShell title={context?.tenant.display_name ?? 'Tenant Console'} mode="client" profileLabel={getInitials(user)} profileName={getDisplayName(user)} profileDescription="Tenant user" activeHref={meta.href} onLogout={onLogout}>
      <PageHeader title={meta.title} description={meta.description} actions={<Button variant="secondary" icon={<RefreshCw size={16} />} onClick={onRefresh}>{loading ? 'Refreshing' : 'Refresh'}</Button>} />
      {children}
    </AppShell>
  );
}

function getDisplayName(user: CurrentUser) {
  return [user.first_name, user.last_name].filter(Boolean).join(' ').trim() || user.email;
}

function getInitials(user: CurrentUser) {
  const parts = getDisplayName(user).split(/[.\s@_-]+/).filter(Boolean);
  return parts.slice(0, 2).map((part) => part[0]?.toUpperCase()).join('') || 'LU';
}
