import { useQuery } from '@tanstack/react-query';
import { apiRequest } from './client';
import { EventStats } from '../types/api';

export async function fetchEventStats(): Promise<EventStats> {
  return apiRequest<EventStats>('/stats/');
}

export function useStats(options?: { refetchInterval?: number | false }) {
  return useQuery({
    queryKey: ['stats'],
    queryFn: () => fetchEventStats(),
    staleTime: 30_000,
    refetchInterval: options?.refetchInterval ?? 60_000,
  });
}
