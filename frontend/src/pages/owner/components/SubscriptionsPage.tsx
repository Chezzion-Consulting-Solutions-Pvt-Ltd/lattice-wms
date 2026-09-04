import { Eye, PauseCircle, Pencil, PlayCircle, Plus, XCircle } from 'lucide-react';
import { FormEvent, useCallback, useEffect, useState } from 'react';
import { apiFetch, LatticeApiError } from '../../../api/client';
import { Button, DataTable, Dialog, DialogClose, FormField, Input, StatusBadge, TextArea } from '../../../design-system';
import { OwnerCrudCard, OwnerDetailTable, OwnerFilterBar, OwnerPagination, OwnerSearchField, OwnerSelectField, type PaginationState } from './OwnerCrud';
import { parseJsonObject } from './ownerCrudUtils';

type PlanOption = { id: number; code: string; name: string; is_active: boolean };
type TenantOption = { id: string; tenant_code: string; display_name: string };

type SubscriptionRecord = {
  id: number;
  tenant_id: string;
  tenant: string;
  tenant_code: string;
  plan_id: number;
  plan: string;
  status: string;
  starts_at: string;
  trial_ends_at: string | null;
  renewal_at: string | null;
  ends_at: string | null;
  notes: string;
  override_metadata: Record<string, unknown>;
};

const blankSubscription = {
  tenant_id: '',
  plan_id: '',
  status: 'ACTIVE',
  starts_at: '',
  trial_ends_at: '',
  renewal_at: '',
  ends_at: '',
  notes: '',
  override_metadata: '{}',
};

export function SubscriptionsPage() {
  const [subscriptions, setSubscriptions] = useState<SubscriptionRecord[]>([]);
  const [plans, setPlans] = useState<PlanOption[]>([]);
  const [tenants, setTenants] = useState<TenantOption[]>([]);
  const [pagination, setPagination] = useState<PaginationState | null>(null);
  const [filters, setFilters] = useState({ search: '', status: '', plan: '', renewal: '', sort: 'tenant', page: 1 });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const query = new URLSearchParams({ page: String(filters.page), sort: filters.sort, page_size: '10' });
      if (filters.search) query.set('search', filters.search);
      if (filters.status) query.set('status', filters.status);
      if (filters.plan) query.set('plan', filters.plan);
      if (filters.renewal) query.set('renewal', filters.renewal);
      const [subscriptionPayload, planPayload, tenantPayload] = await Promise.all([
        apiFetch<{ subscriptions: SubscriptionRecord[]; pagination: PaginationState }>(`/api/v1/control/owner/subscriptions/?${query.toString()}`),
        apiFetch<{ plans: PlanOption[] }>('/api/v1/control/owner/plans/?active=true&page_size=100'),
        apiFetch<{ tenants: TenantOption[] }>('/api/v1/control/owner/tenants/?page_size=100'),
      ]);
      setSubscriptions(subscriptionPayload.subscriptions);
      setPagination(subscriptionPayload.pagination);
      setPlans(planPayload.plans);
      setTenants(tenantPayload.tenants);
    } catch (caught) {
      setError(caught instanceof LatticeApiError ? caught.message : 'Unable to load subscriptions.');
    } finally {
      setLoading(false);
    }
  }, [filters]);

  useEffect(() => {
    load();
  }, [load]);

  const lifecycle = async (subscription: SubscriptionRecord, action: 'activate' | 'suspend' | 'cancel' | 'expire') => {
    await apiFetch(`/api/v1/control/owner/subscriptions/${subscription.id}/${action}/`, { method: 'POST' });
    await load();
  };

  return (
    <section className="owner-page-grid owner-page-grid--single">
      <OwnerCrudCard title="Subscriptions" loading={loading} error={error} onRefresh={load} actions={<SubscriptionFormDialog plans={plans} tenants={tenants} onSaved={load} />}>
        <OwnerFilterBar>
          <OwnerSearchField value={filters.search} onChange={(search) => setFilters((current) => ({ ...current, search, page: 1 }))} placeholder="Search tenants or plans" />
          <OwnerSelectField label="Status" value={filters.status} onChange={(status) => setFilters((current) => ({ ...current, status, page: 1 }))} options={statusOptions('All')} />
          <OwnerSelectField label="Plan" value={filters.plan} onChange={(plan) => setFilters((current) => ({ ...current, plan, page: 1 }))} options={[{ value: '', label: 'All plans' }, ...plans.map((plan) => ({ value: plan.code, label: plan.name }))]} />
          <OwnerSelectField label="Renewal" value={filters.renewal} onChange={(renewal) => setFilters((current) => ({ ...current, renewal, page: 1 }))} options={[{ value: '', label: 'Any' }, { value: 'overdue', label: 'Overdue' }, { value: 'upcoming', label: 'Upcoming' }, { value: 'ending', label: 'Ending soon' }]} />
        </OwnerFilterBar>
        <DataTable
          columns={[
            { key: 'tenant', header: 'Tenant' },
            { key: 'plan', header: 'Plan' },
            { key: 'renewal', header: 'Renewal' },
            { key: 'status', header: 'Status' },
            { key: 'actions', header: 'Actions' },
          ]}
          rows={subscriptions.map((subscription) => ({
            tenant: <span className="owner-tenant-cell">{subscription.tenant}<span>{subscription.tenant_code}</span></span>,
            plan: subscription.plan,
            renewal: subscription.renewal_at ?? subscription.ends_at ?? 'Unscheduled',
            status: <StatusBadge status={subscription.status} variant={statusVariant(subscription.status)} />,
            actions: <SubscriptionActions subscription={subscription} plans={plans} tenants={tenants} onAction={lifecycle} onSaved={load} />,
          }))}
          emptyMessage="No subscriptions found."
        />
        <OwnerPagination pagination={pagination} onPage={(page) => setFilters((current) => ({ ...current, page }))} />
      </OwnerCrudCard>
    </section>
  );
}

function SubscriptionActions({ subscription, plans, tenants, onAction, onSaved }: { subscription: SubscriptionRecord; plans: PlanOption[]; tenants: TenantOption[]; onAction: (subscription: SubscriptionRecord, action: 'activate' | 'suspend' | 'cancel' | 'expire') => Promise<void>; onSaved: () => Promise<void> }) {
  return (
    <div className="owner-row-actions">
      <SubscriptionDetailDialog subscription={subscription} />
      <SubscriptionFormDialog subscription={subscription} plans={plans} tenants={tenants} onSaved={onSaved} />
      <Button variant="secondary" icon={<PlayCircle size={16} />} onClick={() => onAction(subscription, 'activate')}>Activate</Button>
      <Button variant="secondary" icon={<PauseCircle size={16} />} onClick={() => onAction(subscription, 'suspend')}>Suspend</Button>
      <Button variant="danger" icon={<XCircle size={16} />} onClick={() => onAction(subscription, 'cancel')}>Cancel</Button>
    </div>
  );
}

function SubscriptionDetailDialog({ subscription }: { subscription: SubscriptionRecord }) {
  return (
    <Dialog title={subscription.tenant} trigger={<Button variant="secondary" icon={<Eye size={16} />}>View</Button>}>
      <OwnerDetailTable rows={[
        { area: 'Plan', value: subscription.plan },
        { area: 'Status', value: subscription.status },
        { area: 'Starts', value: subscription.starts_at },
        { area: 'Trial Ends', value: subscription.trial_ends_at ?? 'None' },
        { area: 'Renewal', value: subscription.renewal_at ?? 'None' },
        { area: 'Ends', value: subscription.ends_at ?? 'None' },
        { area: 'Overrides', value: JSON.stringify(subscription.override_metadata) },
      ]} />
    </Dialog>
  );
}

function SubscriptionFormDialog({ subscription, plans, tenants, onSaved }: { subscription?: SubscriptionRecord; plans: PlanOption[]; tenants: TenantOption[]; onSaved: () => Promise<void> }) {
  const [form, setForm] = useState(subscription ? subscriptionToForm(subscription) : blankSubscription);
  const [message, setMessage] = useState('');
  const update = (field: keyof typeof form, value: string) => setForm((current) => ({ ...current, [field]: value }));

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setMessage('');
    try {
      await apiFetch(subscription ? `/api/v1/control/owner/subscriptions/${subscription.id}/` : '/api/v1/control/owner/subscriptions/', {
        method: subscription ? 'PATCH' : 'POST',
        body: JSON.stringify(subscriptionPayload(form, !subscription)),
      });
      setMessage('Saved.');
      await onSaved();
    } catch (caught) {
      setMessage(caught instanceof LatticeApiError ? caught.message : 'Unable to save subscription.');
    }
  };

  return (
    <Dialog title={subscription ? 'Edit Subscription' : 'Create Subscription'} trigger={<Button icon={subscription ? <Pencil size={16} /> : <Plus size={16} />}>{subscription ? 'Edit' : 'Create Subscription'}</Button>}>
      <form className="owner-form-grid" onSubmit={submit}>
        <OwnerSelectField label="Tenant" value={form.tenant_id} onChange={(value) => update('tenant_id', value)} options={[{ value: '', label: 'Select tenant' }, ...tenants.map((tenant) => ({ value: tenant.id, label: tenant.display_name }))]} />
        <OwnerSelectField label="Plan" value={form.plan_id} onChange={(value) => update('plan_id', value)} options={[{ value: '', label: 'Select plan' }, ...plans.map((plan) => ({ value: String(plan.id), label: plan.name }))]} />
        <OwnerSelectField label="Status" value={form.status} onChange={(value) => update('status', value)} options={statusOptions()} />
        <FormField label="Starts At"><Input type="datetime-local" value={form.starts_at} onChange={(event) => update('starts_at', event.target.value)} /></FormField>
        <FormField label="Trial Ends"><Input type="datetime-local" value={form.trial_ends_at} onChange={(event) => update('trial_ends_at', event.target.value)} /></FormField>
        <FormField label="Renewal At"><Input type="datetime-local" value={form.renewal_at} onChange={(event) => update('renewal_at', event.target.value)} /></FormField>
        <FormField label="Ends At"><Input type="datetime-local" value={form.ends_at} onChange={(event) => update('ends_at', event.target.value)} /></FormField>
        <FormField label="Notes"><TextArea value={form.notes} onChange={(event) => update('notes', event.target.value)} /></FormField>
        <FormField label="Override JSON"><TextArea value={form.override_metadata} onChange={(event) => update('override_metadata', event.target.value)} /></FormField>
        {message ? <p className="owner-form-message">{message}</p> : null}
        <div className="owner-form-actions">
          <DialogClose><Button variant="secondary">Close</Button></DialogClose>
          <Button type="submit">Save</Button>
        </div>
      </form>
    </Dialog>
  );
}

function subscriptionToForm(subscription: SubscriptionRecord) {
  return {
    tenant_id: subscription.tenant_id,
    plan_id: String(subscription.plan_id),
    status: subscription.status,
    starts_at: toLocalInput(subscription.starts_at),
    trial_ends_at: toLocalInput(subscription.trial_ends_at),
    renewal_at: toLocalInput(subscription.renewal_at),
    ends_at: toLocalInput(subscription.ends_at),
    notes: subscription.notes,
    override_metadata: JSON.stringify(subscription.override_metadata),
  };
}

function subscriptionPayload(form: typeof blankSubscription, includeTenant: boolean) {
  return {
    ...(includeTenant ? { tenant_id: form.tenant_id } : {}),
    plan_id: Number(form.plan_id),
    status: form.status,
    starts_at: form.starts_at || undefined,
    trial_ends_at: form.trial_ends_at || undefined,
    renewal_at: form.renewal_at || undefined,
    ends_at: form.ends_at || undefined,
    notes: form.notes,
    override_metadata: parseJsonObject(form.override_metadata),
  };
}

function statusOptions(firstLabel = 'Select status') {
  return [
    { value: '', label: firstLabel },
    { value: 'TRIAL', label: 'Trial' },
    { value: 'ACTIVE', label: 'Active' },
    { value: 'PAST_DUE', label: 'Past Due' },
    { value: 'SUSPENDED', label: 'Suspended' },
    { value: 'CANCELLED', label: 'Cancelled' },
    { value: 'EXPIRED', label: 'Expired' },
  ];
}

function statusVariant(status: string) {
  if (status === 'ACTIVE' || status === 'TRIAL') return 'success';
  if (status === 'PAST_DUE' || status === 'SUSPENDED') return 'warning';
  return 'danger';
}

function toLocalInput(value: string | null) {
  return value ? value.slice(0, 16) : '';
}
