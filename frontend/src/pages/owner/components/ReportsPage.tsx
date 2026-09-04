import { Download, RefreshCw } from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';
import { apiFetch, LatticeApiError } from '../../../api/client';
import { Button, Card, ErrorState, LoadingState } from '../../../design-system';
import { OwnerResourceTable } from './OwnerResourceTable';
import { OwnerFilterBar, OwnerSelectField } from './OwnerCrud';

const reportOptions = [
  { value: 'tenant-status', label: 'Tenant Status' },
  { value: 'subscription', label: 'Subscriptions' },
  { value: 'license-expiry', label: 'License Expiry' },
  { value: 'module-adoption', label: 'Module Adoption' },
  { value: 'database-health', label: 'Database Health' },
  { value: 'migration-compliance', label: 'Migration Compliance' },
  { value: 'backup-compliance', label: 'Backup Compliance' },
  { value: 'platform-user-access', label: 'Platform User Access' },
  { value: 'security-event', label: 'Security Events' },
  { value: 'support-access', label: 'Support Access' },
];

export function ReportsPage() {
  const [reportType, setReportType] = useState('tenant-status');
  const [rows, setRows] = useState<Array<Record<string, unknown>>>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const payload = await apiFetch<{ rows: Array<Record<string, unknown>> }>(`/api/v1/control/owner/reports/?type=${encodeURIComponent(reportType)}`);
      setRows(payload.rows);
    } catch (caught) {
      setError(caught instanceof LatticeApiError ? caught.message : 'Unable to load report.');
    } finally {
      setLoading(false);
    }
  }, [reportType]);

  useEffect(() => {
    load();
  }, [load]);

  const exportCsv = () => {
    window.location.assign(`/api/v1/control/owner/reports/?type=${encodeURIComponent(reportType)}&export=csv`);
  };

  return (
    <section className="owner-page-grid owner-page-grid--single">
      <Card title="Reports" variant="glass" actions={<Button icon={<Download size={16} />} onClick={exportCsv}>Export CSV</Button>}>
        <OwnerFilterBar>
          <OwnerSelectField label="Report" value={reportType} onChange={setReportType} options={reportOptions} />
        </OwnerFilterBar>
        {loading ? <LoadingState title="Loading report" /> : null}
        {error ? <ErrorState title={error} /> : null}
        {!loading && !error ? <OwnerResourceTable records={rows} /> : null}
        <div className="owner-form-actions">
          <Button variant="secondary" icon={<RefreshCw size={16} />} onClick={load}>Refresh</Button>
        </div>
      </Card>
    </section>
  );
}
