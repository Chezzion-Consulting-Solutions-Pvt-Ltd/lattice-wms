import type { ReactNode } from 'react';
import { DataTable, StatusBadge } from '../../../design-system';

export function OwnerResourceTable({
  records,
}: {
  records: Array<Record<string, unknown>>;
}) {
  const rows = records.map(toTableRow);
  const columns = buildColumns(rows);

  return (
    <DataTable
      searchable
      pagination
      columns={columns.length ? columns : [{ key: 'status', header: 'Status' }]}
      rows={rows.length ? rows : [{ status: 'No records found.' }]}
      emptyMessage="No records found."
    />
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
