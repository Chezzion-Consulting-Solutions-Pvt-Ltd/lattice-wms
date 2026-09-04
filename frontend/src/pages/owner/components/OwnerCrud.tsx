import { RefreshCw } from 'lucide-react';
import type { ReactNode } from 'react';
import { Button, Card, DataTable, ErrorState, FormField, Input, LoadingState, SearchInput } from '../../../design-system';

export type PaginationState = {
  page: number;
  page_size: number;
  total: number;
  pages: number;
  has_next: boolean;
  has_previous: boolean;
};

export function OwnerCrudCard({
  title,
  loading,
  error,
  onRefresh,
  actions,
  children,
}: {
  title: string;
  loading: boolean;
  error: string;
  onRefresh: () => void;
  actions?: ReactNode;
  children: ReactNode;
}) {
  return (
    <Card title={title} variant="glass" actions={actions}>
      {loading ? <LoadingState title={`Loading ${title.toLowerCase()}`} /> : null}
      {error ? <ErrorState title={error} /> : null}
      {!loading && !error ? children : null}
      <div className="owner-form-actions">
        <Button variant="secondary" icon={<RefreshCw size={16} />} onClick={onRefresh}>
          Refresh
        </Button>
      </div>
    </Card>
  );
}

export function OwnerFilterBar({ children }: { children: ReactNode }) {
  return <div className="owner-filter-bar">{children}</div>;
}

export function OwnerSearchField({ value, onChange, placeholder = 'Search' }: { value: string; onChange: (value: string) => void; placeholder?: string }) {
  return <SearchInput value={value} placeholder={placeholder} onChange={(event) => onChange(event.target.value)} />;
}

export function OwnerSelectField({
  label,
  value,
  onChange,
  options,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: Array<{ value: string; label: string }>;
}) {
  return (
    <FormField label={label}>
      <select className="lattice-select" value={value} onChange={(event) => onChange(event.target.value)}>
        {options.map((option) => (
          <option value={option.value} key={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </FormField>
  );
}

export function OwnerNumberField({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) {
  return (
    <FormField label={label}>
      <Input type="number" min="0" value={value} onChange={(event) => onChange(event.target.value)} />
    </FormField>
  );
}

export function OwnerPagination({ pagination, onPage }: { pagination: PaginationState | null; onPage: (page: number) => void }) {
  if (!pagination) {
    return null;
  }
  return (
    <div className="lattice-pagination">
      <span>
        Page {pagination.page} of {pagination.pages} - {pagination.total} total
      </span>
      <div>
        <button type="button" onClick={() => onPage(pagination.page - 1)} disabled={!pagination.has_previous}>
          Previous
        </button>
        <button type="button" onClick={() => onPage(pagination.page + 1)} disabled={!pagination.has_next}>
          Next
        </button>
      </div>
    </div>
  );
}

export function OwnerDetailTable({ rows }: { rows: Array<{ area: string; value: ReactNode }> }) {
  return (
    <DataTable
      columns={[
        { key: 'area', header: 'Field' },
        { key: 'value', header: 'Value' },
      ]}
      rows={rows}
    />
  );
}
