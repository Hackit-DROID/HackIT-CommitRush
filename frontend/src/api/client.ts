import { ApiError } from '../types/api';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api/v1';

export async function apiRequest<T>(
  endpoint: string,
  params?: Record<string, string | number | boolean | undefined | null>
): Promise<T> {
  const url = new URL(
    endpoint.startsWith('/') ? `${API_BASE_URL}${endpoint}` : `${API_BASE_URL}/${endpoint}`,
    window.location.origin
  );

  if (params) {
    Object.entries(params).forEach(([key, val]) => {
      if (val !== undefined && val !== null && val !== '') {
        url.searchParams.append(key, String(val));
      }
    });
  }

  const response = await fetch(url.toString(), {
    headers: {
      Accept: 'application/json',
    },
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
