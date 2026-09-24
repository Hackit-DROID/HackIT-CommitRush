import { Link, useSearchParams } from 'react-router-dom';
import { useDashboard } from '../api/dashboard';
import { useMyContributions } from '../api/contributions';
import { ContributionStatusBadge } from '../components/ContributionStatusBadge';
import { EmptyState } from '../components/EmptyState';
import { ErrorState } from '../components/ErrorState';
import { DashboardSkeleton } from '../components/Skeletons';
import { useDocumentTitle } from '../hooks/useDocumentTitle';

type ProfileTab = 'overview' | 'contributions' | 'activity' | 'statistics';

const STATUS_FILTER_OPTIONS = [
  { label: 'All Statuses', value: '' },
  { label: 'Pending', value: 'PENDING' },
  { label: 'Queued', value: 'QUEUED' },
  { label: 'Under Review', value: 'UNDER_REVIEW' },
  { label: 'Approved', value: 'APPROVED' },
  { label: 'Merging', value: 'MERGING' },
  { label: 'Merged', value: 'MERGED' },
  { label: 'Flagged', value: 'FLAGGED' },
  { label: 'Retry', value: 'RETRY' },
  { label: 'Rejected', value: 'REJECTED' },
];

export function MyProfilePage() {
  useDocumentTitle(
    'CommitRush — My Profile',
    'View your participant identity, sprint rank, points, and active pull request contributions.'
  );

  const [searchParams, setSearchParams] = useSearchParams();
  const currentTab = (searchParams.get('tab') as ProfileTab) || 'overview';
  const statusFilter = searchParams.get('status') || '';
  const pageParam = parseInt(searchParams.get('page') || '1', 10);

  const {
    data: dashboard,
    isLoading: isDashLoading,
    isError: isDashError,
    error: dashError,
    refetch: refetchDash,
    isFetching: isDashFetching,
  } = useDashboard();

  const {
    data: contributionsData,
    isLoading: isContribsLoading,
    isError: isContribsError,
    error: contribsError,
    refetch: refetchContribs,
  } = useMyContributions({
    status: statusFilter || undefined,
    page: pageParam > 0 ? pageParam : 1,
    page_size: 15,
  });

  const setTab = (tab: ProfileTab) => {
    const next = new URLSearchParams(searchParams);
    next.set('tab', tab);
    setSearchParams(next);
  };

  const setStatus = (status: string) => {
    const next = new URLSearchParams(searchParams);
    if (status) {
      next.set('status', status);
    } else {
      next.delete('status');
    }
    next.set('page', '1');
    setSearchParams(next);
  };

  const setPage = (newPage: number) => {
    const next = new URLSearchParams(searchParams);
    next.set('page', String(newPage));
    setSearchParams(next);
  };

  if (isDashLoading) {
    return (
      <div className="space-y-6" data-testid="my-profile-loading">
        <div className="space-y-2">
          <h1 className="text-3xl font-display font-bold text-[#111111] tracking-tight">My Profile</h1>
          <p className="text-[#555555] text-sm">Loading your developer profile, rank, and contribution records...</p>
        </div>
        <DashboardSkeleton />
      </div>
    );
  }

  if (isDashError) {
    return (
      <div className="space-y-6" data-testid="my-profile-error">
        <div className="space-y-2">
          <h1 className="text-3xl font-display font-bold text-[#111111] tracking-tight">My Profile</h1>
          <p className="text-[#555555] text-sm">Your personal developer profile and contribution sprint history.</p>
        </div>
        <ErrorState error={dashError} onRetry={() => refetchDash()} />
      </div>
    );
  }

  if (!dashboard) {
    return (
      <EmptyState
        title="Profile Not Found"
        message="Unable to load authenticated participant profile data."
      />
    );
  }

  const {
    participant,
    rank,
    total_points,
    merged_count,
    daily_usage,
    in_progress_contributions,
    recent_activity,
  } = dashboard;

  const pointsCap = daily_usage?.max_points || 120;
  const pointsClaimed = daily_usage?.points_count || 0;
  const pointsRemaining = Math.max(0, pointsCap - pointsClaimed);
  const pointsPct = Math.min(100, Math.round((pointsClaimed / pointsCap) * 100));

  const contribCap = daily_usage?.max_contributions || 5;
  const contribClaimed = daily_usage?.contributions_count || 0;
  const contribRemaining = Math.max(0, contribCap - contribClaimed);
  const contribPct = Math.min(100, Math.round((contribClaimed / contribCap) * 100));

  const activeContributions = in_progress_contributions || [];
  const recentList = recent_activity || [];
  const totalPages = contributionsData ? Math.max(1, Math.ceil(contributionsData.count / 15)) : 1;

  return (
    <div className="space-y-8" data-testid="my-profile-page">
      {/* 1. Developer Profile Header */}
      <section className="bg-white border border-[#d8d8d3] rounded-md p-6 sm:p-8 shadow-sm relative overflow-hidden">
        <div className="flex flex-col lg:flex-row items-start lg:items-center justify-between gap-6 relative">
          {/* Avatar & User Details */}
          <div className="flex items-center gap-4 sm:gap-6 flex-wrap sm:flex-nowrap">
            <div className="relative shrink-0">
              {participant.avatar_url ? (
                <img
                  src={participant.avatar_url}
                  alt={participant.github_username}
                  width="96"
                  height="96"
                  loading="eager"
                  decoding="async"
                  className="w-20 h-20 sm:w-24 sm:h-24 rounded-md border border-[#d8d8d3] bg-[#f4f4f1] object-cover shadow-sm"
                />
              ) : (
                <div className="w-20 h-20 sm:w-24 sm:h-24 rounded-md border border-[#d8d8d3] bg-[#f4f4f1] flex items-center justify-center font-display font-bold text-3xl text-[#111111] shadow-sm">
                  {participant.github_username ? participant.github_username.charAt(0).toUpperCase() : 'U'}
                </div>
              )}
              <span
                className="absolute -bottom-1 -right-1 w-4 h-4 rounded-full bg-[#3d5f58] border-2 border-white"
                title="Active"
              />
            </div>

            <div className="space-y-2 min-w-0">
              <div className="flex items-center gap-2.5 flex-wrap">
                <h1 className="text-2xl sm:text-3xl font-display font-bold text-[#111111] tracking-tight break-all">
                  {participant.github_username}
                </h1>
                <span className="px-2.5 py-0.5 rounded-full text-xs font-mono font-medium bg-[#f4f4f1] border border-[#d8d8d3] text-[#555555]">
                  Sprint Contributor
                </span>
                {participant.is_suspended && (
                  <span className="px-2.5 py-0.5 rounded-full text-xs font-mono font-semibold bg-rose-50 border border-rose-200 text-rose-800">
                    Suspended
                  </span>
                )}
              </div>

              <div className="flex items-center gap-3 text-xs sm:text-sm text-[#555555] flex-wrap">
                <a
                  href={`https://github.com/${participant.github_username}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1.5 text-[#111111] hover:text-[#ff5a1f] font-mono transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-[#ff5a1f] rounded-sm"
                >
                  <svg className="w-4 h-4 fill-current" viewBox="0 0 24 24">
                    <path fillRule="evenodd" clipRule="evenodd" d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.53 1.032 1.53 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z" />
                  </svg>
                  <span>github.com/{participant.github_username}</span>
                  <span>↗</span>
                </a>

                <span className="text-[#d8d8d3]">•</span>

                <Link
                  to={`/profile/${participant.github_username}`}
                  className="text-[#ff5a1f] hover:text-[#ff8a3d] font-medium underline underline-offset-2 transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-[#ff5a1f] rounded-sm"
                >
                  Public View →
                </Link>

                {isDashFetching && !isDashLoading && (
                  <span className="text-[11px] text-[#ff5a1f] font-mono animate-pulse">
                    ● Live Sync
                  </span>
                )}
              </div>
            </div>
          </div>

          {/* Quick Metrics Cards */}
          <div className="grid grid-cols-3 gap-2.5 sm:gap-3 w-full lg:w-auto shrink-0">
            {/* Rank Card */}
            <div className="bg-[#f4f4f1] border border-[#d8d8d3] rounded-md p-3 sm:p-4 text-center min-w-0 sm:min-w-[110px]">
              <span className="text-[10px] sm:text-xs font-mono uppercase tracking-wider text-[#777777] block mb-1">
                Current Rank
              </span>
              <span className="text-xl sm:text-2xl font-bold text-[#111111] font-mono tabular-nums" data-testid="profile-rank">
                {rank ? `#${rank}` : 'Not ranked yet'}
              </span>
            </div>

            {/* Points Card */}
            <div className="bg-[#f4f4f1] border border-[#d8d8d3] rounded-md p-3 sm:p-4 text-center min-w-0 sm:min-w-[110px]">
              <span className="text-[10px] sm:text-xs font-mono uppercase tracking-wider text-[#777777] block mb-1">
                Total Score
              </span>
              <span className="text-xl sm:text-2xl font-bold text-[#ff5a1f] font-mono tabular-nums" data-testid="profile-points">
                {total_points}
              </span>
            </div>

            {/* Merged PRs Card */}
            <div className="bg-[#f4f4f1] border border-[#d8d8d3] rounded-md p-3 sm:p-4 text-center min-w-0 sm:min-w-[110px]">
              <span className="text-[10px] sm:text-xs font-mono uppercase tracking-wider text-[#777777] block mb-1">
                Merged PRs
              </span>
              <span className="text-xl sm:text-2xl font-bold text-[#111111] font-mono tabular-nums" data-testid="profile-merged-count">
                {merged_count}
              </span>
            </div>
          </div>
        </div>
      </section>

      {/* 2. Internal Profile Navigation Tabs */}
      <div
        className="flex items-center space-x-2 border-b border-[#d8d8d3] pb-3 overflow-x-auto"
        role="tablist"
        aria-label="Profile sections"
      >
        <button
          onClick={() => setTab('overview')}
          role="tab"
          aria-selected={currentTab === 'overview'}
          className={`px-4 py-2 rounded-[4px] text-xs sm:text-sm font-semibold transition-all cursor-pointer whitespace-nowrap focus:outline-none focus-visible:ring-2 focus-visible:ring-[#ff5a1f] ${
            currentTab === 'overview'
              ? 'bg-[#050505] text-white shadow-sm'
              : 'text-[#555555] hover:text-[#111111] hover:bg-black/5'
          }`}
          data-testid="tab-overview"
        >
          Overview
        </button>

        <button
          onClick={() => setTab('contributions')}
          role="tab"
          aria-selected={currentTab === 'contributions'}
          className={`px-4 py-2 rounded-[4px] text-xs sm:text-sm font-semibold transition-all cursor-pointer whitespace-nowrap flex items-center gap-2 focus:outline-none focus-visible:ring-2 focus-visible:ring-[#ff5a1f] ${
            currentTab === 'contributions'
              ? 'bg-[#050505] text-white shadow-sm'
              : 'text-[#555555] hover:text-[#111111] hover:bg-black/5'
          }`}
          data-testid="tab-contributions"
        >
          <span>Contributions</span>
          {contributionsData && (
            <span className={`px-1.5 py-0.2 rounded-full text-[10px] font-mono ${
              currentTab === 'contributions' ? 'bg-white/20 text-white' : 'bg-[#f4f4f1] text-[#555555]'
            }`}>
              {contributionsData.count}
            </span>
          )}
        </button>

        <button
          onClick={() => setTab('activity')}
          role="tab"
          aria-selected={currentTab === 'activity'}
          className={`px-4 py-2 rounded-[4px] text-xs sm:text-sm font-semibold transition-all cursor-pointer whitespace-nowrap focus:outline-none focus-visible:ring-2 focus-visible:ring-[#ff5a1f] ${
            currentTab === 'activity'
              ? 'bg-[#050505] text-white shadow-sm'
              : 'text-[#555555] hover:text-[#111111] hover:bg-black/5'
          }`}
          data-testid="tab-activity"
        >
          Activity Timeline
        </button>

        <button
          onClick={() => setTab('statistics')}
          role="tab"
          aria-selected={currentTab === 'statistics'}
          className={`px-4 py-2 rounded-[4px] text-xs sm:text-sm font-semibold transition-all cursor-pointer whitespace-nowrap focus:outline-none focus-visible:ring-2 focus-visible:ring-[#ff5a1f] ${
            currentTab === 'statistics'
              ? 'bg-[#050505] text-white shadow-sm'
              : 'text-[#555555] hover:text-[#111111] hover:bg-black/5'
          }`}
          data-testid="tab-statistics"
        >
          Personal Statistics
        </button>
      </div>

      {/* 3. Tab Content */}

      {/* Tab: OVERVIEW */}
      {currentTab === 'overview' && (
        <div className="space-y-8" data-testid="overview-section">
          {/* Daily Usage & Limit Widget */}
          <div className="bg-white border border-[#d8d8d3] rounded-md p-6 sm:p-8 space-y-6 shadow-sm">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-[#d8d8d3] pb-4">
              <div>
                <h2 className="text-lg sm:text-xl font-display font-bold text-[#111111] tracking-tight flex items-center gap-2">
                  <span>Daily Quotas & Capacity</span>
                  <span className="text-xs font-mono font-normal text-[#777777]">
                    ({daily_usage?.date})
                  </span>
                </h2>
                <p className="text-xs text-[#555555] mt-0.5 font-sans">
                  Fair-play limits reset every 24 hours at midnight UTC.
                </p>
              </div>

              <div className="text-xs font-mono text-[#555555] bg-[#f4f4f1] border border-[#d8d8d3] px-3 py-1.5 rounded-full self-start sm:self-auto">
                ● Active Fair-Play Rules
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {/* Daily Points Meter */}
              <div className="bg-[#f4f4f1] border border-[#d8d8d3] rounded-md p-5 space-y-3">
                <div className="flex items-center justify-between text-sm gap-2">
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-[#111111]">Daily Points Quota</span>
                    {pointsRemaining === 0 && (
                      <span className="px-1.5 py-0.2 rounded text-[9px] font-mono font-bold uppercase bg-amber-100 text-amber-900 border border-amber-300">
                        Cap Hit
                      </span>
                    )}
                  </div>
                  <span className="font-mono text-xs text-[#ff5a1f] font-semibold tabular-nums shrink-0">
                    {pointsClaimed} / {pointsCap} pts ({pointsPct}%)
                  </span>
                </div>
                <div
                  className="w-full h-2.5 bg-white border border-[#d8d8d3] rounded-full overflow-hidden"
                  role="progressbar"
                  aria-valuenow={pointsClaimed}
                  aria-valuemin={0}
                  aria-valuemax={pointsCap}
                  aria-label="Daily points quota"
                >
                  <div
                    className={`h-full rounded-full transition-all duration-500 ${
                      pointsPct >= 100 ? 'bg-amber-500' : 'bg-[#ff5a1f]'
                    }`}
                    style={{ width: `${pointsPct}%` }}
                  />
                </div>
                <p className="text-xs text-[#555555]">
                  {pointsRemaining > 0 ? (
                    <span>{pointsRemaining} pts capacity remaining today</span>
                  ) : (
                    <span className="text-amber-800 font-medium">Daily points limit reached for today</span>
                  )}
                </p>
              </div>

              {/* Daily Contribution Meter */}
              <div className="bg-[#f4f4f1] border border-[#d8d8d3] rounded-md p-5 space-y-3">
                <div className="flex items-center justify-between text-sm gap-2">
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-[#111111]">Daily PRs Quota</span>
                    {contribRemaining === 0 && (
                      <span className="px-1.5 py-0.2 rounded text-[9px] font-mono font-bold uppercase bg-amber-100 text-amber-900 border border-amber-300">
                        Cap Hit
                      </span>
                    )}
                  </div>
                  <span className="font-mono text-xs text-[#111111] font-semibold tabular-nums shrink-0">
                    {contribClaimed} / {contribCap} PRs ({contribPct}%)
                  </span>
                </div>
                <div
                  className="w-full h-2.5 bg-white border border-[#d8d8d3] rounded-full overflow-hidden"
                  role="progressbar"
                  aria-valuenow={contribClaimed}
                  aria-valuemin={0}
                  aria-valuemax={contribCap}
                  aria-label="Daily PRs quota"
                >
                  <div
                    className={`h-full rounded-full transition-all duration-500 ${
                      contribPct >= 100 ? 'bg-amber-500' : 'bg-[#050505]'
                    }`}
                    style={{ width: `${contribPct}%` }}
                  />
                </div>
                <p className="text-xs text-[#555555]">
                  {contribRemaining > 0 ? (
                    <span>{contribRemaining} credited PRs remaining today</span>
                  ) : (
                    <span className="text-amber-800 font-medium">Daily PR cap reached for today</span>
                  )}
                </p>
              </div>
            </div>
          </div>

          {/* Active In-Progress Contributions Section */}
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <h2 className="text-xl font-display font-bold text-[#111111] tracking-tight">Active Pipeline Contributions</h2>
                {activeContributions.length > 0 && (
                  <span className="px-2 py-0.5 rounded-full bg-[#f4f4f1] border border-[#d8d8d3] text-[#111111] text-xs font-mono">
                    {activeContributions.length}
                  </span>
                )}
              </div>
              <Link
                to="/issues"
                className="text-xs text-[#ff5a1f] hover:text-[#ff8a3d] font-medium flex items-center gap-1 transition-colors"
              >
                <span>Find More Issues</span>
                <span>→</span>
              </Link>
            </div>

            {activeContributions.length > 0 ? (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {activeContributions.map((contrib) => (
                  <div
                    key={contrib.id}
                    data-testid={`in-progress-item-${contrib.id}`}
                    className="bg-white border border-[#d8d8d3] rounded-md p-5 space-y-4 hover:border-[#111111] transition-colors shadow-sm"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="space-y-1">
                        <span className="text-xs font-mono text-[#ff5a1f] block">
                          {contrib.pull_request?.repo || contrib.issue?.project} PR #{contrib.pull_request?.number}
                        </span>
                        <h3 className="text-base font-display font-bold text-[#111111] leading-snug line-clamp-2">
                          {contrib.issue?.title || 'Contribution In Progress'}
                        </h3>
                      </div>
                      <div className="shrink-0">
                        <ContributionStatusBadge status={contrib.status} size="sm" />
                      </div>
                    </div>

                    <div className="flex items-center justify-between text-xs text-[#555555] pt-3 border-t border-[#d8d8d3]">
                      <span className="font-mono text-[#111111] font-semibold">
                        +{contrib.issue?.points || 0} pts
                      </span>
                      <Link
                        to={`/contributions/${contrib.id}`}
                        className="text-[#555555] hover:text-[#111111] font-medium transition-colors"
                      >
                        View Validation Status →
                      </Link>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="bg-white border border-[#d8d8d3] rounded-md p-8 text-center space-y-3 shadow-sm">
                <p className="text-[#111111] text-sm font-medium">No pull requests currently in the validation queue.</p>
                <p className="text-[#555555] text-xs max-w-md mx-auto">
                  Claim an issue, implement your solution, and open a GitHub PR referencing the issue ID to start tracking.
                </p>
                <div className="pt-2">
                  <Link
                    to="/issues"
                    className="inline-flex items-center gap-2 px-5 py-2.5 rounded-[4px] bg-[#050505] hover:bg-[#1a1a1a] text-white text-xs font-semibold shadow-sm transition-colors"
                  >
                    <span>Browse Open Issues</span>
                    <span>→</span>
                  </Link>
                </div>
              </div>
            )}
          </div>

          {/* Recent Activity Snippet */}
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-xl font-display font-bold text-[#111111] tracking-tight">Recent Activity</h2>
              <button
                onClick={() => setTab('activity')}
                className="text-xs text-[#555555] hover:text-[#111111] font-medium cursor-pointer"
              >
                View Full Timeline →
              </button>
            </div>

            {recentList.length > 0 ? (
              <div className="bg-white border border-[#d8d8d3] rounded-md divide-y divide-[#d8d8d3] overflow-hidden shadow-sm">
                {recentList.slice(0, 5).map((item) => (
                  <div
                    key={item.id}
                    data-testid={`activity-item-${item.id}`}
                    className="p-4 sm:p-5 flex flex-col sm:flex-row sm:items-center justify-between gap-3 hover:bg-[#fafaf8] transition-colors"
                  >
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-mono text-[#777777]">
                          {item.pull_request?.repo} PR #{item.pull_request?.number}
                        </span>
                        <span className="text-[#777777]">•</span>
                        <span className="text-xs text-[#ff5a1f] font-mono font-semibold">
                          +{item.issue?.points || 0} pts
                        </span>
                      </div>
                      <p className="text-sm font-semibold text-[#111111] font-sans">
                        {item.issue?.title || 'Sprint Contribution'}
                      </p>
                    </div>

                    <div className="flex items-center gap-3 shrink-0">
                      <ContributionStatusBadge status={item.status} size="sm" />
                      <Link
                        to={`/contributions/${item.id}`}
                        className="text-xs text-[#555555] hover:text-[#111111] transition-colors"
                      >
                        Details →
                      </Link>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-xs text-[#777777] italic">No contribution activity recorded yet.</p>
            )}
          </div>
        </div>
      )}

      {/* Tab: CONTRIBUTIONS */}
      {currentTab === 'contributions' && (
        <div className="space-y-6" data-testid="contributions-section">
          {/* Filter Bar */}
          <div className="flex flex-wrap items-center gap-2 border-b border-[#d8d8d3] pb-4">
            <span className="text-xs font-mono font-medium text-[#777777] uppercase tracking-wider mr-1">
              Filter Status:
            </span>
            {STATUS_FILTER_OPTIONS.map((opt) => {
              const isActive = statusFilter === opt.value;
              return (
                <button
                  key={opt.value}
                  type="button"
                  onClick={() => setStatus(opt.value)}
                  className={`px-3.5 py-1.5 rounded-full text-xs font-mono font-medium transition-all cursor-pointer ${
                    isActive
                      ? 'bg-[#050505] text-white shadow-sm'
                      : 'bg-white text-[#555555] hover:text-[#111111] hover:bg-[#f4f4f1] border border-[#d8d8d3]'
                  }`}
                >
                  {opt.label}
                </button>
              );
            })}
          </div>

          {/* Contributions List */}
          {isContribsLoading ? (
            <div className="space-y-3">
              {[1, 2, 3, 4].map((i) => (
                <div key={i} className="h-20 bg-white border border-[#d8d8d3] rounded-md animate-pulse" />
              ))}
            </div>
          ) : isContribsError ? (
            <ErrorState error={contribsError} onRetry={() => refetchContribs()} />
          ) : !contributionsData || contributionsData.results.length === 0 ? (
            <div className="bg-white border border-[#d8d8d3] rounded-md p-12 text-center space-y-4 shadow-sm">
              <div className="text-3xl">📦</div>
              <h3 className="text-lg font-display font-bold text-[#111111]">No Contributions Found</h3>
              <p className="text-sm text-[#555555] max-w-md mx-auto">
                {statusFilter
                  ? `No contributions match the filter "${statusFilter}".`
                  : "You haven't submitted any pull requests to the drive yet."}
              </p>
              <Link
                to="/issues"
                className="inline-flex items-center gap-2 px-5 py-2.5 rounded-[4px] bg-[#050505] hover:bg-[#1a1a1a] text-white text-xs font-semibold shadow-sm transition-colors"
              >
                <span>Browse Issues to Start</span>
                <span>→</span>
              </Link>
            </div>
          ) : (
            <div className="space-y-4">
              <div className="bg-white border border-[#d8d8d3] rounded-md divide-y divide-[#d8d8d3] overflow-hidden shadow-sm">
                {contributionsData.results.map((c) => (
                  <div
                    key={c.id}
                    className="p-5 flex flex-col sm:flex-row sm:items-center justify-between gap-4 hover:bg-[#fafaf8] transition-colors"
                  >
                    <div className="space-y-1.5">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="text-xs font-mono text-[#ff5a1f] font-semibold">
                          {c.pull_request?.repo || c.issue?.project} PR #{c.pull_request?.number}
                        </span>
                        <span className="text-[#777777]">•</span>
                        <span className="text-xs text-[#555555] font-mono">
                          Issue #{c.issue?.github_number || c.issue?.id}
                        </span>
                        <span className="text-[#777777]">•</span>
                        <span className="text-xs text-[#111111] font-mono font-bold">
                          +{c.issue?.points || 0} pts
                        </span>
                      </div>

                      <h4 className="text-base font-display font-bold text-[#111111] leading-snug">
                        {c.issue?.title || 'Contribution'}
                      </h4>

                      {c.status_message && (
                        <p className="text-xs text-[#555555] font-mono">
                          {c.status_message}
                        </p>
                      )}
                    </div>

                    <div className="flex items-center gap-4 shrink-0">
                      <ContributionStatusBadge status={c.status} />
                      <Link
                        to={`/contributions/${c.id}`}
                        className="px-3.5 py-1.5 rounded-[4px] bg-white hover:bg-[#f4f4f1] text-[#111111] text-xs font-medium border border-[#d8d8d3] transition-colors"
                      >
                        View Details →
                      </Link>
                    </div>
                  </div>
                ))}
              </div>

              {/* Pagination */}
              {totalPages > 1 && (
                <div className="flex items-center justify-between pt-4 text-xs text-[#555555] font-mono">
                  <span>
                    Page {pageParam} of {totalPages} ({contributionsData.count} total)
                  </span>
                  <div className="flex gap-2">
                    <button
                      onClick={() => setPage(pageParam - 1)}
                      disabled={pageParam <= 1}
                      className="px-3.5 py-1.5 rounded-[4px] bg-white hover:bg-[#f4f4f1] border border-[#d8d8d3] disabled:opacity-40 text-[#111111] transition-colors cursor-pointer"
                    >
                      Previous
                    </button>
                    <button
                      onClick={() => setPage(pageParam + 1)}
                      disabled={pageParam >= totalPages}
                      className="px-3.5 py-1.5 rounded-[4px] bg-white hover:bg-[#f4f4f1] border border-[#d8d8d3] disabled:opacity-40 text-[#111111] transition-colors cursor-pointer"
                    >
                      Next
                    </button>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Tab: ACTIVITY TIMELINE */}
      {currentTab === 'activity' && (
        <div className="space-y-6" data-testid="activity-section">
          <div className="bg-white border border-[#d8d8d3] rounded-md p-6 sm:p-8 space-y-6 shadow-sm">
            <h2 className="text-xl font-display font-bold text-[#111111] tracking-tight">Chronological Sprint Activity</h2>
            {recentList.length > 0 ? (
              <div className="relative border-l-2 border-[#d8d8d3] ml-4 space-y-8 pl-6">
                {recentList.map((act) => (
                  <div key={act.id} className="relative space-y-2">
                    <div
                      className={`absolute -left-[31px] top-0.5 w-4 h-4 rounded-full border-2 border-white ${
                        act.status === 'MERGED'
                          ? 'bg-[#3d5f58]'
                          : act.status === 'REJECTED'
                          ? 'bg-[#ff5a1f]'
                          : 'bg-[#555555]'
                      }`}
                    />
                    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-1">
                      <span className="text-xs font-mono text-[#ff5a1f]">
                        {act.pull_request?.repo} PR #{act.pull_request?.number}
                      </span>
                      <ContributionStatusBadge status={act.status} size="sm" />
                    </div>

                    <h4 className="text-base font-display font-bold text-[#111111]">
                      {act.issue?.title || 'PR Submission'}
                    </h4>

                    <div className="flex items-center gap-3 text-xs text-[#555555] font-mono">
                      <span>Bounty: {act.issue?.points || 0} pts</span>
                      <span className="text-[#d8d8d3]">•</span>
                      <Link
                        to={`/contributions/${act.id}`}
                        className="text-[#555555] hover:text-[#ff5a1f] hover:underline"
                      >
                        Inspect Full Audit Trail →
                      </Link>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-[#777777] italic">No activity logged yet.</p>
            )}
          </div>
        </div>
      )}

      {/* Tab: PERSONAL STATISTICS */}
      {currentTab === 'statistics' && (
        <div className="space-y-6" data-testid="statistics-section">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="bg-white border border-[#d8d8d3] rounded-md p-5 space-y-2 shadow-sm">
              <span className="text-xs font-mono uppercase tracking-wider text-[#777777]">
                Current Sprint Rank
              </span>
              <p className="text-3xl font-display font-bold text-[#111111] font-mono tabular-nums">
                {rank ? `#${rank}` : 'Not ranked yet'}
              </p>
              <p className="text-xs text-[#777777]">Live authoritative leaderboard rank</p>
            </div>

            <div className="bg-white border border-[#d8d8d3] rounded-md p-5 space-y-2 shadow-sm">
              <span className="text-xs font-mono uppercase tracking-wider text-[#777777]">
                Total Score
              </span>
              <p className="text-3xl font-display font-bold text-[#ff5a1f] font-mono tabular-nums">
                {total_points} pts
              </p>
              <p className="text-xs text-[#777777]">Accumulated verified points</p>
            </div>

            <div className="bg-white border border-[#d8d8d3] rounded-md p-5 space-y-2 shadow-sm">
              <span className="text-xs font-mono uppercase tracking-wider text-[#777777]">
                Merged Contributions
              </span>
              <p className="text-3xl font-display font-bold text-[#111111] font-mono tabular-nums">
                {merged_count} PRs
              </p>
              <p className="text-xs text-[#777777]">Merged into monorepo target</p>
            </div>

            <div className="bg-white border border-[#d8d8d3] rounded-md p-5 space-y-2 shadow-sm">
              <span className="text-xs font-mono uppercase tracking-wider text-[#777777]">
                In-Progress PRs
              </span>
              <p className="text-3xl font-display font-bold text-[#111111] font-mono tabular-nums">
                {activeContributions.length} PRs
              </p>
              <p className="text-xs text-[#777777]">Validating or queued for merge</p>
            </div>
          </div>

          <div className="bg-white border border-[#d8d8d3] rounded-md p-6 sm:p-8 space-y-4 shadow-sm">
            <h3 className="text-lg font-display font-bold text-[#111111] tracking-tight">Personal Sprint Capacity Breakdown</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div className="bg-[#f4f4f1] border border-[#d8d8d3] rounded-md p-5 space-y-3">
                <div className="flex justify-between text-sm">
                  <span className="text-[#111111] font-medium">Daily Points Capacity</span>
                  <span className="font-mono text-[#ff5a1f] font-semibold tabular-nums">{pointsPct}% Used</span>
                </div>
                <div
                  className="w-full h-2.5 bg-white border border-[#d8d8d3] rounded-full overflow-hidden"
                  role="progressbar"
                  aria-valuenow={pointsClaimed}
                  aria-valuemin={0}
                  aria-valuemax={pointsCap}
                  aria-label="Daily points capacity"
                >
                  <div
                    className={`h-full rounded-full transition-all duration-500 ${
                      pointsPct >= 100 ? 'bg-amber-500' : 'bg-[#ff5a1f]'
                    }`}
                    style={{ width: `${pointsPct}%` }}
                  />
                </div>
                <div className="flex justify-between text-xs text-[#777777] font-mono">
                  <span className="tabular-nums">Claimed: {pointsClaimed} pts</span>
                  <span className="tabular-nums">Daily Cap: {pointsCap} pts</span>
                </div>
              </div>

              <div className="bg-[#f4f4f1] border border-[#d8d8d3] rounded-md p-5 space-y-3">
                <div className="flex justify-between text-sm">
                  <span className="text-[#111111] font-medium">Daily Merged PRs Capacity</span>
                  <span className="font-mono text-[#111111] font-semibold tabular-nums">{contribPct}% Used</span>
                </div>
                <div
                  className="w-full h-2.5 bg-white border border-[#d8d8d3] rounded-full overflow-hidden"
                  role="progressbar"
                  aria-valuenow={contribClaimed}
                  aria-valuemin={0}
                  aria-valuemax={contribCap}
                  aria-label="Daily merged PRs capacity"
                >
                  <div
                    className={`h-full rounded-full transition-all duration-500 ${
                      contribPct >= 100 ? 'bg-amber-500' : 'bg-[#050505]'
                    }`}
                    style={{ width: `${contribPct}%` }}
                  />
                </div>
                <div className="flex justify-between text-xs text-[#777777] font-mono">
                  <span className="tabular-nums">Claimed: {contribClaimed} PRs</span>
                  <span className="tabular-nums">Daily Cap: {contribCap} PRs</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
