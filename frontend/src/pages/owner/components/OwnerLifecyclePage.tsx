import { Eye, Pencil, Plus } from 'lucide-react';
import { FormEvent, ReactNode, useCallback, useEffect, useState } from 'react';
import { apiFetch, LatticeApiError } from '../../../api/client';
import { Button, ConfirmationDialog, DataTable, Dialog, DialogClose, FormField, Input, StatusBadge, TextArea } from '../../../design-system';
import type { DataTableColumn } from '../../../design-system';
import { OwnerCrudCard, OwnerDetailTable, OwnerFilterBar, OwnerPagination, OwnerSearchField, OwnerSelectField, type PaginationState } from './OwnerCrud';
import { parseCsv, parseJsonObject } from './ownerCrudUtils';

export type FieldConfig = {
  name: string;
  label: string;
  type?: 'text' | 'number' | 'datetime' | 'json' | 'csv' | 'textarea' | 'checkbox' | 'select';
  createOnly?: boolean;
  options?: Array<{ value: string; label: string }>;
};

export type ResourceAction = {
  label: string;
  action: string;
  variant?: 'secondary' | 'danger';
};

export function OwnerLifecyclePage({
  title,
  endpoint,
  collection,
  idField = 'id',
  searchPlaceholder = 'Search',
  fields,
  columns,
  actions,
  statusField,
  statusVariant = defaultStatusVariant,
  mapRecord = (record) => record,
  afterLoad,
}: {
  title: string;
  endpoint: string;
  collection: string;
  idField?: string;
  searchPlaceholder?: string;
  fields: FieldConfig[];
  columns: Array<{ key: string; header: string; render?: (record: Record<string, unknown>) => ReactNode }>;
  actions?: ResourceAction[];
  statusField?: string;
  statusVariant?: (status: string) => 'success' | 'warning' | 'danger' | 'info';
  mapRecord?: (record: Record<string, unknown>) => Record<string, unknown>;
  afterLoad?: (payload: Record<string, unknown>) => void;
}) {
  const [records, setRecords] = useState<Array<Record<string, unknown>>>([]);
  const [pagination, setPagination] = useState<PaginationState | null>(null);
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const query = new URLSearchParams({ page_size: '25', page: String(page) });
      if (search) query.set('search', search);
      const payload = await apiFetch<Record<string, unknown>>(`${endpoint}?${query.toString()}`);
      setRecords(Array.isArray(payload[collection]) ? (payload[collection] as Array<Record<string, unknown>>).map(mapRecord) : []);
      setPagination((payload.pagination as PaginationState | undefined) ?? null);
      afterLoad?.(payload);
    } catch (caught) {
      setError(caught instanceof LatticeApiError ? caught.message : `Unable to load ${title.toLowerCase()}.`);
    } finally {
      setLoading(false);
    }
  }, [afterLoad, collection, endpoint, mapRecord, page, search, title]);

  useEffect(() => {
    load();
  }, [load]);

  const lifecycle = async (record: Record<string, unknown>, action: string) => {
    await apiFetch(`${endpoint}${record[idField]}/${action}/`, { method: 'POST' });
    await load();
  };

  return (
    <section className="owner-page-grid owner-page-grid--single">
      <OwnerCrudCard title={title} loading={loading} error={error} onRefresh={load} actions={<RecordFormDialog endpoint={endpoint} fields={fields} onSaved={load} />}>
        <OwnerFilterBar>
          <OwnerSearchField value={search} onChange={(value) => { setSearch(value); setPage(1); }} placeholder={searchPlaceholder} />
        </OwnerFilterBar>
        <DataTable<Record<string, ReactNode>>
          columns={[...columns.map((column) => ({ key: column.key, header: column.header })), { key: 'actions', header: 'Actions' }] as DataTableColumn<Record<string, ReactNode>>[]}
          rows={records.map((record): Record<string, ReactNode> => ({
            ...Object.fromEntries(columns.map((column) => [column.key, column.render ? column.render(record) : renderValue(record[column.key], statusField === column.key, statusVariant)])),
            actions: <RecordActions record={record} endpoint={endpoint} fields={fields} idField={idField} actions={actions ?? []} onAction={lifecycle} onSaved={load} />,
          }))}
          emptyMessage={`No ${title.toLowerCase()} found.`}
        />
        <OwnerPagination pagination={pagination} onPage={setPage} />
      </OwnerCrudCard>
    </section>
  );
}

function RecordActions({ record, endpoint, fields, idField, actions, onAction, onSaved }: { record: Record<string, unknown>; endpoint: string; fields: FieldConfig[]; idField: string; actions: ResourceAction[]; onAction: (record: Record<string, unknown>, action: string) => Promise<void>; onSaved: () => Promise<void> }) {
  return (
    <div className="owner-row-actions">
      <RecordDetailDialog record={record} />
      <RecordFormDialog endpoint={endpoint} record={record} fields={fields} idField={idField} onSaved={onSaved} />
      {actions.map((item) => item.variant === 'danger' ? (
        <ConfirmationDialog
          key={item.action}
          title={`${item.label} record`}
          description="This lifecycle action is persisted and audited."
          confirmLabel={item.label}
          trigger={<Button variant="danger">{item.label}</Button>}
          onConfirm={() => onAction(record, item.action)}
        />
      ) : (
        <Button variant={item.variant ?? 'secondary'} key={item.action} onClick={() => onAction(record, item.action)}>
          {item.label}
        </Button>
      ))}
    </div>
  );
}

function RecordDetailDialog({ record }: { record: Record<string, unknown> }) {
  return (
    <Dialog title="Detail" trigger={<Button variant="secondary" icon={<Eye size={16} />}>View</Button>}>
      <OwnerDetailTable rows={Object.entries(record).slice(0, 12).map(([area, value]) => ({ area, value: renderValue(value, false, defaultStatusVariant) }))} />
    </Dialog>
  );
}

function RecordFormDialog({ endpoint, record, fields, idField = 'id', onSaved }: { endpoint: string; record?: Record<string, unknown>; fields: FieldConfig[]; idField?: string; onSaved: () => Promise<void> }) {
  const [form, setForm] = useState(() => buildForm(fields, record));
  const [message, setMessage] = useState('');
  const update = (field: string, value: string | boolean) => setForm((current) => ({ ...current, [field]: value }));

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setMessage('');
    try {
      const payload = Object.fromEntries(fields.filter((field) => !record || !field.createOnly).map((field) => [field.name, fieldValue(field, form[field.name] ?? '')]));
      await apiFetch(record ? `${endpoint}${record[idField]}/` : endpoint, { method: record ? 'PATCH' : 'POST', body: JSON.stringify(payload) });
      setMessage('Saved.');
      await onSaved();
    } catch (caught) {
      setMessage(caught instanceof LatticeApiError ? caught.message : 'Unable to save record.');
    }
  };

  return (
    <Dialog title={record ? 'Edit' : 'Create'} trigger={<Button icon={record ? <Pencil size={16} /> : <Plus size={16} />}>{record ? 'Edit' : 'Create'}</Button>}>
      <form className="owner-form-grid" onSubmit={submit}>
        {fields.map((field) => <FieldInput key={field.name} field={field} value={form[field.name] ?? ''} disabled={Boolean(record && field.createOnly)} onChange={(value) => update(field.name, value)} />)}
        {message ? <p className="owner-form-message">{message}</p> : null}
        <div className="owner-form-actions">
          <DialogClose><Button variant="secondary">Close</Button></DialogClose>
          <Button type="submit">Save</Button>
        </div>
      </form>
    </Dialog>
  );
}

function FieldInput({ field, value, disabled, onChange }: { field: FieldConfig; value: string | boolean; disabled: boolean; onChange: (value: string | boolean) => void }) {
  if (field.type === 'select') {
    return <OwnerSelectField label={field.label} value={String(value)} onChange={onChange} options={field.options ?? []} />;
  }
  if (field.type === 'textarea' || field.type === 'json' || field.type === 'csv') {
    return <FormField label={field.label}><TextArea value={String(value)} disabled={disabled} onChange={(event) => onChange(event.target.value)} /></FormField>;
  }
  if (field.type === 'checkbox') {
    return <FormField label={field.label}><input type="checkbox" checked={Boolean(value)} disabled={disabled} onChange={(event) => onChange(event.target.checked)} /></FormField>;
  }
  return <FormField label={field.label}><Input type={field.type === 'datetime' ? 'datetime-local' : field.type ?? 'text'} value={String(value)} disabled={disabled} onChange={(event) => onChange(event.target.value)} /></FormField>;
}

function buildForm(fields: FieldConfig[], record?: Record<string, unknown>) {
  return Object.fromEntries(fields.map((field) => [field.name, initialValue(field, record?.[field.name])]));
}

function initialValue(field: FieldConfig, value: unknown) {
  if (field.type === 'checkbox') return Boolean(value);
  if (field.type === 'json') return JSON.stringify(value ?? {});
  if (field.type === 'datetime') return typeof value === 'string' ? value.slice(0, 16) : '';
  return String(value ?? '');
}

function fieldValue(field: FieldConfig, value: string | boolean) {
  if (field.type === 'number') return String(value).trim() ? Number(value) : null;
  if (field.type === 'checkbox') return Boolean(value);
  if (field.type === 'json') return parseJsonObject(String(value));
  if (field.type === 'csv') return parseCsv(String(value));
  return String(value);
}

function renderValue(value: unknown, isStatus: boolean, statusVariant: (status: string) => 'success' | 'warning' | 'danger' | 'info') {
  if (isStatus) return <StatusBadge status={String(value)} variant={statusVariant(String(value))} />;
  if (typeof value === 'boolean') return value ? 'Yes' : 'No';
  if (Array.isArray(value)) return value.join(', ');
  if (value && typeof value === 'object') return JSON.stringify(value);
  return String(value ?? 'UNASSIGNED');
}

function defaultStatusVariant(status: string) {
  if (['ACTIVE', 'READY', 'HEALTHY', 'YES', 'APPROVED'].includes(status)) return 'success';
  if (['PENDING', 'REQUESTED', 'TRIAL', 'EXPIRING', 'SUSPENDED'].includes(status)) return 'warning';
  if (['FAILED', 'REVOKED', 'DENIED', 'EXPIRED', 'CANCELLED'].includes(status)) return 'danger';
  return 'info';
}
