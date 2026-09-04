export type OwnerRoute =
  | 'dashboard'
  | 'tenants'
  | 'tenants/new'
  | 'tenant-detail'
  | 'tenant-edit'
  | 'plans'
  | 'subscriptions'
  | 'licenses'
  | 'modules'
  | 'features'
  | 'users'
  | 'roles'
  | 'permissions'
  | 'support-access'
  | 'infrastructure/databases'
  | 'infrastructure/migrations'
  | 'infrastructure/backups'
  | 'infrastructure/restore'
  | 'infrastructure/health'
  | 'security/events'
  | 'security/audit'
  | 'security/sessions'
  | 'security/mfa'
  | 'reports'
  | 'settings'
  | 'settings/security'
  | 'settings/authentication'
  | 'settings/provisioning'
  | 'settings/notifications'
  | 'settings/branding'
  | 'profile'
  | 'security-settings';

export const ownerRouteMeta: Record<OwnerRoute, { title: string; description: string; href: string }> = {
  dashboard: { title: 'Platform Dashboard', description: 'SaaS platform health, tenant attention, and control-plane signals.', href: '/owner/dashboard' },
  tenants: { title: 'Tenants', description: 'Tenant lifecycle, license, provisioning, database, and subscription status.', href: '/owner/tenants' },
  'tenants/new': { title: 'Create Tenant', description: 'Provision new tenant control-plane records and database mappings.', href: '/owner/tenants/new' },
  'tenant-detail': { title: 'Tenant Detail', description: 'Tenant overview, lifecycle, subscription, domain, and database metadata.', href: '/owner/tenants' },
  'tenant-edit': { title: 'Edit Tenant', description: 'Update control-plane tenant metadata.', href: '/owner/tenants' },
  plans: { title: 'Plans', description: 'Commercial plan definitions, limits, modules, and support tiers.', href: '/owner/plans' },
  subscriptions: { title: 'Subscriptions', description: 'Tenant subscription state, renewal posture, and plan assignments.', href: '/owner/subscriptions' },
  licenses: { title: 'Licenses', description: 'Tenant license status, renewals, expiry, and revocation controls.', href: '/owner/licenses' },
  modules: { title: 'Modules', description: 'Global WMS module definitions and activation state.', href: '/owner/modules' },
  features: { title: 'Feature Flags', description: 'Global feature flags and tenant override state.', href: '/owner/features' },
  users: { title: 'Platform Users', description: 'Platform users, MFA posture, and session counts.', href: '/owner/users' },
  roles: { title: 'Roles', description: 'Platform roles and assigned permission codes.', href: '/owner/roles' },
  permissions: { title: 'Permissions', description: 'Grouped platform permission registry.', href: '/owner/permissions' },
  'support-access': { title: 'Support Access', description: 'Time-bounded owner-approved tenant support access grants.', href: '/owner/support-access' },
  'infrastructure/databases': { title: 'Tenant Databases', description: 'Safe tenant database metadata, health, migration, and provisioning state.', href: '/owner/infrastructure/databases' },
  'infrastructure/migrations': { title: 'Migrations', description: 'Tenant migration status and attention items.', href: '/owner/infrastructure/migrations' },
  'infrastructure/backups': { title: 'Backups', description: 'Backup policies and provider status without fake backup success.', href: '/owner/infrastructure/backups' },
  'infrastructure/restore': { title: 'Restore Requests', description: 'Controlled restore requests and provider-dependent execution state.', href: '/owner/infrastructure/restore' },
  'infrastructure/health': { title: 'Service Health', description: 'Backend, PostgreSQL, Redis, Celery, and tenant database health checks.', href: '/owner/infrastructure/health' },
  'security/events': { title: 'Security Events', description: 'Denied and failed control-plane events with safe request details.', href: '/owner/security/events' },
  'security/audit': { title: 'Audit Logs', description: 'Append-only owner audit history and mutation records.', href: '/owner/security/audit' },
  'security/sessions': { title: 'Sessions', description: 'Platform security sessions and revocation state.', href: '/owner/security/sessions' },
  'security/mfa': { title: 'MFA Compliance', description: 'Privileged platform user MFA compliance posture.', href: '/owner/security/mfa' },
  reports: { title: 'Reports', description: 'Control-plane operational reports and exported platform summaries.', href: '/owner/reports' },
  settings: { title: 'General Settings', description: 'Platform display name, defaults, domain, and support metadata.', href: '/owner/settings' },
  'settings/security': { title: 'Security Settings', description: 'Persisted platform security policy values.', href: '/owner/settings/security' },
  'settings/authentication': { title: 'Authentication Settings', description: 'Password, MFA, session, and future federation policy metadata.', href: '/owner/settings/authentication' },
  'settings/provisioning': { title: 'Provisioning Settings', description: 'Safe tenant provisioning defaults and migration policy metadata.', href: '/owner/settings/provisioning' },
  'settings/notifications': { title: 'Notification Settings', description: 'Owner notification policy and unread operational alerts.', href: '/owner/settings/notifications' },
  'settings/branding': { title: 'Branding Settings', description: 'Safe Lattice branding metadata without arbitrary CSS or JavaScript.', href: '/owner/settings/branding' },
  profile: { title: 'Profile', description: 'Signed-in platform account, role posture, and console access.', href: '/owner/profile' },
  'security-settings': { title: 'Security Settings', description: 'MFA posture, secure session behavior, and account protections.', href: '/owner/security-settings' },
};

export const dashboardBackedRoutes = new Set<OwnerRoute>(['dashboard', 'tenants', 'tenants/new', 'tenant-detail', 'tenant-edit', 'infrastructure/health', 'security/events']);

export const ownerApiResources: Partial<Record<OwnerRoute, { endpoint: string; collection: string; title: string }>> = {
  plans: { endpoint: '/api/v1/control/owner/plans/', collection: 'plans', title: 'Plans' },
  licenses: { endpoint: '/api/v1/control/owner/licenses/', collection: 'licenses', title: 'Licenses' },
  modules: { endpoint: '/api/v1/control/owner/modules/', collection: 'modules', title: 'Modules' },
  features: { endpoint: '/api/v1/control/owner/features/', collection: 'features', title: 'Feature Flags' },
  users: { endpoint: '/api/v1/control/owner/users/', collection: 'users', title: 'Platform Users' },
  roles: { endpoint: '/api/v1/control/owner/roles/', collection: 'roles', title: 'Roles' },
  permissions: { endpoint: '/api/v1/control/owner/permissions/', collection: 'permissions', title: 'Permissions' },
  'support-access': { endpoint: '/api/v1/control/owner/support-access/', collection: 'support_access', title: 'Support Access' },
  'infrastructure/databases': { endpoint: '/api/v1/control/owner/infrastructure/databases/', collection: 'databases', title: 'Tenant Databases' },
  'infrastructure/migrations': { endpoint: '/api/v1/control/owner/infrastructure/migrations/', collection: 'migrations', title: 'Migrations' },
  'infrastructure/backups': { endpoint: '/api/v1/control/owner/infrastructure/backups/', collection: 'backups', title: 'Backups' },
  'infrastructure/restore': { endpoint: '/api/v1/control/owner/infrastructure/restore/', collection: 'restore_requests', title: 'Restore Requests' },
  'security/audit': { endpoint: '/api/v1/control/owner/security/audit/', collection: 'audit_logs', title: 'Audit Logs' },
  'security/sessions': { endpoint: '/api/v1/control/owner/security/sessions/', collection: 'sessions', title: 'Sessions' },
  'security/mfa': { endpoint: '/api/v1/control/owner/security/mfa/', collection: 'mfa_compliance', title: 'MFA Compliance' },
  reports: { endpoint: '/api/v1/control/owner/reports/', collection: 'rows', title: 'Owner Reports' },
  settings: { endpoint: '/api/v1/control/owner/settings/', collection: 'settings', title: 'General Settings' },
  'settings/security': { endpoint: '/api/v1/control/owner/settings/', collection: 'settings', title: 'Security Settings' },
  'settings/authentication': { endpoint: '/api/v1/control/owner/settings/', collection: 'settings', title: 'Authentication Settings' },
  'settings/provisioning': { endpoint: '/api/v1/control/owner/settings/', collection: 'settings', title: 'Provisioning Settings' },
  'settings/notifications': { endpoint: '/api/v1/control/owner/notifications/', collection: 'notifications', title: 'Notifications' },
  'settings/branding': { endpoint: '/api/v1/control/owner/settings/', collection: 'settings', title: 'Branding Settings' },
};
