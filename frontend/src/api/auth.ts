import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiRequest } from './client';
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
    return await apiRequest<CurrentUser>('/auth/me/');
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
      queryClient.setQueryData(authKeys.me, UNAUTHENTICATED_USER);
      queryClient.invalidateQueries({ queryKey: authKeys.me });
      window.location.href = '/';
    },
    onError: () => {
      // Even on network error, reset client cache and navigate to root
      queryClient.setQueryData(authKeys.me, UNAUTHENTICATED_USER);
      window.location.href = '/';
    },
  });
}
