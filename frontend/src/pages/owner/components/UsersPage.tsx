import { OwnerLifecyclePage } from './OwnerLifecyclePage';

export function UsersPage() {
  return (
    <OwnerLifecyclePage
      title="Platform Users"
      endpoint="/api/v1/control/owner/users/"
      collection="users"
      searchPlaceholder="Search users"
      statusField="is_active"
      fields={[
        { name: 'email', label: 'Email', createOnly: true },
        { name: 'first_name', label: 'First Name' },
        { name: 'last_name', label: 'Last Name' },
        { name: 'is_staff', label: 'Staff Access', type: 'checkbox' },
        { name: 'is_platform_admin', label: 'Platform Admin', type: 'checkbox' },
        { name: 'platform_roles', label: 'Platform Roles', type: 'csv' },
        { name: 'mfa_required', label: 'MFA Required', type: 'checkbox' },
      ]}
      columns={[
        { key: 'email', header: 'Email' },
        { key: 'platform_roles', header: 'Roles' },
        { key: 'mfa_enabled', header: 'MFA' },
        { key: 'active_sessions', header: 'Sessions' },
        { key: 'is_active', header: 'Status' },
      ]}
      actions={[
        { label: 'Activate', action: 'activate' },
        { label: 'Reset Password', action: 'password-reset' },
        { label: 'Revoke Sessions', action: 'revoke-sessions', variant: 'danger' },
        { label: 'Disable', action: 'disable', variant: 'danger' },
      ]}
      statusVariant={(status) => (status === 'true' || status === 'Yes' ? 'success' : 'danger')}
    />
  );
}
