export type ApiError = {
  code: string;
  message: string;
  request_id?: string;
  status?: number;
};

export class LatticeApiError extends Error {
  readonly code: string;
  readonly requestId: string | undefined;
  readonly status: number | undefined;

  constructor(error: ApiError) {
    super(error.message);
    this.name = 'LatticeApiError';
    this.code = error.code;
    this.requestId = error.request_id;
    this.status = error.status;
  }
}

let accessToken = '';

export function setAccessToken(token: string) {
  accessToken = token;
}

export function clearAccessToken() {
  accessToken = '';
}

export async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await rawApiFetch(path, init);
  if ((response.status === 401 || response.status === 403) && path !== '/api/v1/auth/token/refresh/') {
    const refreshed = await refreshAccessToken();
    if (refreshed) {
      return handleResponse<T>(await rawApiFetch(path, init));
    }
  }
  return handleResponse<T>(response);
}

async function rawApiFetch(path: string, init: RequestInit = {}) {
  const response = await fetch(path, {
    ...init,
    credentials: 'include',
    headers: {
      Accept: 'application/json',
      'Content-Type': 'application/json',
      ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
      ...init.headers,
    },
  });
  return response;
}

async function handleResponse<T>(response: Response): Promise<T> {
  const payload = (await response.json().catch(() => ({}))) as { detail?: string; error?: ApiError };
  if (!response.ok) {
    const fallbackError = {
      code: response.status === 401 ? 'AUTHENTICATION_REQUIRED' : response.status === 403 ? 'FORBIDDEN' : 'API_ERROR',
      message: payload.detail ?? 'Request failed.',
    };
    throw new LatticeApiError({
      ...(payload.error ?? fallbackError),
      status: response.status,
    });
  }

  if (payload.error) {
    throw new LatticeApiError({
      ...payload.error,
      status: response.status,
    });
  }

  return payload as T;
}

async function refreshAccessToken() {
  try {
    const response = await fetch('/api/v1/auth/token/refresh/', {
      credentials: 'include',
      headers: {
        Accept: 'application/json',
        'Content-Type': 'application/json',
      },
      method: 'POST',
    });
    const payload = (await response.json().catch(() => ({}))) as { access_token?: string };
    if (!response.ok || !payload.access_token) {
      clearAccessToken();
      return false;
    }
    setAccessToken(payload.access_token);
    return true;
  } catch {
    clearAccessToken();
    return false;
  }
}
