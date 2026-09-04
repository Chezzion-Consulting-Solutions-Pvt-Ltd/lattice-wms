import { OwnerLifecyclePage } from './OwnerLifecyclePage';

export function ModulesPage() {
  return (
    <OwnerLifecyclePage
      title="Modules"
      endpoint="/api/v1/control/owner/modules/"
      collection="modules"
      searchPlaceholder="Search modules"
      statusField="active"
      fields={[
        { name: 'module_code', label: 'Module Code', createOnly: true },
        { name: 'name', label: 'Name' },
        { name: 'description', label: 'Description', type: 'textarea' },
        { name: 'active', label: 'Active', type: 'checkbox' },
        { name: 'display_order', label: 'Display Order', type: 'number' },
        { name: 'dependencies', label: 'Dependencies', type: 'csv' },
      ]}
      columns={[
        { key: 'module_code', header: 'Code' },
        { key: 'name', header: 'Name' },
        { key: 'display_order', header: 'Order' },
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
