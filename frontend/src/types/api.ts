export interface PaginatedResponse<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

export interface ProjectListItem {
  id: number;
  github_repo_id: number;
  owner: string;
  name: string;
  full_name: string;
  language: string;
  is_enabled: boolean;
  description: string;
}

export interface ContributionActivity {
  total_contributions: number;
  merged_contributions: number;
  in_progress_contributions: number;
}

export interface ProjectDetail extends ProjectListItem {
  issue_count: number;
  open_issue_count: number;
  contribution_activity: ContributionActivity;
}

export interface IssueListItem {
  id: number;
  title: string;
  project: string;
  github_number: number;
  points: number;
  difficulty: string;
  category: string;
  status: string;
  is_featured: boolean;
  labels: string[];
  github_url: string;
  created_at?: string;
}

export interface IssueDetail extends IssueListItem {
  github_issue_id: number;
  project_id: number;
  project_name: string;
}

export interface ProjectFilters {
  search?: string;
  language?: string;
  enabled?: boolean | string;
  page?: number;
  page_size?: number;
}

export interface IssueFilters {
  project?: string;
  language?: string;
  difficulty?: string;
  category?: string;
  status?: string;
  is_featured?: boolean | string;
  points_min?: number;
  points_max?: number;
  sort?: string;
  page?: number;
  page_size?: number;
}

export class ApiError extends Error {
  status: number;
  data: unknown;

  constructor(status: number, message: string, data?: unknown) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.data = data;
  }

  get isRateLimited(): boolean {
    return this.status === 429;
  }

  get isNotFound(): boolean {
    return this.status === 404;
  }
}
