import { Link } from 'react-router-dom';
import { useDashboard } from '../api/dashboard';
import { ContributionStatusBadge } from '../components/ContributionStatusBadge';
import { EmptyState } from '../components/EmptyState';
import { ErrorState } from '../components/ErrorState';
import { DashboardSkeleton } from '../components/Skeletons';

export function DashboardPage() {
  const { data, isLoading, isError, error, refetch, isFetching } = useDashboard();

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div className="space-y-1">
          <h1 className="text-3xl font-display font-bold text-[#111111] tracking-tight">Participant Dashboard</h1>
          <p className="text-[#555555] text-sm">Your real-time sprint statistics, daily usage caps, and contribution progress.</p>
        </div>
        <DashboardSkeleton />
      </div>
    );
  }

  if (isError) {
    return (
      <div className="space-y-6">
        <div className="space-y-1">
          <h1 className="text-3xl font-display font-bold text-[#111111] tracking-tight">Participant Dashboard</h1>
          <p className="text-[#555555] text-sm">Your real-time sprint statistics, daily usage caps, and contribution progress.</p>
        </div>
        <ErrorState error={error} onRetry={() => refetch()} />
      </div>
    );
  }

  if (!data) {
    return (
      <EmptyState
        title="No Dashboard Data"
        message="Unable to load participant profile or session data."
      />
    );
  }

  const { participant, rank, total_points, merged_count, daily_usage, in_progress_contributions, recent_activity } = data;

  const pointsCap = daily_usage?.max_points || 120;
  const pointsClaimed = daily_usage?.points_count || 0;
  const pointsPct = Math.min(100, Math.round((pointsClaimed / pointsCap) * 100));

  const contribCap = daily_usage?.max_contributions || 5;
  const contribClaimed = daily_usage?.contributions_count || 0;
  const contribPct = Math.min(100, Math.round((contribClaimed / contribCap) * 100));

  const hasActiveContributions = (in_progress_contributions || []).length > 0;

  return (
    <div className="space-y-8" data-testid="dashboard-page">
      {/* Header Profile Summary */}
      <div className="bg-white border border-[#d8d8d3] rounded-md p-6 sm:p-8 shadow-sm flex flex-col md:flex-row items-start md:items-center justify-between gap-6">
        <div className="flex items-center gap-5 min-w-0">
          {participant.avatar_url ? (
            <img
              src={participant.avatar_url}
              alt={participant.github_username}
              className="w-16 h-16 sm:w-20 sm:h-20 rounded-full border border-[#d8d8d3] bg-[#f4f4f1] object-cover shadow-sm shrink-0"
            />
          ) : (
            <div className="w-16 h-16 sm:w-20 sm:h-20 rounded-full border border-[#d8d8d3] bg-[#f4f4f1] flex items-center justify-center font-bold text-2xl text-[#111111] shadow-sm shrink-0">
              {participant.github_username.charAt(0).toUpperCase()}
            </div>
          )}

          <div className="space-y-1 min-w-0">
            <div className="flex items-center gap-3 flex-wrap">
              <h1 className="text-2xl sm:text-3xl font-display font-bold text-[#111111] tracking-tight truncate max-w-[260px] sm:max-w-md">
                {participant.github_username}
              </h1>
              <Link
                to={`/profile/${participant.github_username}`}
                className="text-xs text-[#ff5a1f] hover:text-[#ff8a3d] font-medium underline underline-offset-2 transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-[#ff5a1f] focus-visible:ring-offset-1 rounded-sm shrink-0"
              >
                View Public Profile →
              </Link>
            </div>
            <p className="text-xs sm:text-sm text-[#555555] flex items-center gap-2 font-mono flex-wrap">
              <span>GitHub ID: {participant.github_id}</span>
              {isFetching && !isLoading && (
                <span className="text-[11px] text-[#ff5a1f] font-mono animate-pulse">
                  ● Live Sync
                </span>
              )}
            </p>
          </div>
        </div>

        {/* Aggregate Stats Cards */}
        <div className="grid grid-cols-3 gap-3 sm:gap-4 w-full md:w-auto font-mono shrink-0">
          <div className="bg-[#f4f4f1] border border-[#d8d8d3] rounded-md p-3 sm:p-4 text-center min-w-[90px] sm:min-w-[110px]">
            <span className="text-[10px] sm:text-xs uppercase tracking-wider text-[#777777] block mb-1">
              Rank
            </span>
            <span className="text-xl sm:text-2xl font-black text-[#111111] tabular-nums">
              {rank ? `#${rank}` : '-'}
            </span>
          </div>

          <div className="bg-[#f4f4f1] border border-[#d8d8d3] rounded-md p-3 sm:p-4 text-center min-w-[90px] sm:min-w-[110px]">
            <span className="text-[10px] sm:text-xs uppercase tracking-wider text-[#777777] block mb-1">
              Total Points
            </span>
            <span className="text-xl sm:text-2xl font-black text-[#ff5a1f] tabular-nums">
              {total_points}
            </span>
          </div>

          <div className="bg-[#f4f4f1] border border-[#d8d8d3] rounded-md p-3 sm:p-4 text-center min-w-[90px] sm:min-w-[110px]">
            <span className="text-[10px] sm:text-xs uppercase tracking-wider text-[#777777] block mb-1">
              Merged PRs
            </span>
            <span className="text-xl sm:text-2xl font-black text-[#111111] tabular-nums">
              {merged_count}
            </span>
          </div>
        </div>
      </div>

      {/* Daily Limits & Capacity */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6" data-testid="daily-limits-section">
        {/* Daily Points Cap */}
        <div className="bg-white border border-[#d8d8d3] rounded-md p-6 space-y-4 shadow-sm">
          <div className="flex items-center justify-between gap-2">
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-base font-display font-bold text-[#111111]">Daily Points Cap</h2>
                {pointsClaimed >= pointsCap ? (
                  <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold uppercase bg-amber-100 text-amber-900 border border-amber-300">
                    Daily Cap Hit
                  </span>
                ) : pointsClaimed > 0 ? (
                  <span className="px-2 py-0.5 rounded text-[10px] font-mono font-semibold bg-emerald-50 text-emerald-800 border border-emerald-200">
                    {Math.max(0, pointsCap - pointsClaimed)} pts left
                  </span>
                ) : null}
              </div>
              <p className="text-xs text-[#777777]">Resets daily at 00:00 IST</p>
            </div>
            <div className="text-right shrink-0">
              <span className="text-lg font-mono font-black text-[#ff5a1f] tabular-nums">{pointsClaimed}</span>
              <span className="text-xs text-[#777777] font-mono"> / {pointsCap} pts</span>
            </div>
          </div>

          <div
            className="w-full bg-[#f4f4f1] rounded-full h-2.5 overflow-hidden border border-[#d8d8d3]"
            role="progressbar"
            aria-valuenow={pointsClaimed}
            aria-valuemin={0}
            aria-valuemax={pointsCap}
            aria-label="Daily points capacity"
          >
            <div
              className={`h-full transition-all duration-500 rounded-full ${
                pointsPct >= 100 ? 'bg-amber-500' : 'bg-[#ff5a1f]'
              }`}
              style={{ width: `${pointsPct}%` }}
            />
          </div>

          <div className="flex justify-between text-xs text-[#555555] pt-1">
            <span>{Math.max(0, pointsCap - pointsClaimed)} pts capacity remaining today</span>
            <span className="font-mono tabular-nums">{pointsPct}% used</span>
          </div>
        </div>

        {/* Daily Contributions Cap */}
        <div className="bg-white border border-[#d8d8d3] rounded-md p-6 space-y-4 shadow-sm">
          <div className="flex items-center justify-between gap-2">
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-base font-display font-bold text-[#111111]">Daily Contribution Cap</h2>
                {contribClaimed >= contribCap ? (
                  <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold uppercase bg-amber-100 text-amber-900 border border-amber-300">
                    Daily Cap Hit
                  </span>
                ) : contribClaimed > 0 ? (
                  <span className="px-2 py-0.5 rounded text-[10px] font-mono font-semibold bg-emerald-50 text-emerald-800 border border-emerald-200">
                    {Math.max(0, contribCap - contribClaimed)} PRs left
                  </span>
                ) : null}
              </div>
              <p className="text-xs text-[#777777]">Maximum credited PRs per UTC day</p>
            </div>
            <div className="text-right shrink-0">
              <span className="text-lg font-mono font-black text-[#111111] tabular-nums">{contribClaimed}</span>
              <span className="text-xs text-[#777777] font-mono"> / {contribCap} PRs</span>
            </div>
          </div>

          <div
            className="w-full bg-[#f4f4f1] rounded-full h-2.5 overflow-hidden border border-[#d8d8d3]"
            role="progressbar"
            aria-valuenow={contribClaimed}
            aria-valuemin={0}
            aria-valuemax={contribCap}
            aria-label="Daily contribution capacity"
          >
            <div
              className={`h-full transition-all duration-500 rounded-full ${
                contribPct >= 100 ? 'bg-amber-500' : 'bg-[#050505]'
              }`}
              style={{ width: `${contribPct}%` }}
            />
          </div>

          <div className="flex justify-between text-xs text-[#555555] pt-1">
            <span>{Math.max(0, contribCap - contribClaimed)} credited PRs remaining today</span>
            <span className="font-mono tabular-nums">{contribPct}% used</span>
          </div>
        </div>
      </div>

      {/* In-Progress Contributions */}
      <div className="space-y-4" data-testid="in-progress-section">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <h2 className="text-xl font-display font-bold text-[#111111]">In-Progress Contributions</h2>
            {hasActiveContributions && (
              <span className="px-3 py-0.5 rounded-full text-xs font-mono font-semibold bg-[#f4f4f1] border border-[#d8d8d3] text-[#111111]">
                {in_progress_contributions.length} Active
              </span>
            )}
          </div>
          <Link
            to="/issues"
            className="text-xs font-medium text-[#ff5a1f] hover:text-[#ff8a3d] transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-[#ff5a1f] rounded-sm"
          >
            Browse More Issues →
          </Link>
        </div>

        {!hasActiveContributions ? (
          <div className="bg-white border border-[#d8d8d3] rounded-md p-8 text-center shadow-sm">
            <p className="text-[#555555] text-sm mb-3">No contributions are currently in validation or merge queue.</p>
            <Link
              to="/issues"
              className="inline-flex items-center px-5 py-2.5 rounded-[4px] bg-[#050505] hover:bg-[#1a1a1a] text-xs font-medium text-white transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-[#ff5a1f]"
            >
              Explore Open Issues
            </Link>
          </div>
        ) : (
          <div className="space-y-3">
            {in_progress_contributions.map((c) => (
              <div
                key={c.id}
                className="bg-white border border-[#d8d8d3] rounded-md p-5 flex flex-col sm:flex-row sm:items-center justify-between gap-4 transition-colors hover:border-[#111111] shadow-sm"
                data-testid={`in-progress-item-${c.id}`}
              >
                <div className="space-y-1.5 flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-xs font-mono text-[#777777] truncate max-w-[200px] sm:max-w-xs">
                      {c.pull_request?.repo || c.issue?.project}
                    </span>
                    <span className="text-[#777777]">•</span>
                    <span className="text-xs font-mono text-[#ff5a1f] shrink-0">
                      Issue #{c.issue?.github_number || c.issue?.id}
                    </span>
                  </div>
                  <h3 className="font-semibold text-[#111111] text-base break-words">
                    {c.issue?.title || `Contribution #${c.id}`}
                  </h3>
                </div>

                <div className="flex items-center gap-4 shrink-0 justify-between sm:justify-end">
                  <span className="text-xs font-mono font-bold text-[#ff5a1f] bg-orange-50 px-3 py-1 rounded-full border border-orange-200 tabular-nums">
                    +{c.issue?.points || 0} pts
                  </span>
                  <ContributionStatusBadge status={c.status} />
                  <Link
                    to={`/contributions/${c.id}`}
                    className="text-xs text-[#555555] hover:text-[#111111] transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-[#ff5a1f] rounded-sm"
                  >
                    Details →
                  </Link>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Recent Activity */}
      <div className="space-y-4" data-testid="recent-activity-section">
        <div className="flex items-center justify-between">
          <h2 className="text-xl font-display font-bold text-[#111111]">Recent Activity</h2>
          <Link
            to="/contributions"
            className="text-xs font-medium text-[#555555] hover:text-[#111111] transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-[#ff5a1f] rounded-sm"
          >
            View All Contributions ({merged_count + (in_progress_contributions?.length || 0)}) →
          </Link>
        </div>

        {(recent_activity || []).length === 0 ? (
          <div className="bg-white border border-[#d8d8d3] rounded-md p-8 text-center shadow-sm">
            <p className="text-[#555555] text-sm">No activity recorded yet.</p>
          </div>
        ) : (
          <div className="bg-white border border-[#d8d8d3] rounded-md divide-y divide-[#d8d8d3] overflow-hidden shadow-sm">
            {recent_activity.map((c) => (
              <div
                key={c.id}
                className="p-5 flex flex-col sm:flex-row sm:items-center justify-between gap-3 hover:bg-[#fafaf8] transition-colors"
                data-testid={`activity-item-${c.id}`}
              >
                <div className="space-y-1 flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-xs font-mono text-[#777777] truncate max-w-[200px] sm:max-w-xs">
                      {c.pull_request?.repo || c.issue?.project}
                    </span>
                    <span className="text-[#777777]">•</span>
                    <span className="text-xs font-mono text-[#777777] shrink-0">
                      PR #{c.pull_request?.number || '-'}
                    </span>
                  </div>
                  <h3 className="font-semibold text-[#111111] text-sm break-words">
                    {c.issue?.title || `Contribution #${c.id}`}
                  </h3>
                </div>

                <div className="flex items-center gap-4 shrink-0 justify-between sm:justify-end">
                  {c.status === 'MERGED' && (
                    <div className="text-right font-mono">
                      <span className="text-xs font-bold text-[#ff5a1f] block tabular-nums">
                        +{c.scoring_breakdown?.final_awarded_points ?? (c.issue?.points || 0)} pts
                      </span>
                      {c.scoring_breakdown && (
                        <span className="text-[10px] text-[#777777] block">
                          {c.scoring_breakdown.category_label} • {c.scoring_breakdown.multiplier}×
                          {c.scoring_breakdown.cap_applied !== 'Not reached' && (
                            <span className="text-amber-700 ml-1">({c.scoring_breakdown.cap_applied})</span>
                          )}
                        </span>
                      )}
                    </div>
                  )}
                  <ContributionStatusBadge status={c.status} />
                  <Link
                    to={`/contributions/${c.id}`}
                    className="text-xs text-[#555555] hover:text-[#111111] transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-[#ff5a1f] rounded-sm"
                  >
                    View →
                  </Link>
                </div>

              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
