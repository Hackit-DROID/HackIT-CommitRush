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

export type ContributionStatus =
  | 'PENDING'
  | 'QUEUED'
  | 'UNDER_REVIEW'
  | 'APPROVED'
  | 'MERGING'
  | 'MERGED'
  | 'REJECTED'
  | 'FLAGGED'
  | 'RETRY';

export interface ContributionParticipant {
  id: number;
  github_id: number;
  github_username: string;
  avatar_url: string;
}

export interface ContributionIssue {
  id: number;
  github_issue_id: number;
  title: string;
  project: string;
  github_number: number;
  points: number;
  difficulty: string;
  category: string;
  status: string;
  github_url: string;
}

export interface ContributionPullRequest {
  id: number;
  github_pr_id: number;
  number: number;
  repo: string;
  merged: boolean;
  merged_at: string | null;
  head_sha: string;
  github_url: string;
}

export interface Contribution {
  id: number;
  participant: ContributionParticipant;
  issue: ContributionIssue;
  pull_request: ContributionPullRequest;
  status: ContributionStatus | string;
  sub_status: string;
  retry_count: number;
  flagged_reason: string;
  approved_at: string | null;
  merged_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface ContributionFilters {
  status?: string;
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
