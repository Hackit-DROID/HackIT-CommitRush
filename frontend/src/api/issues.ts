import { useQuery } from '@tanstack/react-query';
import { apiRequest } from './client';
import {
  IssueCategoryItem,
  IssueDetail,
  IssueFilters,
  IssueListItem,
  PaginatedResponse,
} from '../types/api';
import { ISSUE_CATEGORIES } from '../constants/categories';

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

export async function fetchIssueCategories(): Promise<IssueCategoryItem[]> {
  try {
    const data = await apiRequest<IssueCategoryItem[]>('/issues/categories/');
    return Array.isArray(data) ? data : ISSUE_CATEGORIES;
  } catch {
    return ISSUE_CATEGORIES;
  }
}

export function useIssueCategories() {
  return useQuery({
    queryKey: ['issue-categories'],
    queryFn: fetchIssueCategories,
    initialData: ISSUE_CATEGORIES,
    staleTime: 60_000,
  });
}

