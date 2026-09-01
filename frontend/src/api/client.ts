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

export async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(path, {
    ...init,
    credentials: 'include',
    headers: {
      Accept: 'application/json',
      'Content-Type': 'application/json',
      ...init.headers,
    },
  });

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
