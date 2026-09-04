import { OwnerLifecyclePage } from './OwnerLifecyclePage';

export function SupportAccessPage() {
  return (
    <OwnerLifecyclePage
      title="Support Access"
      endpoint="/api/v1/control/owner/support-access/"
      collection="support_access"
      searchPlaceholder="Search support grants"
      statusField="status"
      fields={[
        { name: 'user_id', label: 'Support User ID', createOnly: true },
        { name: 'tenant_id', label: 'Tenant ID', createOnly: true },
        { name: 'reason', label: 'Reason', type: 'textarea' },
        { name: 'scope', label: 'Scope' },
        { name: 'hours', label: 'Hours', type: 'number' },
        { name: 'requested', label: 'Create As Request', type: 'checkbox' },
      ]}
      columns={[
        { key: 'support_user', header: 'User' },
        { key: 'tenant', header: 'Tenant' },
        { key: 'scope', header: 'Scope' },
        { key: 'expires_at', header: 'Expires' },
        { key: 'status', header: 'Status' },
      ]}
      actions={[
        { label: 'Approve', action: 'approve' },
        { label: 'Deny', action: 'deny', variant: 'danger' },
        { label: 'Revoke', action: 'revoke', variant: 'danger' },
      ]}
    />
  );
}
