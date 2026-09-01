import { LogIn } from 'lucide-react';
import { FormEvent, ReactNode, useEffect, useState } from 'react';
import { apiFetch, LatticeApiError } from '../../api/client';
import { Badge, BrandLogo, Button, FormField, Input, LoadingState, PasswordInput } from '../../design-system';
import type { CurrentUser, LoginContext } from '../../types';

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
  const [loginContext, setLoginContext] = useState<LoginContext | null>(null);

  useEffect(() => {
    let mounted = true;
    apiFetch<LoginContext>('/api/v1/auth/login/context/')
      .then((context) => {
        if (mounted) {
          setLoginContext(context);
        }
      })
      .catch(() => {
        if (mounted) {
          setLoginContext(null);
        }
      });
    return () => {
      mounted = false;
    };
  }, []);

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
          <BrandLogo />
          <Badge variant="success">Secure Core</Badge>
        </div>
        <div className="login-copy">
          <p className="lattice-caption">{loginContext?.mode === 'tenant' ? 'Tenant access' : 'Platform access'}</p>
          <h1 id="login-title">
            {loginContext?.mode === 'tenant' ? `Sign in to ${loginContext.tenant.display_name}` : 'Sign in to Lattice'}
          </h1>
          <p>
            {loginContext?.mode === 'tenant'
              ? 'Use an authorized tenant account for this workspace.'
              : 'Use an authorized platform owner account to continue.'}
          </p>
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
          <div className="login-options">
            <label className="login-remember">
              <input type="checkbox" name="remember" />
              <span>Remember me</span>
            </label>
            <a className="login-forgot" href="#password-reset">
              Forgot password?
            </a>
          </div>
          <div className="login-actions">
            <Button disabled={loading} icon={<LogIn size={16} />} type="submit">
              {loading ? 'Signing in' : 'Sign in'}
            </Button>
          </div>
        </form>
        <p className="login-meta">Session cookies are handled by the backend. No access tokens are stored in the browser.</p>
      </section>
    </LoginScreenShell>
  );
}

export function LoginScreenShell({ children }: { children: ReactNode }) {
  return (
    <main className="login-shell">
      <section className="login-visual" aria-hidden="true">
        <div className="login-visual__mark">
          <BrandLogo compact />
        </div>
      </section>
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
