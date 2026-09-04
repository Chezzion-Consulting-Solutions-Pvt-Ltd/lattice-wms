import { OwnerLifecyclePage } from './OwnerLifecyclePage';

export function RolesPage() {
  return (
    <OwnerLifecyclePage
      title="Roles"
      endpoint="/api/v1/control/owner/roles/"
      collection="roles"
      searchPlaceholder="Search roles"
      statusField="is_active"
      fields={[
        { name: 'code', label: 'Code', createOnly: true },
        { name: 'name', label: 'Name' },
        { name: 'scope', label: 'Scope', type: 'select', options: [{ value: 'PLATFORM', label: 'Platform' }, { value: 'TENANT', label: 'Tenant' }] },
        { name: 'is_active', label: 'Active', type: 'checkbox' },
        { name: 'requires_mfa', label: 'Requires MFA', type: 'checkbox' },
        { name: 'permissions', label: 'Permissions', type: 'csv' },
      ]}
      columns={[
        { key: 'code', header: 'Code' },
        { key: 'name', header: 'Name' },
        { key: 'scope', header: 'Scope' },
        { key: 'assigned_users', header: 'Users' },
        { key: 'is_active', header: 'Status' },
      ]}
      actions={[
        { label: 'Activate', action: 'activate' },
        { label: 'Disable', action: 'disable', variant: 'danger' },
      ]}
      statusVariant={(status) => (status === 'true' || status === 'Yes' ? 'success' : 'danger')}
    />
  );
}
