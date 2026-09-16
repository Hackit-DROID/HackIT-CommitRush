import { useQuery } from '@tanstack/react-query';
import { apiRequest } from './client';
import { PublicProfile } from '../types/api';

export async function fetchPublicProfile(username: string): Promise<PublicProfile> {
  return apiRequest<PublicProfile>(`/profile/${encodeURIComponent(username)}/`);
}

export function usePublicProfile(username: string | undefined) {
  return useQuery({
    queryKey: ['profile', username?.toLowerCase()],
    queryFn: () => fetchPublicProfile(username!),
    enabled: Boolean(username && username.trim()),
    staleTime: 30_000,
  });
}
