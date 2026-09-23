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

export interface IssueCategoryItem {
  value: string;
  label: string;
  count?: number;
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
  avatar_url: string | null;
  is_suspended?: boolean;
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

export interface ScoringBreakdown {
  id: number;
  base_points: number;
  category: string;
  category_label: string;
  multiplier: number;
  calculated_points: number;
  per_pr_cap: number | null;
  points_after_pr_cap: number;
  daily_points_cap: number;
  daily_points_before: number;
  daily_allowance_remaining: number;
  cap_applied: string;
  final_awarded_points: number;
  farming_signals: Record<string, unknown>;
  created_at: string;
}

export interface Contribution {
  id: number;
  participant: ContributionParticipant;
  issue: ContributionIssue;
  pull_request: ContributionPullRequest;
  status: ContributionStatus | string;
  sub_status: string;
  status_message?: string;
  retry_count: number;
  flagged_reason: string;
  scoring_breakdown?: ScoringBreakdown | null;
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

// =============================================================================
// M7 API Interfaces (PRD §8.6, §16, §19, §23)
// =============================================================================

export interface LeaderboardEntry {
  rank: number;
  participant_id: number;
  github_username: string;
  avatar_url: string | null;
  total_points: number;
  merged_count: number;
  points_today?: number;
  daily_limit?: number;
  remaining_daily_allowance?: number;
  is_daily_limit_reached?: boolean;
}

export interface LeaderboardMe {
  rank: number | null;
  participant_id: number;
  github_username: string;
  avatar_url: string | null;
  total_points: number;
  merged_count: number;
  points_today?: number;
  daily_limit?: number;
  remaining_daily_allowance?: number;
  is_daily_limit_reached?: boolean;
}


export interface LeaderboardResponse {
  count: number;
  page: number;
  page_size: number;
  num_pages: number;
  frozen: boolean;
  frozen_at: string | null;
  results: LeaderboardEntry[];
  me?: LeaderboardMe | null;
}

export interface LeaderboardFilters {
  page?: number;
  page_size?: number;
  include_me?: boolean;
}

export interface DailyUsage {
  date: string;
  contributions_count: number;
  max_contributions: number;
  points_count: number;
  max_points: number;
}

export interface DashboardData {
  participant: ContributionParticipant;
  rank: number | null;
  total_points: number;
  merged_count: number;
  daily_usage: DailyUsage;
  in_progress_contributions: Contribution[];
  recent_activity: Contribution[];
}

export interface PublicProfileStats {
  total_contributions: number;
  merged_contributions: number;
  in_progress_contributions: number;
  rejected_contributions: number;
}

export interface PublicProfileContribution {
  id: number;
  project_name: string;
  issue_number: number;
  issue_title: string;
  points: number;
  merged_at: string | null;
  github_url: string;
}

export interface PublicProfile {
  id: number;
  github_id: number;
  github_username: string;
  avatar_url: string | null;
  total_points: number;
  merged_count: number;
  rank: number | null;
  stats: PublicProfileStats;
  recent_merged_contributions: PublicProfileContribution[];
}

export interface SystemStatus {
  merge_paused: boolean;
  validation_paused: boolean;
  submissions_paused: boolean;
  leaderboard_frozen: boolean;
}

export interface StatsParticipants {
  total: number;
  active: number;
}

export interface StatsPullRequests {
  total: number;
  merged: number;
}

export interface StatsContributions {
  total: number;
  by_status: Record<string, number>;
}

export interface StatsPoints {
  total_awarded: number;
  points_past_hour: number;
}

export interface StatsRates {
  merges_past_hour: number;
  points_past_hour: number;
}

export interface EventStats {
  event_status: string;
  system_status: SystemStatus;
  participants: StatsParticipants;
  pull_requests: StatsPullRequests;
  contributions: StatsContributions;
  points: StatsPoints;
  rates: StatsRates;
  updated_at: string;
}

export interface OpsQueues {
  validation_queued: number;
  validation_under_review: number;
  merge_approved: number;
  merge_active: number;
  flagged_or_retry: number;
  webhooks_total: number;
  webhooks_unprocessed: number;
}

export interface OpsSemaphore {
  configured_concurrency: number;
  active_semaphore_slots: number;
  available_slots: number;
}

export interface OpsMetrics {
  event_status: string;
  system_status: SystemStatus;
  queues: OpsQueues;
  semaphore: OpsSemaphore;
  oldest_queued_item_age_seconds: number | null;
  last_webhook_received_at: string | null;
  generated_at: string;
}

export interface CurrentUser {
  id: number | null;
  user_id: number;
  github_id: number | null;
  github_username: string;
  avatar_url: string | null;
  is_suspended: boolean;
  total_points: number;
  is_staff: boolean;
  is_authenticated: boolean;
  csrf_token?: string;
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

