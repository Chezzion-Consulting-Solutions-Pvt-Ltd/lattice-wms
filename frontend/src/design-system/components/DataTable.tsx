import type { ReactNode } from 'react';
import { useMemo, useState } from 'react';
import { SearchInput } from './Forms';
import './components.css';

export type DataTableColumn<Row> = {
  key: keyof Row;
  header: string;
  render?: (row: Row) => ReactNode;
};

export function DataTable<Row extends Record<string, ReactNode>>({
  columns,
  rows,
  emptyMessage = 'No records found.',
  searchable = false,
  pagination = false,
}: {
  columns: DataTableColumn<Row>[];
  rows: Row[];
  emptyMessage?: string;
  searchable?: boolean;
  pagination?: boolean;
}) {
  const [query, setQuery] = useState('');
  const [page, setPage] = useState(1);
  const pageSize = 8;
  const filteredRows = useMemo(() => {
    if (!query.trim()) {
      return rows;
    }
    const normalized = query.trim().toLowerCase();
    return rows.filter((row) =>
      Object.values(row)
        .map((value) => String(value))
        .join(' ')
        .toLowerCase()
        .includes(normalized),
    );
  }, [query, rows]);
  const pageCount = Math.max(1, Math.ceil(filteredRows.length / pageSize));
  const visibleRows = pagination ? filteredRows.slice((page - 1) * pageSize, page * pageSize) : filteredRows;

  return (
    <div className="lattice-table-shell">
      {searchable ? (
        <div className="lattice-table-toolbar">
          <SearchInput
            value={query}
            onChange={(event) => {
              setQuery(event.target.value);
              setPage(1);
            }}
          />
        </div>
      ) : null}
      <div className="lattice-table-wrap">
        <table className="lattice-table">
          <thead>
            <tr>
              {columns.map((column) => (
                <th key={String(column.key)} scope="col">
                  {column.header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {visibleRows.length ? (
              visibleRows.map((row, rowIndex) => (
                <tr key={rowIndex}>
                  {columns.map((column) => (
                    <td data-label={column.header} key={String(column.key)}>
                      {column.render ? column.render(row) : row[column.key]}
                    </td>
                  ))}
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan={columns.length}>{emptyMessage}</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      {pagination ? (
        <div className="lattice-pagination">
          <span>
            Page {page} of {pageCount}
          </span>
          <div>
            <button type="button" onClick={() => setPage(Math.max(1, page - 1))} disabled={page === 1}>
              Previous
            </button>
            <button type="button" onClick={() => setPage(Math.min(pageCount, page + 1))} disabled={page === pageCount}>
              Next
            </button>
          </div>
        </div>
      ) : null}
    </div>
  );
}
