import { Plus, Save } from 'lucide-react';
import type { FormEvent, ReactNode } from 'react';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { apiFetch, LatticeApiError } from '../../../api/client';
import { Button, Card, DataTable, Dialog, DialogClose, ErrorState, FormField, Input, LoadingState, StatusBadge } from '../../../design-system';
import type { TenantResourceConfig } from '../tenantRoutes';

type Row = Record<string, ReactNode>;

export function TenantResourcePage({ config }: { config: TenantResourceConfig }) {
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
      status: <StatusBadge status={String(row.status ?? (row.is_active === false ? 'INACTIVE' : 'ACTIVE'))} variant={row.is_active === false ? 'warning' : 'success'} />,
      id: <code>{String(row.id ?? '')}</code>,
    })),
    [config.codeKey, config.nameKey, rows],
  );

  return (
    <section className="tenant-page-stack">
      <Card title={config.title} description={config.description} actions={<CreateRecordDialog config={config} onCreated={() => void loadRows()} />} variant="glass">
        {loading ? <LoadingState title="Loading records" /> : null}
        {!loading && error ? <ErrorState title={error} /> : null}
        {!loading && !error ? <DataTable rows={tableRows} columns={columns} searchable pagination emptyMessage="No records created yet." /> : null}
      </Card>
    </section>
  );
}

function CreateRecordDialog({ config, onCreated }: { config: TenantResourceConfig; onCreated: () => void }) {
  const [form, setForm] = useState<Record<string, string>>({ status: 'ACTIVE', timezone: 'UTC', zone_type: 'STORAGE', storage_behavior: 'RACK', capacity_method: 'NONE' });
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setSaving(true);
    setError('');
    try {
      const payload = Object.fromEntries(Object.entries(form).filter(([, value]) => value !== '').map(([key, value]) => [key, numericKeys.has(key) ? Number(value) : value]));
      await apiFetch(config.endpoint, { body: JSON.stringify(payload), method: 'POST' });
      setForm({ status: 'ACTIVE', timezone: 'UTC', zone_type: 'STORAGE', storage_behavior: 'RACK', capacity_method: 'NONE' });
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
        {config.fields.map((field) => (
          <FormField label={field.label} key={field.key}>
            <Input required={field.required} type={field.type ?? 'text'} value={form[field.key] ?? ''} onChange={(event) => setForm((current) => ({ ...current, [field.key]: event.target.value }))} />
          </FormField>
        ))}
        {error ? <div className="login-error">{error}</div> : null}
        <div className="lattice-dialog__actions">
          <DialogClose><Button variant="secondary" type="button">Cancel</Button></DialogClose>
          <Button disabled={saving} icon={<Save size={16} />} type="submit">{saving ? 'Saving' : 'Save'}</Button>
        </div>
      </form>
    </Dialog>
  );
}

const numericKeys = new Set(['sequence', 'priority', 'padding', 'current_value', 'display_order', 'length', 'width', 'height']);
const columns = [{ key: 'code', header: 'Code' }, { key: 'name', header: 'Name' }, { key: 'status', header: 'Status' }, { key: 'id', header: 'ID' }];
