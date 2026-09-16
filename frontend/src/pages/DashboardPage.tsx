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
        <div className="space-y-2">
          <h1 className="text-3xl font-extrabold text-white tracking-tight">Participant Dashboard</h1>
          <p className="text-slate-400 text-sm">Your real-time sprint statistics, daily usage caps, and contribution progress.</p>
        </div>
        <DashboardSkeleton />
      </div>
    );
  }

  if (isError) {
    return (
      <div className="space-y-6">
        <div className="space-y-2">
          <h1 className="text-3xl font-extrabold text-white tracking-tight">Participant Dashboard</h1>
          <p className="text-slate-400 text-sm">Your real-time sprint statistics, daily usage caps, and contribution progress.</p>
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

  const pointsCap = daily_usage?.max_points || 500;
  const pointsClaimed = daily_usage?.points_count || 0;
  const pointsPct = Math.min(100, Math.round((pointsClaimed / pointsCap) * 100));

  const contribCap = daily_usage?.max_contributions || 5;
  const contribClaimed = daily_usage?.contributions_count || 0;
  const contribPct = Math.min(100, Math.round((contribClaimed / contribCap) * 100));

  const hasActiveContributions = (in_progress_contributions || []).length > 0;

  return (
    <div className="space-y-8" data-testid="dashboard-page">
      {/* Header Profile Summary */}
      <div className="bg-gradient-to-r from-slate-900 via-slate-900 to-indigo-950/40 border border-slate-800 rounded-3xl p-6 sm:p-8 shadow-xl shadow-slate-950/50 flex flex-col md:flex-row items-start md:items-center justify-between gap-6">
        <div className="flex items-center gap-5">
          {participant.avatar_url ? (
            <img
              src={participant.avatar_url}
              alt={participant.github_username}
              className="w-16 h-16 sm:w-20 sm:h-20 rounded-2xl border-2 border-indigo-500/60 bg-slate-800 object-cover shadow-md"
            />
          ) : (
            <div className="w-16 h-16 sm:w-20 sm:h-20 rounded-2xl border-2 border-indigo-500/60 bg-slate-800 flex items-center justify-center font-black text-2xl text-white shadow-md">
              {participant.github_username.charAt(0).toUpperCase()}
            </div>
          )}

          <div className="space-y-1">
            <div className="flex items-center gap-3">
              <h1 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight">
                {participant.github_username}
              </h1>
              <Link
                to={`/profile/${participant.github_username}`}
                className="text-xs text-indigo-400 hover:text-indigo-300 font-medium underline underline-offset-2 transition-colors"
              >
                View Public Profile →
              </Link>
            </div>
            <p className="text-xs sm:text-sm text-slate-400 flex items-center gap-2">
              <span>GitHub ID: {participant.github_id}</span>
              {isFetching && !isLoading && (
                <span className="text-[11px] text-cyan-400 font-mono animate-pulse">
                  ● Live Sync
                </span>
              )}
            </p>
          </div>
        </div>

        {/* Aggregate Stats Cards */}
        <div className="grid grid-cols-3 gap-3 sm:gap-4 w-full md:w-auto">
          <div className="bg-slate-950/80 border border-slate-800/80 rounded-2xl p-3 sm:p-4 text-center min-w-[90px] sm:min-w-[110px]">
            <span className="text-[10px] sm:text-xs font-mono uppercase tracking-wider text-slate-500 block mb-1">
              Rank
            </span>
            <span className="text-xl sm:text-2xl font-black text-indigo-400">
              {rank ? `#${rank}` : '-'}
            </span>
          </div>

          <div className="bg-slate-950/80 border border-slate-800/80 rounded-2xl p-3 sm:p-4 text-center min-w-[90px] sm:min-w-[110px]">
            <span className="text-[10px] sm:text-xs font-mono uppercase tracking-wider text-slate-500 block mb-1">
              Total Points
            </span>
            <span className="text-xl sm:text-2xl font-black text-cyan-400">
              {total_points}
            </span>
          </div>

          <div className="bg-slate-950/80 border border-slate-800/80 rounded-2xl p-3 sm:p-4 text-center min-w-[90px] sm:min-w-[110px]">
            <span className="text-[10px] sm:text-xs font-mono uppercase tracking-wider text-slate-500 block mb-1">
              Merged PRs
            </span>
            <span className="text-xl sm:text-2xl font-black text-slate-200">
              {merged_count}
            </span>
          </div>
        </div>
      </div>

      {/* Daily Limits & Capacity */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6" data-testid="daily-limits-section">
        {/* Daily Points Cap */}
        <div className="bg-slate-900/50 border border-slate-800 rounded-2xl p-6 space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-base font-bold text-white">Daily Points Cap</h2>
              <p className="text-xs text-slate-400">Resets daily at 00:00 UTC</p>
            </div>
            <div className="text-right">
              <span className="text-lg font-mono font-black text-cyan-400">{pointsClaimed}</span>
              <span className="text-xs text-slate-500 font-mono"> / {pointsCap} pts</span>
            </div>
          </div>

          <div className="w-full bg-slate-950 rounded-full h-3 overflow-hidden border border-slate-800/80">
            <div
              className={`h-full transition-all duration-500 rounded-full ${
                pointsPct >= 100 ? 'bg-amber-500' : 'bg-cyan-500'
              }`}
              style={{ width: `${pointsPct}%` }}
            />
          </div>

          <div className="flex justify-between text-xs text-slate-400 pt-1">
            <span>{Math.max(0, pointsCap - pointsClaimed)} pts capacity remaining today</span>
            <span>{pointsPct}% used</span>
          </div>
        </div>

        {/* Daily Contributions Cap */}
        <div className="bg-slate-900/50 border border-slate-800 rounded-2xl p-6 space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-base font-bold text-white">Daily Contribution Cap</h2>
              <p className="text-xs text-slate-400">Maximum credited PRs per UTC day</p>
            </div>
            <div className="text-right">
              <span className="text-lg font-mono font-black text-indigo-400">{contribClaimed}</span>
              <span className="text-xs text-slate-500 font-mono"> / {contribCap} PRs</span>
            </div>
          </div>

          <div className="w-full bg-slate-950 rounded-full h-3 overflow-hidden border border-slate-800/80">
            <div
              className={`h-full transition-all duration-500 rounded-full ${
                contribPct >= 100 ? 'bg-amber-500' : 'bg-indigo-500'
              }`}
              style={{ width: `${contribPct}%` }}
            />
          </div>

          <div className="flex justify-between text-xs text-slate-400 pt-1">
            <span>{Math.max(0, contribCap - contribClaimed)} credited PRs remaining today</span>
            <span>{contribPct}% used</span>
          </div>
        </div>
      </div>

      {/* In-Progress Contributions */}
      <div className="space-y-4" data-testid="in-progress-section">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <h2 className="text-xl font-bold text-white">In-Progress Contributions</h2>
            {hasActiveContributions && (
              <span className="px-2.5 py-0.5 rounded-full text-xs font-mono font-semibold bg-cyan-950 border border-cyan-800 text-cyan-400">
                {in_progress_contributions.length} Active
              </span>
            )}
          </div>
          <Link
            to="/issues"
            className="text-xs font-medium text-cyan-400 hover:text-cyan-300 transition-colors"
          >
            Browse More Issues →
          </Link>
        </div>

        {!hasActiveContributions ? (
          <div className="bg-slate-900/30 border border-slate-800/60 rounded-2xl p-8 text-center">
            <p className="text-slate-400 text-sm mb-3">No contributions are currently in validation or merge queue.</p>
            <Link
              to="/issues"
              className="inline-flex items-center px-4 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-xs font-medium text-cyan-400 border border-slate-700 transition-colors"
            >
              Explore Open Issues
            </Link>
          </div>
        ) : (
          <div className="space-y-3">
            {in_progress_contributions.map((c) => (
              <div
                key={c.id}
                className="bg-slate-900/60 border border-slate-800 rounded-2xl p-4 sm:p-5 flex flex-col sm:flex-row sm:items-center justify-between gap-4 transition-colors hover:border-slate-700"
                data-testid={`in-progress-item-${c.id}`}
              >
                <div className="space-y-1.5 flex-1">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-xs font-mono text-slate-400">
                      {c.pull_request?.repo || c.issue?.project}
                    </span>
                    <span className="text-slate-600">•</span>
                    <span className="text-xs font-mono text-cyan-400">
                      Issue #{c.issue?.github_number || c.issue?.id}
                    </span>
                  </div>
                  <h3 className="font-semibold text-white text-base">
                    {c.issue?.title || `Contribution #${c.id}`}
                  </h3>
                </div>

                <div className="flex items-center gap-4 shrink-0 justify-between sm:justify-end">
                  <span className="text-xs font-mono font-bold text-cyan-400 bg-slate-950 px-2.5 py-1 rounded-lg border border-slate-800">
                    +{c.issue?.points || 0} pts
                  </span>
                  <ContributionStatusBadge status={c.status} />
                  <Link
                    to={`/contributions/${c.id}`}
                    className="text-xs text-slate-400 hover:text-white transition-colors"
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
          <h2 className="text-xl font-bold text-white">Recent Activity</h2>
          <Link
            to="/contributions"
            className="text-xs font-medium text-slate-400 hover:text-white transition-colors"
          >
            View All Contributions ({merged_count + (in_progress_contributions?.length || 0)}) →
          </Link>
        </div>

        {(recent_activity || []).length === 0 ? (
          <div className="bg-slate-900/30 border border-slate-800/60 rounded-2xl p-8 text-center">
            <p className="text-slate-400 text-sm">No activity recorded yet.</p>
          </div>
        ) : (
          <div className="bg-slate-900/50 border border-slate-800 rounded-2xl divide-y divide-slate-800/60 overflow-hidden">
            {recent_activity.map((c) => (
              <div
                key={c.id}
                className="p-4 sm:p-5 flex flex-col sm:flex-row sm:items-center justify-between gap-3 hover:bg-slate-800/30 transition-colors"
                data-testid={`activity-item-${c.id}`}
              >
                <div className="space-y-1 flex-1">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-mono text-slate-400">
                      {c.pull_request?.repo || c.issue?.project}
                    </span>
                    <span className="text-slate-600">•</span>
                    <span className="text-xs font-mono text-slate-500">
                      PR #{c.pull_request?.number || '-'}
                    </span>
                  </div>
                  <h3 className="font-semibold text-white text-sm">
                    {c.issue?.title || `Contribution #${c.id}`}
                  </h3>
                </div>

                <div className="flex items-center gap-4 shrink-0 justify-between sm:justify-end">
                  <span className="text-xs font-mono text-slate-300">
                    {c.status === 'MERGED' ? `+${c.issue?.points || 0} pts` : ''}
                  </span>
                  <ContributionStatusBadge status={c.status} />
                  <Link
                    to={`/contributions/${c.id}`}
                    className="text-xs text-slate-400 hover:text-white transition-colors"
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
