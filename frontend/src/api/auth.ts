import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiRequest, API_BASE_URL, setMemoryCsrfToken } from './client';
import { CurrentUser, ApiError } from '../types/api';

export const authKeys = {
  me: ['auth', 'me'] as const,
};

export const UNAUTHENTICATED_USER: CurrentUser = {
  id: null,
  user_id: 0,
  github_id: null,
  github_username: '',
  avatar_url: null,
  is_suspended: false,
  total_points: 0,
  is_staff: false,
  is_authenticated: false,
};

export async function fetchCurrentUser(): Promise<CurrentUser> {
  try {
    const user = await apiRequest<CurrentUser>('/auth/me/');
    if (user.csrf_token) {
      setMemoryCsrfToken(user.csrf_token);
    }
    return user;
  } catch (err) {
    if (err instanceof ApiError && err.status === 401) {
      return UNAUTHENTICATED_USER;
    }
    throw err;
  }
}

export async function logoutUser(): Promise<{ detail: string }> {
  return apiRequest<{ detail: string }>('/auth/logout/', undefined, {
    method: 'POST',
  });
}

export function getGitHubLoginUrl(nextPath: string = '/profile'): string {
  const query = `?next=${encodeURIComponent(nextPath)}`;

  // If an absolute API base URL is configured (e.g. https://api.commitrush.org/api/v1),
  // route OAuth login directly to that backend host.
  if (API_BASE_URL.startsWith('http://') || API_BASE_URL.startsWith('https://')) {
    return `${API_BASE_URL}/auth/github/login/${query}`;
  }

  // Local development default when running locally against local backend
  if (
    typeof window !== 'undefined' &&
    (window.location.hostname === '127.0.0.1' || window.location.hostname === 'localhost')
  ) {
    return `http://localhost:8000/auth/github/login/${query}`;
  }

  // Same-origin production or reverse-proxied relative path (/api/v1)
  const base = API_BASE_URL.startsWith('/') ? API_BASE_URL : `/${API_BASE_URL}`;
  return `${base}/auth/github/login/${query}`;
}

export function useCurrentUser() {
  return useQuery<CurrentUser, Error>({
    queryKey: authKeys.me,
    queryFn: fetchCurrentUser,
    staleTime: 60_000,
    retry: false,
  });
}

export function useLogout() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: logoutUser,
    onSuccess: () => {
      setMemoryCsrfToken(null);
      queryClient.setQueryData(authKeys.me, UNAUTHENTICATED_USER);
      queryClient.invalidateQueries({ queryKey: authKeys.me });
      window.location.href = '/';
    },
    onError: () => {
      setMemoryCsrfToken(null);
      // Even on network error, reset client cache and navigate to root
      queryClient.setQueryData(authKeys.me, UNAUTHENTICATED_USER);
      window.location.href = '/';
    },
  });
}
