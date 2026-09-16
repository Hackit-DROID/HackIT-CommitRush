import { useQuery } from '@tanstack/react-query';
import { apiRequest } from './client';
import {
  IssueDetail,
  IssueFilters,
  IssueListItem,
  PaginatedResponse,
} from '../types/api';

export async function fetchIssues(
  filters: IssueFilters = {}
): Promise<PaginatedResponse<IssueListItem>> {
  return apiRequest<PaginatedResponse<IssueListItem>>('/issues/', {
    project: filters.project,
    language: filters.language,
    difficulty: filters.difficulty,
    category: filters.category,
    status: filters.status,
    is_featured: filters.is_featured,
    points_min: filters.points_min,
    points_max: filters.points_max,
    sort: filters.sort,
    page: filters.page,
    page_size: filters.page_size,
  });
}

export async function fetchIssue(id: number | string): Promise<IssueDetail> {
  return apiRequest<IssueDetail>(`/issues/${id}/`);
}

export function useIssues(filters: IssueFilters = {}) {
  return useQuery({
    queryKey: ['issues', filters],
    queryFn: () => fetchIssues(filters),
    placeholderData: (previousData) => previousData,
    staleTime: 30_000,
  });
}

export function useIssue(id: number | string | undefined) {
  return useQuery({
    queryKey: ['issue', id],
    queryFn: () => fetchIssue(id!),
    enabled: Boolean(id),
    staleTime: 60_000,
  });
}
