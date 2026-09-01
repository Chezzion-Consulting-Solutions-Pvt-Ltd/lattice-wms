import { LogIn } from 'lucide-react';
import { FormEvent, ReactNode, useState } from 'react';
import { LatticeApiError } from '../../api/client';
import { Badge, Button, FormField, Input, LoadingState, PasswordInput } from '../../design-system';
import type { CurrentUser } from '../../types';

type ApiErrorPayload = {
  error?: {
    code?: string;
    message?: string;
    request_id?: string;
  };
};

export function LoginPage({ notice, onAuthenticated }: { notice?: string; onAuthenticated: (user: CurrentUser) => void }) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setLoading(true);
    setError('');

    try {
      const currentUser = await loginRequest(email, password);
      onAuthenticated(currentUser);
    } catch (caught) {
      if (caught instanceof LatticeApiError) {
        setError(`${caught.code}: ${caught.message}`);
        return;
      }
      setError('Unable to sign in to Lattice.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <LoginScreenShell>
      <section className="login-panel" aria-labelledby="login-title">
        <div className="login-brand">
          <span>LATTICE</span>
          <Badge variant="success">Secure Core</Badge>
        </div>
        <div className="login-copy">
          <p className="lattice-caption">Platform access</p>
          <h1 id="login-title">Sign in to Lattice</h1>
          <p>Use an authorized platform owner account to continue.</p>
        </div>
        {notice ? <div className="login-notice">{notice}</div> : null}
        <form className="login-form" onSubmit={submit}>
          <FormField label="Email">
            <Input
              autoComplete="email"
              inputMode="email"
              name="email"
              onChange={(event) => setEmail(event.target.value)}
              required
              type="email"
              value={email}
            />
          </FormField>
          <FormField label="Password">
            <PasswordInput
              name="password"
              onChange={(event) => setPassword(event.target.value)}
              required
              value={password}
            />
          </FormField>
          {error ? (
            <div className="login-error" role="alert">
              {error}
            </div>
          ) : null}
          <Button disabled={loading} icon={<LogIn size={16} />} type="submit">
            {loading ? 'Signing in' : 'Sign in'}
          </Button>
        </form>
        <p className="login-meta">Session cookies are handled by the backend. No access tokens are stored in the browser.</p>
      </section>
    </LoginScreenShell>
  );
}

export function LoginScreenShell({ children }: { children: ReactNode }) {
  return (
    <main className="login-shell">
      <div className="login-shell__surface">{children}</div>
    </main>
  );
}

export function LoginCheckingPage() {
  return (
    <LoginScreenShell>
      <LoadingState title="Checking secure session" />
    </LoginScreenShell>
  );
}

async function loginRequest(email: string, password: string) {
  const response = await fetch('/api/v1/auth/login/', {
    body: JSON.stringify({ email, password }),
    credentials: 'include',
    headers: {
      Accept: 'application/json',
      'Content-Type': 'application/json',
    },
    method: 'POST',
  });
  const payload = (await response.json().catch(() => ({}))) as CurrentUser & ApiErrorPayload;
  if (!response.ok || payload.error) {
    const error = payload.error ?? { code: 'API_ERROR', message: 'Request failed.' };
    const apiError = {
      code: error.code ?? 'API_ERROR',
      message: error.message ?? 'Request failed.',
      ...(error.request_id ? { request_id: error.request_id } : {}),
    };
    throw new LatticeApiError(apiError);
  }
  return payload as CurrentUser;
}
