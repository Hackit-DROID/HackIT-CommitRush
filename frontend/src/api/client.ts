import { ApiError } from '../types/api';

export const RAW_BASE_URL = import.meta.env.VITE_API_BASE_URL || import.meta.env.VITE_API_URL || '/api/v1';
export const API_BASE_URL = RAW_BASE_URL.replace(/\/+$/, '');


let memoryCsrfToken: string | null = null;

export function setMemoryCsrfToken(token: string | null): void {
  memoryCsrfToken = token;
}

export function getCsrfToken(): string | null {
  if (memoryCsrfToken) return memoryCsrfToken;
  if (typeof document === 'undefined') return null;
  const match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
  return match ? decodeURIComponent(match[1]) : null;
}

export async function apiRequest<T>(
  endpoint: string,
  params?: Record<string, string | number | boolean | undefined | null>,
  options?: RequestInit
): Promise<T> {
  const normalizedEndpoint = endpoint.startsWith('/') ? endpoint : `/${endpoint}`;
  const fullPath = `${API_BASE_URL}${normalizedEndpoint}`;
  const baseOrigin = typeof window !== 'undefined' && window.location?.origin ? window.location.origin : 'http://localhost:5173';
  const url = new URL(fullPath, baseOrigin);

  if (params) {
    Object.entries(params).forEach(([key, val]) => {
      if (val !== undefined && val !== null && val !== '') {
        url.searchParams.append(key, String(val));
      }
    });
  }

  const isMutation = Boolean(options?.method && options.method.toUpperCase() !== 'GET');
  let csrfToken = getCsrfToken();

  // If a mutation is sent without a known CSRF token, proactively fetch it from /auth/csrf/
  if (isMutation && !csrfToken && !endpoint.includes('/auth/csrf')) {
    try {
      const csrfUrl = new URL(`${API_BASE_URL}/auth/csrf/`, baseOrigin);
      const csrfRes = await fetch(csrfUrl.toString(), {
        credentials: 'include',
        headers: { Accept: 'application/json' },
      });
      if (csrfRes.ok) {
        const csrfData = (await csrfRes.json()) as { csrf_token?: string };
        if (csrfData && typeof csrfData.csrf_token === 'string') {
          csrfToken = csrfData.csrf_token;
          setMemoryCsrfToken(csrfToken);
        }
      }
    } catch {
      // Continue if probe fails
    }
  }

  const headers: Record<string, string> = {
    Accept: 'application/json',
    ...((options?.headers as Record<string, string>) || {}),
  };

  if (csrfToken && isMutation) {
    headers['X-CSRFToken'] = csrfToken;
  }

  const response = await fetch(url.toString(), {
    credentials: 'include',
    ...options,
    headers,
  });

  const csrfHeader = response.headers?.get ? response.headers.get('X-CSRFToken') : null;
  if (csrfHeader) {
    setMemoryCsrfToken(csrfHeader);
  }

  if (!response.ok) {
    let errorData: unknown = null;
    let errorMessage = `HTTP Error ${response.status}: ${response.statusText}`;

    try {
      errorData = await response.json();
      if (errorData && typeof errorData === 'object') {
        const detail = (errorData as Record<string, unknown>).detail || (errorData as Record<string, unknown>).error;
        if (typeof detail === 'string') {
          errorMessage = detail;
        } else if (response.status === 429) {
          errorMessage = 'Rate limit exceeded (~100 req/min). Please slow down and try again shortly.';
        }
      }
    } catch {
      // Non-JSON response
    }

    throw new ApiError(response.status, errorMessage, errorData);
  }

  return response.json() as Promise<T>;
}
