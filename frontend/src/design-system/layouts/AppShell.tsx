import {
  Bell,
  Boxes,
  ClipboardList,
  Database,
  KeyRound,
  LayoutDashboard,
  Lock,
  Settings,
  Shield,
  Users,
  Warehouse,
} from 'lucide-react';
import type { MouseEvent, ReactNode } from 'react';
import { BrandLogo } from '../components/BrandLogo';
import { IconButton } from '../components/Button';
import { DropdownItem, DropdownMenu, Tooltip } from '../components/Overlays';
import './layouts.css';

const clientNavItems = [
  { label: 'Dashboard', icon: LayoutDashboard, href: '/tenant/dashboard' },
  { label: 'Product Categories', icon: Boxes, href: '/tenant/product-categories' },
  { label: 'Plants', icon: Boxes, href: '/tenant/plants' },
  { label: 'Warehouses', icon: Warehouse, href: '/tenant/warehouses' },
  { label: 'Zones', icon: Database, href: '/tenant/zones' },
  { label: 'Storage Types', icon: Boxes, href: '/tenant/storage-types' },
  { label: 'Sections', icon: ClipboardList, href: '/tenant/storage-sections' },
  { label: 'Bins', icon: Database, href: '/tenant/bins' },
  { label: 'Hierarchy', icon: Boxes, href: '/tenant/hierarchy' },
  { label: 'Users & Access', icon: Shield, href: '/tenant/users-access' },
  { label: 'Settings', icon: Settings, href: '/tenant/settings' },
];

const ownerNavItems = [
  { label: 'Dashboard', icon: LayoutDashboard, href: '/owner/dashboard' },
  { label: 'Tenants', icon: Users, href: '/owner/tenants' },
  { label: 'Subscriptions', icon: KeyRound, href: '/owner/subscriptions' },
  { label: 'Modules', icon: Boxes, href: '/owner/modules' },
  { label: 'Users & Access', icon: Shield, href: '/owner/users-access' },
  { label: 'Infrastructure', icon: Database, href: '/owner/infrastructure' },
  { label: 'Security', icon: Lock, href: '/owner/security' },
  { label: 'Reports', icon: ClipboardList, href: '/owner/reports' },
  { label: 'Settings', icon: Settings, href: '/owner/settings' },
];

function navigateWithinApp(event: MouseEvent<HTMLAnchorElement>, href: string) {
  if (!href.startsWith('/owner/') && !href.startsWith('/tenant/')) {
    return;
  }
  event.preventDefault();
  window.history.pushState(null, '', href);
  window.dispatchEvent(new PopStateEvent('popstate'));
}

function navigateToAppPage(href: string) {
  if (!href.startsWith('/owner/') && !href.startsWith('/tenant/')) {
    return;
  }
  window.history.pushState(null, '', href);
  window.dispatchEvent(new PopStateEvent('popstate'));
}

export function AppShell({
  title,
  children,
  mode = 'client',
  profileLabel = 'LU',
  profileName = 'Platform Owner',
  profileDescription = 'Owner Console',
  activeHref,
  onLogout,
  profileHref,
  securityHref,
}: {
  title: string;
  children: ReactNode;
  mode?: 'client' | 'owner';
  profileLabel?: string;
  profileName?: string;
  profileDescription?: string;
  activeHref?: string;
  onLogout?: () => void;
  profileHref?: string;
  securityHref?: string;
}) {
  const navItems = mode === 'owner' ? ownerNavItems : clientNavItems;
  const resolvedProfileHref = profileHref ?? (mode === 'owner' ? '/owner/profile' : '/tenant/profile');
  const resolvedSecurityHref = securityHref ?? (mode === 'owner' ? '/owner/security-settings' : '/tenant/security-settings');

  return (
    <div className="lattice-shell">
      <aside className="lattice-sidebar" aria-label="Primary navigation">
        <div>
          <div className="lattice-sidebar__mark">
            <BrandLogo />
          </div>
          <nav className="lattice-nav">
            {navItems.map((item, index) => {
              const Icon = item.icon;
              const isActive = activeHref ? item.href === activeHref : index === 0;
              return (
                <a className={isActive ? 'active' : ''} href={item.href} key={item.label} onClick={(event) => navigateWithinApp(event, item.href)}>
                  <Icon size={17} />
                  <span>{item.label}</span>
                </a>
              );
            })}
          </nav>
        </div>
        {mode === 'owner' ? (
          <div className="lattice-sidebar__footer">
            <span className="lattice-sidebar__avatar">{profileLabel}</span>
            <div>
              <strong>{profileName}</strong>
              <span>{profileDescription}</span>
            </div>
          </div>
        ) : null}
      </aside>
      <div className="lattice-main">
        <header className="lattice-topbar">
          <div>
            <p className="lattice-caption">{mode === 'owner' ? 'Platform owner' : 'Welcome, Lattice User'}</p>
            <h1>{title}</h1>
          </div>
          <div className="lattice-topbar__actions">
            <Tooltip label="Notifications">
              <IconButton label="Notifications" icon={<Bell size={17} />} />
            </Tooltip>
            <DropdownMenu
              trigger={
                <button className="lattice-user-menu" type="button" aria-label="Open owner profile menu">
                  {profileLabel}
                </button>
              }
            >
              <DropdownItem onSelect={() => navigateToAppPage(resolvedProfileHref)}>Profile</DropdownItem>
              <DropdownItem onSelect={() => navigateToAppPage(resolvedSecurityHref)}>Security settings</DropdownItem>
              {onLogout ? <DropdownItem onSelect={onLogout}>Log out</DropdownItem> : null}
            </DropdownMenu>
          </div>
        </header>
        <main className="lattice-content">{children}</main>
      </div>
    </div>
  );
}
