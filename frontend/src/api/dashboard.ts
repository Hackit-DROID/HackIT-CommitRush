import { useQuery } from '@tanstack/react-query';
import { apiRequest } from './client';
import { DashboardData } from '../types/api';

export async function fetchDashboard(): Promise<DashboardData> {
  return apiRequest<DashboardData>('/dashboard/');
}

export function useDashboard() {
  return useQuery({
    queryKey: ['dashboard'],
    queryFn: () => fetchDashboard(),
    staleTime: 5_000,
    refetchInterval: (query) => {
      // Poll on 15s interval ONLY while there are non-terminal in-progress contributions (PRD §17, Plan M7-T6)
      const data = query.state.data;
      if (!data) return false;
      const inProgress = data.in_progress_contributions;
      if (!inProgress || inProgress.length === 0) return false;
      const hasActive = inProgress.some(
        (c) => c.status !== 'MERGED' && c.status !== 'REJECTED'
      );
      return hasActive ? 15_000 : false;
    },
  });
}
