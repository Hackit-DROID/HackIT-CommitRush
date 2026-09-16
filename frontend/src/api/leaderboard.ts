import { useQuery } from '@tanstack/react-query';
import { apiRequest } from './client';
import { LeaderboardFilters, LeaderboardResponse } from '../types/api';

export async function fetchLeaderboard(
  filters: LeaderboardFilters = {}
): Promise<LeaderboardResponse> {
  return apiRequest<LeaderboardResponse>('/leaderboard/', {
    page: filters.page,
    page_size: filters.page_size,
    include_me: filters.include_me,
  });
}

export function useLeaderboard(filters: LeaderboardFilters = {}) {
  return useQuery({
    queryKey: ['leaderboard', filters],
    queryFn: () => fetchLeaderboard(filters),
    placeholderData: (previousData) => previousData,
    staleTime: 30_000,
  });
}
