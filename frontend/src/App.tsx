import { useEffect, useState } from 'react';
import { apiFetch } from './api/client';
import './app.css';
import { LoginCheckingPage, LoginPage } from './pages/auth/LoginPage';
import { OwnerConsole } from './pages/owner/OwnerConsole';
import { TenantPortal } from './pages/tenant/TenantPortal';
import type { CurrentUser } from './types';

export function App() {
  const [requestedPortal] = useState(getRequestedPortal);
  const [authState, setAuthState] = useState<'checking' | 'anonymous' | 'authenticated'>('checking');
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [loginNotice, setLoginNotice] = useState('');

  useEffect(() => {
    apiFetch<CurrentUser>('/api/v1/auth/me/')
      .then((currentUser) => {
        if (requestedPortal === 'tenant' || canOpenOwnerConsole(currentUser)) {
          setLoginNotice('');
          setUser(currentUser);
          setAuthState('authenticated');
          return;
        }
        setLoginNotice('Sign in with an authorized platform owner account to continue.');
        setUser(null);
        setAuthState('anonymous');
      })
      .catch(() => {
        setLoginNotice('');
        setUser(null);
        setAuthState('anonymous');
      });
  }, [requestedPortal]);

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

function getRequestedPortal() {
  return window.location.pathname.startsWith('/tenant') ? 'tenant' : 'owner';
}
