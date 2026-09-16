import { useQuery } from '@tanstack/react-query';
import { apiRequest } from './client';
import { OpsMetrics } from '../types/api';

export const opsKeys = {
  all: ['ops'] as const,
  metrics: () => [...opsKeys.all, 'metrics'] as const,
};

export async function fetchOpsMetrics(): Promise<OpsMetrics> {
  return apiRequest<OpsMetrics>('/ops/metrics/');
}

export function useOpsMetrics(refetchInterval: number | false = 30_000) {
  return useQuery({
    queryKey: opsKeys.metrics(),
    queryFn: fetchOpsMetrics,
    refetchInterval,
    staleTime: 10_000,
    retry: 1,
  });
}
