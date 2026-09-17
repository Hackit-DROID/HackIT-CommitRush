import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiRequest } from './client';
import { CurrentUser } from '../types/api';

export const authKeys = {
  me: ['auth', 'me'] as const,
};

export async function fetchCurrentUser(): Promise<CurrentUser> {
  return apiRequest<CurrentUser>('/auth/me/');
}

export async function logoutUser(): Promise<{ detail: string }> {
  return apiRequest<{ detail: string }>('/auth/logout/');
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
      queryClient.invalidateQueries({ queryKey: authKeys.me });
      window.location.href = '/';
    },
  });
}
