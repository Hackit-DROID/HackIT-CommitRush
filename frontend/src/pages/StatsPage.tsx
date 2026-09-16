import { useStats } from '../api/stats';
import { ErrorState } from '../components/ErrorState';
import { StatsSkeleton } from '../components/Skeletons';

export function StatsPage() {
  const { data, isLoading, isError, error, refetch, isFetching } = useStats();

  if (isLoading) {
    return <StatsSkeleton />;
  }

  if (isError) {
    return (
      <div className="space-y-6">
        <div className="space-y-2">
          <h1 className="text-3xl font-extrabold text-white tracking-tight">Event Statistics</h1>
          <p className="text-slate-400 text-sm">Real-time aggregate activity across all event repositories.</p>
        </div>
        <ErrorState error={error} onRetry={() => refetch()} />
      </div>
    );
  }

  if (!data) return null;

  const {
    event_status,
    system_status,
    participants,
    pull_requests,
    contributions,
    points,
    rates,
    updated_at,
  } = data;

  const statusList = [
    { key: 'PENDING', label: 'Pending', count: contributions.by_status?.PENDING || 0, color: 'text-slate-300' },
    { key: 'QUEUED', label: 'Queued', count: contributions.by_status?.QUEUED || 0, color: 'text-indigo-400' },
    { key: 'UNDER_REVIEW', label: 'Under Review', count: contributions.by_status?.UNDER_REVIEW || 0, color: 'text-blue-400' },
    { key: 'APPROVED', label: 'Approved', count: contributions.by_status?.APPROVED || 0, color: 'text-cyan-400' },
    { key: 'MERGING', label: 'Merging', count: contributions.by_status?.MERGING || 0, color: 'text-purple-400' },
    { key: 'MERGED', label: 'Merged', count: contributions.by_status?.MERGED || 0, color: 'text-emerald-400' },
    { key: 'REJECTED', label: 'Rejected', count: contributions.by_status?.REJECTED || 0, color: 'text-red-400' },
    { key: 'FLAGGED', label: 'Flagged', count: contributions.by_status?.FLAGGED || 0, color: 'text-amber-400' },
    { key: 'RETRY', label: 'Retry', count: contributions.by_status?.RETRY || 0, color: 'text-orange-400' },
  ];

  return (
    <div className="space-y-8" data-testid="stats-page">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="space-y-1">
          <div className="flex items-center gap-3">
            <h1 className="text-3xl font-extrabold text-white tracking-tight">Event Statistics</h1>
            <span className="px-2.5 py-0.5 rounded-full text-xs font-mono font-bold uppercase bg-emerald-950 border border-emerald-800 text-emerald-400">
              {event_status}
            </span>
            {isFetching && (
              <span className="text-xs text-slate-500 font-mono animate-pulse">
                Updating...
              </span>
            )}
          </div>
          <p className="text-slate-400 text-sm">
            Aggregate contribution metrics refreshed periodically from PostgreSQL.
          </p>
        </div>

        <div className="text-xs text-slate-500 font-mono self-start sm:self-auto">
          Updated: {new Date(updated_at).toLocaleTimeString()}
        </div>
      </div>

      {/* Aggregate Overview Metric Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5" data-testid="stats-overview-grid">
        {/* Participants */}
        <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-6 space-y-2">
          <span className="text-xs font-mono uppercase tracking-wider text-slate-400">
            Total Participants
          </span>
          <div className="text-3xl font-black text-white font-mono">{participants.total}</div>
          <p className="text-xs text-slate-500 font-mono">
            {participants.active} active contributors
          </p>
        </div>

        {/* Pull Requests */}
        <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-6 space-y-2">
          <span className="text-xs font-mono uppercase tracking-wider text-slate-400">
            Total Pull Requests
          </span>
          <div className="text-3xl font-black text-indigo-400 font-mono">{pull_requests.total}</div>
          <p className="text-xs text-slate-500 font-mono">
            {pull_requests.merged} successfully merged
          </p>
        </div>

        {/* Total Points Awarded */}
        <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-6 space-y-2">
          <span className="text-xs font-mono uppercase tracking-wider text-slate-400">
            Total Points Awarded
          </span>
          <div className="text-3xl font-black text-cyan-400 font-mono">{points.total_awarded}</div>
          <p className="text-xs text-slate-500 font-mono">
            +{points.points_past_hour} in the past hour
          </p>
        </div>

        {/* Velocity / Rates */}
        <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-6 space-y-2">
          <span className="text-xs font-mono uppercase tracking-wider text-slate-400">
            Merge Velocity
          </span>
          <div className="text-3xl font-black text-emerald-400 font-mono">
            {rates.merges_past_hour}
            <span className="text-xs text-slate-500 font-normal ml-1">/hr</span>
          </div>
          <p className="text-xs text-slate-500 font-mono">
            {rates.points_past_hour} pts awarded/hour
          </p>
        </div>
      </div>

      {/* Contribution Status Pipeline */}
      <div className="bg-slate-900/50 border border-slate-800 rounded-3xl p-6 sm:p-8 space-y-6" data-testid="stats-pipeline-section">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
          <div>
            <h2 className="text-xl font-bold text-white">Contribution State Breakdown</h2>
            <p className="text-xs text-slate-400">
              Total {contributions.total} tracked contributions across all pipeline phases.
            </p>
          </div>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-4">
          {statusList.map((st) => (
            <div
              key={st.key}
              className="bg-slate-950/60 border border-slate-800/80 rounded-2xl p-4 space-y-1.5"
              data-testid={`status-count-${st.key}`}
            >
              <span className="text-xs font-mono text-slate-400">{st.label}</span>
              <p className={`text-2xl font-black font-mono ${st.color}`}>{st.count}</p>
            </div>
          ))}
        </div>
      </div>

      {/* System Status Indicators */}
      <div className="bg-slate-900/50 border border-slate-800 rounded-3xl p-6 sm:p-8 space-y-4" data-testid="stats-system-status">
        <h2 className="text-xl font-bold text-white">System Runtime Controls</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="bg-slate-950/60 border border-slate-800 rounded-2xl p-4 flex items-center justify-between">
            <span className="text-xs font-medium text-slate-300">Merge Queue</span>
            <span
              className={`px-2 py-0.5 rounded text-xs font-mono font-semibold ${
                system_status.merge_paused
                  ? 'bg-amber-950 text-amber-400 border border-amber-800'
                  : 'bg-emerald-950 text-emerald-400 border border-emerald-800'
              }`}
            >
              {system_status.merge_paused ? 'Paused' : 'Active'}
            </span>
          </div>

          <div className="bg-slate-950/60 border border-slate-800 rounded-2xl p-4 flex items-center justify-between">
            <span className="text-xs font-medium text-slate-300">Submissions</span>
            <span
              className={`px-2 py-0.5 rounded text-xs font-mono font-semibold ${
                system_status.submissions_paused
                  ? 'bg-amber-950 text-amber-400 border border-amber-800'
                  : 'bg-emerald-950 text-emerald-400 border border-emerald-800'
              }`}
            >
              {system_status.submissions_paused ? 'Paused' : 'Active'}
            </span>
          </div>

          <div className="bg-slate-950/60 border border-slate-800 rounded-2xl p-4 flex items-center justify-between">
            <span className="text-xs font-medium text-slate-300">Validation Pipeline</span>
            <span
              className={`px-2 py-0.5 rounded text-xs font-mono font-semibold ${
                system_status.validation_paused
                  ? 'bg-amber-950 text-amber-400 border border-amber-800'
                  : 'bg-emerald-950 text-emerald-400 border border-emerald-800'
              }`}
            >
              {system_status.validation_paused ? 'Paused' : 'Active'}
            </span>
          </div>

          <div className="bg-slate-950/60 border border-slate-800 rounded-2xl p-4 flex items-center justify-between">
            <span className="text-xs font-medium text-slate-300">Leaderboard</span>
            <span
              className={`px-2 py-0.5 rounded text-xs font-mono font-semibold ${
                system_status.leaderboard_frozen
                  ? 'bg-cyan-950 text-cyan-300 border border-cyan-800'
                  : 'bg-emerald-950 text-emerald-400 border border-emerald-800'
              }`}
            >
              {system_status.leaderboard_frozen ? 'Frozen' : 'Live'}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
