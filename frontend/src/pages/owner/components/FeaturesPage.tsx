import { OwnerLifecyclePage } from './OwnerLifecyclePage';

export function FeaturesPage() {
  return (
    <OwnerLifecyclePage
      title="Feature Flags"
      endpoint="/api/v1/control/owner/features/"
      collection="features"
      searchPlaceholder="Search feature flags"
      statusField="active"
      fields={[
        { name: 'code', label: 'Code', createOnly: true },
        { name: 'name', label: 'Name' },
        { name: 'description', label: 'Description', type: 'textarea' },
        { name: 'active', label: 'Active', type: 'checkbox' },
        { name: 'enabled_by_default', label: 'Default Enabled', type: 'checkbox' },
        { name: 'environment_metadata', label: 'Environment JSON', type: 'json' },
      ]}
      columns={[
        { key: 'code', header: 'Code' },
        { key: 'name', header: 'Name' },
        { key: 'enabled_by_default', header: 'Default' },
        { key: 'active', header: 'Status' },
      ]}
      actions={[
        { label: 'Activate', action: 'activate' },
        { label: 'Deactivate', action: 'deactivate', variant: 'danger' },
      ]}
      statusVariant={(status) => (status === 'true' || status === 'Yes' ? 'success' : 'warning')}
    />
  );
}
