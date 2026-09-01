import { useEffect, useState } from 'react';
import { apiFetch } from './api/client';
import './app.css';
import { LoginCheckingPage, LoginPage } from './pages/auth/LoginPage';
import { OwnerConsole } from './pages/owner/OwnerConsole';
import type { CurrentUser } from './types';

export function App() {
  const [authState, setAuthState] = useState<'checking' | 'anonymous' | 'authenticated'>('checking');
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [loginNotice, setLoginNotice] = useState('');

  useEffect(() => {
    apiFetch<CurrentUser>('/api/v1/auth/me/')
      .then((currentUser) => {
        if (canOpenOwnerConsole(currentUser)) {
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
  }, []);

  const handleAuthenticated = (currentUser: CurrentUser) => {
    if (!canOpenOwnerConsole(currentUser)) {
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

  return <OwnerConsole user={user} onAuthorizationLost={handleLogout} onLogout={handleLogout} />;
}

function canOpenOwnerConsole(user: CurrentUser) {
  return user.is_staff || user.is_platform_admin;
}
