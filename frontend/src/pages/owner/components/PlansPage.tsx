import { Eye, PauseCircle, Pencil, PlayCircle, Plus } from 'lucide-react';
import { FormEvent, useCallback, useEffect, useState } from 'react';
import { apiFetch, LatticeApiError } from '../../../api/client';
import { Button, DataTable, Dialog, DialogClose, FormField, Input, StatusBadge, TextArea } from '../../../design-system';
import { OwnerCrudCard, OwnerDetailTable, OwnerFilterBar, OwnerNumberField, OwnerPagination, OwnerSearchField, OwnerSelectField, type PaginationState } from './OwnerCrud';
import { parseCsv, parseJsonObject } from './ownerCrudUtils';

type PlanRecord = {
  id: number;
  code: string;
  name: string;
  description: string;
  is_active: boolean;
  billing_interval: string;
  currency: string;
  price_metadata: Record<string, unknown>;
  user_limit: number | null;
  warehouse_limit: number | null;
  storage_limit: number | null;
  api_limit: number | null;
  support_tier: string;
  included_modules: string[];
  feature_entitlements: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

const blankPlan = {
  code: '',
  name: '',
  description: '',
  billing_interval: 'MONTHLY',
  currency: '',
  price_metadata: '{}',
  user_limit: '',
  warehouse_limit: '',
  storage_limit: '',
  api_limit: '',
  support_tier: '',
  included_modules: 'masters, inventory',
  feature_entitlements: '{}',
};

export function PlansPage() {
  const [plans, setPlans] = useState<PlanRecord[]>([]);
  const [pagination, setPagination] = useState<PaginationState | null>(null);
  const [filters, setFilters] = useState({ search: '', active: '', sort: 'code', page: 1 });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const query = new URLSearchParams({ page: String(filters.page), sort: filters.sort, page_size: '10' });
      if (filters.search) query.set('search', filters.search);
      if (filters.active) query.set('active', filters.active);
      const payload = await apiFetch<{ plans: PlanRecord[]; pagination: PaginationState }>(`/api/v1/control/owner/plans/?${query.toString()}`);
      setPlans(payload.plans);
      setPagination(payload.pagination);
    } catch (caught) {
      setError(caught instanceof LatticeApiError ? caught.message : 'Unable to load plans.');
    } finally {
      setLoading(false);
    }
  }, [filters]);

  useEffect(() => {
    load();
  }, [load]);

  const action = async (plan: PlanRecord, lifecycle: 'activate' | 'deactivate') => {
    await apiFetch(`/api/v1/control/owner/plans/${plan.id}/${lifecycle}/`, { method: 'POST' });
    await load();
  };

  return (
    <section className="owner-page-grid owner-page-grid--single">
      <OwnerCrudCard title="Plans" loading={loading} error={error} onRefresh={load} actions={<PlanFormDialog onSaved={load} />}>
        <OwnerFilterBar>
          <OwnerSearchField value={filters.search} onChange={(search) => setFilters((current) => ({ ...current, search, page: 1 }))} placeholder="Search plans" />
          <OwnerSelectField label="Status" value={filters.active} onChange={(active) => setFilters((current) => ({ ...current, active, page: 1 }))} options={[{ value: '', label: 'All' }, { value: 'true', label: 'Active' }, { value: 'false', label: 'Inactive' }]} />
          <OwnerSelectField label="Sort" value={filters.sort} onChange={(sort) => setFilters((current) => ({ ...current, sort, page: 1 }))} options={[{ value: 'code', label: 'Code' }, { value: 'name', label: 'Name' }, { value: 'active', label: 'Status' }, { value: 'updated', label: 'Updated' }]} />
        </OwnerFilterBar>
        <DataTable
          columns={[
            { key: 'plan', header: 'Plan' },
            { key: 'billing', header: 'Billing' },
            { key: 'limits', header: 'Limits' },
            { key: 'status', header: 'Status' },
            { key: 'actions', header: 'Actions' },
          ]}
          rows={plans.map((plan) => ({
            plan: <span className="owner-tenant-cell">{plan.name}<span>{plan.code}</span></span>,
            billing: `${plan.billing_interval}${plan.currency ? ` / ${plan.currency}` : ''}`,
            limits: `${plan.user_limit ?? 'No'} users, ${plan.warehouse_limit ?? 'No'} warehouses`,
            status: <StatusBadge status={plan.is_active ? 'ACTIVE' : 'INACTIVE'} variant={plan.is_active ? 'success' : 'warning'} />,
            actions: <PlanActions plan={plan} onAction={action} onSaved={load} />,
          }))}
          emptyMessage="No plans found."
        />
        <OwnerPagination pagination={pagination} onPage={(page) => setFilters((current) => ({ ...current, page }))} />
      </OwnerCrudCard>
    </section>
  );
}

function PlanActions({ plan, onAction, onSaved }: { plan: PlanRecord; onAction: (plan: PlanRecord, action: 'activate' | 'deactivate') => Promise<void>; onSaved: () => Promise<void> }) {
  return (
    <div className="owner-row-actions">
      <PlanDetailDialog plan={plan} />
      <PlanFormDialog plan={plan} onSaved={onSaved} />
      <Button variant="secondary" icon={plan.is_active ? <PauseCircle size={16} /> : <PlayCircle size={16} />} onClick={() => onAction(plan, plan.is_active ? 'deactivate' : 'activate')}>
        {plan.is_active ? 'Deactivate' : 'Activate'}
      </Button>
    </div>
  );
}

function PlanDetailDialog({ plan }: { plan: PlanRecord }) {
  return (
    <Dialog title={plan.name} trigger={<Button variant="secondary" icon={<Eye size={16} />}>View</Button>}>
      <OwnerDetailTable rows={[
        { area: 'Code', value: plan.code },
        { area: 'Status', value: plan.is_active ? 'Active' : 'Inactive' },
        { area: 'Modules', value: plan.included_modules.join(', ') || 'None' },
        { area: 'Features', value: JSON.stringify(plan.feature_entitlements) },
        { area: 'Pricing', value: JSON.stringify(plan.price_metadata) },
      ]} />
    </Dialog>
  );
}

function PlanFormDialog({ plan, onSaved }: { plan?: PlanRecord; onSaved: () => Promise<void> }) {
  const [form, setForm] = useState(plan ? planToForm(plan) : blankPlan);
  const [message, setMessage] = useState('');
  const update = (field: keyof typeof form, value: string) => setForm((current) => ({ ...current, [field]: value }));

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setMessage('');
    try {
      await apiFetch(plan ? `/api/v1/control/owner/plans/${plan.id}/` : '/api/v1/control/owner/plans/', {
        method: plan ? 'PATCH' : 'POST',
        body: JSON.stringify(formToPayload(form, !plan)),
      });
      setMessage('Saved.');
      await onSaved();
    } catch (caught) {
      setMessage(caught instanceof LatticeApiError ? caught.message : 'Unable to save plan.');
    }
  };

  return (
    <Dialog title={plan ? 'Edit Plan' : 'Create Plan'} trigger={<Button icon={plan ? <Pencil size={16} /> : <Plus size={16} />}>{plan ? 'Edit' : 'Create Plan'}</Button>}>
      <form className="owner-form-grid" onSubmit={submit}>
        <FormField label="Code"><Input value={form.code} disabled={Boolean(plan)} onChange={(event) => update('code', event.target.value)} /></FormField>
        <FormField label="Name"><Input value={form.name} onChange={(event) => update('name', event.target.value)} /></FormField>
        <OwnerSelectField label="Billing" value={form.billing_interval} onChange={(value) => update('billing_interval', value)} options={[{ value: 'MONTHLY', label: 'Monthly' }, { value: 'ANNUAL', label: 'Annual' }, { value: 'CUSTOM', label: 'Custom' }]} />
        <FormField label="Currency"><Input maxLength={3} value={form.currency} onChange={(event) => update('currency', event.target.value.toUpperCase())} /></FormField>
        <OwnerNumberField label="Users" value={form.user_limit} onChange={(value) => update('user_limit', value)} />
        <OwnerNumberField label="Warehouses" value={form.warehouse_limit} onChange={(value) => update('warehouse_limit', value)} />
        <OwnerNumberField label="Storage GB" value={form.storage_limit} onChange={(value) => update('storage_limit', value)} />
        <OwnerNumberField label="API Limit" value={form.api_limit} onChange={(value) => update('api_limit', value)} />
        <FormField label="Support Tier"><Input value={form.support_tier} onChange={(event) => update('support_tier', event.target.value)} /></FormField>
        <FormField label="Modules"><Input value={form.included_modules} onChange={(event) => update('included_modules', event.target.value)} /></FormField>
        <FormField label="Description"><TextArea value={form.description} onChange={(event) => update('description', event.target.value)} /></FormField>
        <FormField label="Price JSON"><TextArea value={form.price_metadata} onChange={(event) => update('price_metadata', event.target.value)} /></FormField>
        <FormField label="Feature JSON"><TextArea value={form.feature_entitlements} onChange={(event) => update('feature_entitlements', event.target.value)} /></FormField>
        {message ? <p className="owner-form-message">{message}</p> : null}
        <div className="owner-form-actions">
          <DialogClose><Button variant="secondary">Close</Button></DialogClose>
          <Button type="submit">Save</Button>
        </div>
      </form>
    </Dialog>
  );
}

function planToForm(plan: PlanRecord) {
  return {
    code: plan.code,
    name: plan.name,
    description: plan.description,
    billing_interval: plan.billing_interval,
    currency: plan.currency,
    price_metadata: JSON.stringify(plan.price_metadata),
    user_limit: String(plan.user_limit ?? ''),
    warehouse_limit: String(plan.warehouse_limit ?? ''),
    storage_limit: String(plan.storage_limit ?? ''),
    api_limit: String(plan.api_limit ?? ''),
    support_tier: plan.support_tier,
    included_modules: plan.included_modules.join(', '),
    feature_entitlements: JSON.stringify(plan.feature_entitlements),
  };
}

function formToPayload(form: typeof blankPlan, includeCode: boolean) {
  return {
    ...(includeCode ? { code: form.code.trim().toLowerCase() } : {}),
    name: form.name.trim(),
    description: form.description.trim(),
    billing_interval: form.billing_interval,
    currency: form.currency.trim(),
    price_metadata: parseJsonObject(form.price_metadata),
    user_limit: numberOrNull(form.user_limit),
    warehouse_limit: numberOrNull(form.warehouse_limit),
    storage_limit: numberOrNull(form.storage_limit),
    api_limit: numberOrNull(form.api_limit),
    support_tier: form.support_tier.trim(),
    included_modules: parseCsv(form.included_modules),
    feature_entitlements: parseJsonObject(form.feature_entitlements),
  };
}

function numberOrNull(value: string) {
  return value.trim() ? Number(value) : null;
}
