import { OwnerLifecyclePage } from './OwnerLifecyclePage';

export function LicensesPage() {
  return (
    <OwnerLifecyclePage
      title="Licenses"
      endpoint="/api/v1/control/owner/licenses/"
      collection="licenses"
      searchPlaceholder="Search licenses"
      statusField="status"
      fields={[
        { name: 'tenant_id', label: 'Tenant ID', createOnly: true },
        { name: 'plan_id', label: 'Plan ID', type: 'number' },
        { name: 'status', label: 'Status', type: 'select', options: ['ACTIVE', 'EXPIRING', 'EXPIRED', 'REVOKED'].map((value) => ({ value, label: value })) },
        { name: 'expires_at', label: 'Expires At', type: 'datetime' },
        { name: 'metadata', label: 'Metadata JSON', type: 'json' },
      ]}
      columns={[
        { key: 'tenant', header: 'Tenant' },
        { key: 'license_number', header: 'License' },
        { key: 'plan', header: 'Plan' },
        { key: 'expires_at', header: 'Expires' },
        { key: 'status', header: 'Status' },
      ]}
      actions={[
        { label: 'Renew', action: 'renew' },
        { label: 'Reactivate', action: 'reactivate' },
        { label: 'Revoke', action: 'revoke', variant: 'danger' },
      ]}
    />
  );
}
