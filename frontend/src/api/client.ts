import { ApiError } from '../types/api';

const RAW_BASE_URL = import.meta.env.VITE_API_BASE_URL || import.meta.env.VITE_API_URL || '/api/v1';
const API_BASE_URL = RAW_BASE_URL.replace(/\/+$/, '');

function getCsrfToken(): string | null {
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

  const csrfToken = getCsrfToken();
  const headers: Record<string, string> = {
    Accept: 'application/json',
    ...((options?.headers as Record<string, string>) || {}),
  };

  if (csrfToken && options?.method && options.method.toUpperCase() !== 'GET') {
    headers['X-CSRFToken'] = csrfToken;
  }

  const response = await fetch(url.toString(), {
    credentials: 'include',
    ...options,
    headers,
  });

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
