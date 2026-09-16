import { useQuery } from '@tanstack/react-query';
import { apiRequest } from './client';
import {
  PaginatedResponse,
  ProjectDetail,
  ProjectFilters,
  ProjectListItem,
} from '../types/api';

export async function fetchProjects(
  filters: ProjectFilters = {}
): Promise<PaginatedResponse<ProjectListItem>> {
  return apiRequest<PaginatedResponse<ProjectListItem>>('/projects/', {
    search: filters.search,
    language: filters.language,
    enabled: filters.enabled,
    page: filters.page,
    page_size: filters.page_size,
  });
}

export async function fetchProject(slug: string): Promise<ProjectDetail> {
  const cleanSlug = encodeURIComponent(slug.trim()).replace(/%2F/g, '/');
  return apiRequest<ProjectDetail>(`/projects/${cleanSlug}/`);
}

export function useProjects(filters: ProjectFilters = {}) {
  return useQuery({
    queryKey: ['projects', filters],
    queryFn: () => fetchProjects(filters),
    placeholderData: (previousData) => previousData,
    staleTime: 30_000,
  });
}

export function useProject(slug: string) {
  return useQuery({
    queryKey: ['project', slug],
    queryFn: () => fetchProject(slug),
    enabled: Boolean(slug && slug.trim()),
    staleTime: 60_000,
  });
}
