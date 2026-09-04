import { Building2, Database, Settings, Shield, Warehouse } from 'lucide-react';
import type { ReactNode } from 'react';
import { Card, DataTable, StatusBadge } from '../../../design-system';
import type { TenantContext } from '../../../types';

type SummaryRow = Record<'area' | 'value' | 'status', ReactNode>;

export function TenantDashboardPage({ context }: { context: TenantContext }) {
  return (
    <section className="tenant-page-stack">
      <div className="tenant-portal-grid">
        <MetricCard icon={<Building2 size={18} />} title="Plants" value={context.counts.plants} />
        <MetricCard icon={<Warehouse size={18} />} title="Warehouses" value={context.counts.warehouses} />
        <MetricCard icon={<Database size={18} />} title="Storage Types" value={context.counts.storage_types} />
        <MetricCard icon={<Database size={18} />} title="Zones" value={context.counts.zones} />
        <MetricCard icon={<Database size={18} />} title="Sections" value={context.counts.sections} />
        <MetricCard icon={<Database size={18} />} title="Bays" value={context.counts.bays} />
        <MetricCard icon={<Shield size={18} />} title="Active Bays" value={context.counts.active_bays} />
        <MetricCard icon={<Shield size={18} />} title="Blocked Bays" value={context.counts.blocked_bays} />
        <MetricCard icon={<Settings size={18} />} title="Machines" value={context.counts.machines} />
        <MetricCard icon={<Settings size={18} />} title="Resources" value={context.counts.people_resources} />
      </div>
      <Card title="Configuration Health" variant="glass"><DataTable rows={healthRows(context)} columns={summaryColumns} /></Card>
    </section>
  );
}

function MetricCard({ icon, title, value }: { icon: ReactNode; title: string; value: number | string }) {
  return <Card title={title} variant="glass"><div className="tenant-portal-card"><span className="tenant-portal-card__icon">{icon}</span><strong>{value}</strong></div></Card>;
}

function healthRows(context: TenantContext): SummaryRow[] {
  return [
    { area: 'Warehouse Structure Summary', value: `${context.counts.warehouses} warehouses / ${context.counts.bays} bays`, status: badge(context.counts.warehouses > 0 ? 'READY' : 'ATTENTION') },
    { area: 'Recently Updated Configuration', value: 'Tracked through tenant audit logs', status: badge('AUDITED') },
    { area: 'Inactive Configuration', value: context.counts.blocked_bays, status: badge(context.counts.blocked_bays > 0 ? 'ATTENTION' : 'OK') },
    { area: 'Capacity Configuration Attention', value: context.counts.configuration_alerts, status: badge(context.counts.configuration_alerts > 0 ? 'REVIEW' : 'OK') },
    { area: 'Sequence/Number Range Attention', value: context.counts.storage_types > 0 ? 'Configured as needed' : 'Not configured', status: badge('FOUNDATION') },
    { area: 'Role/Access Attention', value: context.authorization.warehouses.length, status: badge(context.authorization.warehouses.length > 0 ? 'SCOPED' : 'ATTENTION') },
  ];
}

function badge(status: string) {
  return <StatusBadge status={status} variant={['READY', 'OK', 'AUDITED', 'SCOPED'].includes(status) ? 'success' : 'warning'} />;
}

const summaryColumns = [{ key: 'area', header: 'Area' }, { key: 'value', header: 'Value' }, { key: 'status', header: 'Status' }] satisfies { key: keyof SummaryRow; header: string }[];
