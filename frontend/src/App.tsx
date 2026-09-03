import { useEffect, useState } from 'react';
import { apiFetch, clearAccessToken } from './api/client';
import './app.css';
import { LoginCheckingPage, LoginPage } from './pages/auth/LoginPage';
import { OwnerConsole } from './pages/owner/OwnerConsole';
import { TenantPortal } from './pages/tenant/TenantPortal';
import type { CurrentUser, LoginContext } from './types';

type PortalMode = 'owner' | 'tenant';

export function App() {
  const [requestedPortal, setRequestedPortal] = useState<PortalMode>(getRequestedPortal);
  const [authState, setAuthState] = useState<'checking' | 'anonymous' | 'authenticated'>('checking');
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [loginNotice, setLoginNotice] = useState('');

  useEffect(() => {
    let mounted = true;

    async function checkAuthentication() {
      let portalMode = getRequestedPortal();
      try {
        const context = await apiFetch<LoginContext>('/api/v1/auth/login/context/');
        portalMode = context.mode === 'tenant' ? 'tenant' : 'owner';
      } catch {
        portalMode = getRequestedPortal();
      }

      if (!mounted) {
        return;
      }
      setRequestedPortal(portalMode);

      try {
        const currentUser = await apiFetch<CurrentUser>('/api/v1/auth/me/');
        if (!mounted) {
          return;
        }
        if (portalMode === 'tenant' || canOpenOwnerConsole(currentUser)) {
          setLoginNotice('');
          setUser(currentUser);
          setAuthState('authenticated');
          return;
        }
        setLoginNotice('Sign in with an authorized platform owner account to continue.');
        setUser(null);
        setAuthState('anonymous');
      } catch {
        if (!mounted) {
          return;
        }
        setLoginNotice('');
        setUser(null);
        setAuthState('anonymous');
      }
    }

    checkAuthentication();

    return () => {
      mounted = false;
    };
  }, []);

  const handleAuthenticated = (currentUser: CurrentUser) => {
    if (requestedPortal === 'owner' && !canOpenOwnerConsole(currentUser)) {
      setLoginNotice('This account is not authorized for the Owner Console.');
      setUser(null);
      setAuthState('anonymous');
      return;
    }
    setLoginNotice('');
    setUser(currentUser);
    setAuthState('authenticated');
  };

  const handleLogout = async () => {
    try {
      await apiFetch('/api/v1/auth/logout/', { method: 'POST' });
    } finally {
      clearAccessToken();
      setUser(null);
      setAuthState('anonymous');
    }
  };

  if (authState === 'checking') {
    return <LoginCheckingPage />;
  }

  if (authState === 'anonymous' || !user) {
    return <LoginPage notice={loginNotice} onAuthenticated={handleAuthenticated} />;
  }

  if (requestedPortal === 'tenant') {
    return <TenantPortal user={user} onLogout={handleLogout} />;
  }

  return <OwnerConsole user={user} onAuthorizationLost={handleLogout} onLogout={handleLogout} />;
}

function canOpenOwnerConsole(user: CurrentUser) {
  return user.is_staff || user.is_platform_admin;
}

function getRequestedPortal(): PortalMode {
  const hostname = window.location.hostname.toLowerCase();
  if (window.location.pathname.startsWith('/tenant')) {
    return 'tenant';
  }
  if (window.location.pathname.startsWith('/owner')) {
    return 'owner';
  }
  return hostname === 'localhost' || hostname === '127.0.0.1' ? 'owner' : 'tenant';
}
