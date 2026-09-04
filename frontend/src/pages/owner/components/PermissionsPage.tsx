import { useCallback, useEffect, useMemo, useState } from 'react';
import { apiFetch, LatticeApiError } from '../../../api/client';
import { Card, DataTable, ErrorState, LoadingState, StatusBadge } from '../../../design-system';
import { OwnerFilterBar, OwnerSearchField } from './OwnerCrud';

type PermissionRecord = {
  id: number;
  code: string;
  description: string;
  category: string;
};

export function PermissionsPage() {
  const [permissions, setPermissions] = useState<PermissionRecord[]>([]);
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const payload = await apiFetch<{ permissions: PermissionRecord[] }>('/api/v1/control/owner/permissions/');
      setPermissions(payload.permissions);
    } catch (caught) {
      setError(caught instanceof LatticeApiError ? caught.message : 'Unable to load permissions.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const rows = useMemo(() => {
    const normalized = search.trim().toLowerCase();
    return permissions
      .filter((permission) => !normalized || permission.code.toLowerCase().includes(normalized) || permission.category.toLowerCase().includes(normalized))
      .map((permission) => ({
        category: permission.category,
        code: permission.code,
        description: permission.description || 'Registered platform permission',
        status: <StatusBadge status="REGISTERED" variant="info" />,
      }));
  }, [permissions, search]);

  return (
    <section className="owner-page-grid owner-page-grid--single">
      <Card title="Permissions" variant="glass">
        {loading ? <LoadingState title="Loading permissions" /> : null}
        {error ? <ErrorState title={error} /> : null}
        {!loading && !error ? (
          <>
            <OwnerFilterBar>
              <OwnerSearchField value={search} onChange={setSearch} placeholder="Search permissions" />
            </OwnerFilterBar>
            <DataTable
              searchable
              pagination
              columns={[
                { key: 'category', header: 'Group' },
                { key: 'code', header: 'Permission' },
                { key: 'description', header: 'Description' },
                { key: 'status', header: 'Status' },
              ]}
              rows={rows}
            />
          </>
        ) : null}
      </Card>
    </section>
  );
}
