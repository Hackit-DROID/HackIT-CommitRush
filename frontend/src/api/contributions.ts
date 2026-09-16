import { useQuery } from '@tanstack/react-query';
import { apiRequest } from './client';
import {
  Contribution,
  ContributionFilters,
  PaginatedResponse,
} from '../types/api';

export async function fetchMyContributions(
  filters: ContributionFilters = {}
): Promise<PaginatedResponse<Contribution>> {
  return apiRequest<PaginatedResponse<Contribution>>('/contributions/mine/', {
    status: filters.status,
    page: filters.page,
    page_size: filters.page_size,
  });
}

export async function fetchContribution(
  id: number | string
): Promise<Contribution> {
  return apiRequest<Contribution>(`/contributions/${id}/`);
}

export function useMyContributions(filters: ContributionFilters = {}) {
  return useQuery({
    queryKey: ['my-contributions', filters],
    queryFn: () => fetchMyContributions(filters),
    placeholderData: (previousData) => previousData,
    staleTime: 5_000,
    refetchInterval: (query) => {
      // Poll every 10s if any contribution is in a non-terminal state
      const results = query.state.data?.results;
      if (!results || results.length === 0) return false;
      const hasActive = results.some(
        (c) => c.status !== 'MERGED' && c.status !== 'REJECTED'
      );
      return hasActive ? 10_000 : false;
    },
  });
}

export function useContribution(id: number | string | undefined) {
  return useQuery({
    queryKey: ['contribution', id],
    queryFn: () => fetchContribution(id!),
    enabled: Boolean(id),
    staleTime: 5_000,
    refetchInterval: (query) => {
      const data = query.state.data;
      if (!data) return false;
      const isTerminal = data.status === 'MERGED' || data.status === 'REJECTED';
      return isTerminal ? false : 5_000;
    },
  });
}
