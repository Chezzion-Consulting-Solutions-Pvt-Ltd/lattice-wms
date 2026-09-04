import type { ReactNode } from 'react';
import { AppShell } from '../../../design-system';
import type { CurrentUser } from '../../../types';

export function OwnerShell({
  activeHref,
  children,
  onLogout,
  profileLabel,
  profileName,
  user,
}: {
  activeHref: string;
  children: ReactNode;
  onLogout: () => void;
  profileLabel: string;
  profileName: string;
  user: CurrentUser;
}) {
  return (
    <AppShell
      title="Owner Console"
      mode="owner"
      profileLabel={profileLabel}
      profileName={profileName}
      profileDescription={user.is_platform_admin ? 'Platform Admin' : 'Owner Console'}
      activeHref={activeHref}
      onLogout={onLogout}
    >
      {children}
    </AppShell>
  );
}
