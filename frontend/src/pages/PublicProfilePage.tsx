import { useParams, Link } from 'react-router-dom';
import { usePublicProfile } from '../api/profile';
import { ApiError } from '../types/api';
import { ErrorState } from '../components/ErrorState';
import { ProfileSkeleton } from '../components/Skeletons';
import { useDocumentTitle } from '../hooks/useDocumentTitle';

export function PublicProfilePage() {
  const { username } = useParams<{ username: string }>();
  const { data, isLoading, isError, error, refetch } = usePublicProfile(username);

  useDocumentTitle(
    username ? `CommitRush — @${username}'s Profile` : 'CommitRush — Contributor Profile',
    'Public contributor profile, merged pull requests, and rank standings on CommitRush.'
  );

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div className="space-y-2">
          <Link
            to="/leaderboard"
            className="text-xs text-slate-400 hover:text-white transition-colors inline-flex items-center gap-1 mb-2"
          >
            ← Back to Leaderboard
          </Link>
          <h1 className="text-3xl font-extrabold text-white tracking-tight">Contributor Profile</h1>
        </div>
        <ProfileSkeleton />
      </div>
    );
  }

  if (isError) {
    const is404 = error instanceof ApiError && error.isNotFound;
    return (
      <div className="space-y-6">
        <Link
          to="/leaderboard"
          className="text-xs text-slate-400 hover:text-white transition-colors inline-flex items-center gap-1 mb-2"
        >
          ← Back to Leaderboard
        </Link>
        {is404 ? (
          <div
            className="bg-slate-900/60 border border-slate-800 rounded-3xl p-10 text-center max-w-md mx-auto my-8 shadow-xl"
            data-testid="profile-not-found"
          >
            <div className="w-14 h-14 rounded-2xl bg-slate-800 border border-slate-700/60 flex items-center justify-center mx-auto mb-4 text-2xl">
              👤
            </div>
            <h2 className="text-xl font-bold text-white mb-2">Contributor Not Found</h2>
            <p className="text-sm text-slate-400 mb-6">
              The contributor <span className="font-mono text-cyan-400 font-semibold">@{username}</span> was not found or is currently suspended.
            </p>
            <Link
              to="/leaderboard"
              className="inline-flex items-center px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-sm font-medium text-cyan-400 border border-slate-700 transition-colors"
            >
              Browse Leaderboard
            </Link>
          </div>
        ) : (
          <ErrorState error={error} onRetry={() => refetch()} />
        )}
      </div>
    );
  }

  if (!data) return null;

  const { github_username, avatar_url, total_points, merged_count, rank, stats, recent_merged_contributions } = data;

  return (
    <div className="space-y-8 max-w-4xl mx-auto" data-testid="profile-page">
      {/* Back Link */}
      <Link
        to="/leaderboard"
        className="text-xs text-slate-400 hover:text-white transition-colors inline-flex items-center gap-1"
      >
        ← Back to Leaderboard
      </Link>

      {/* Header Contributor Card */}
      <div className="bg-gradient-to-r from-slate-900 via-slate-900 to-indigo-950/40 border border-slate-800 rounded-3xl p-6 sm:p-8 shadow-xl flex flex-col sm:flex-row items-center sm:items-start justify-between gap-6">
        <div className="flex flex-col sm:flex-row items-center gap-5 text-center sm:text-left">
          {avatar_url ? (
            <img
              src={avatar_url}
              alt={github_username}
              width="80"
              height="80"
              loading="eager"
              decoding="async"
              className="w-20 h-20 rounded-full border-2 border-indigo-500/60 bg-slate-800 object-cover shadow-lg shadow-indigo-950/40"
            />
          ) : (
            <div className="w-20 h-20 rounded-2xl border-2 border-indigo-500/60 bg-slate-800 flex items-center justify-center font-black text-2xl text-white shadow-lg">
              {github_username.charAt(0).toUpperCase()}
            </div>
          )}

          <div className="space-y-1.5">
            <h1 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight">
              {github_username}
            </h1>
            <a
              href={`https://github.com/${github_username}`}
              target="_blank"
              rel="noopener noreferrer"
              className="text-xs text-indigo-400 hover:text-indigo-300 font-mono inline-flex items-center gap-1 transition-colors"
            >
              github.com/{github_username} ↗
            </a>
          </div>
        </div>

        {/* Highlight Stats */}
        <div className="flex items-center gap-2.5 sm:gap-3 w-full sm:w-auto justify-center sm:justify-end">
          <div className="bg-slate-950/80 border border-slate-800/80 rounded-2xl p-3 sm:p-3.5 text-center min-w-0 sm:min-w-[100px] flex-1 sm:flex-initial">
            <span className="text-[10px] uppercase font-mono tracking-wider text-slate-500 block mb-1">
              Global Rank
            </span>
            <span className="text-xl font-black text-indigo-400">
              {rank ? `#${rank}` : '-'}
            </span>
          </div>

          <div className="bg-slate-950/80 border border-slate-800/80 rounded-2xl p-3 sm:p-3.5 text-center min-w-0 sm:min-w-[100px] flex-1 sm:flex-initial">
            <span className="text-[10px] uppercase font-mono tracking-wider text-slate-500 block mb-1">
              Total Points
            </span>
            <span className="text-xl font-black text-cyan-400">
              {total_points}
            </span>
          </div>

          <div className="bg-slate-950/80 border border-slate-800/80 rounded-2xl p-3 sm:p-3.5 text-center min-w-0 sm:min-w-[100px] flex-1 sm:flex-initial">
            <span className="text-[10px] uppercase font-mono tracking-wider text-slate-500 block mb-1">
              Merged PRs
            </span>
            <span className="text-xl font-black text-emerald-400">
              {merged_count}
            </span>
          </div>
        </div>
      </div>

      {/* Aggregate Stats Grid */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4" data-testid="profile-stats-grid">
        <div className="bg-slate-900/50 border border-slate-800 rounded-2xl p-5 space-y-1">
          <span className="text-xs text-slate-400">Total Submissions</span>
          <p className="text-2xl font-black text-white font-mono">{stats.total_contributions}</p>
        </div>

        <div className="bg-slate-900/50 border border-slate-800 rounded-2xl p-5 space-y-1">
          <span className="text-xs text-slate-400">Merged PRs</span>
          <p className="text-2xl font-black text-emerald-400 font-mono">{stats.merged_contributions}</p>
        </div>

        <div className="bg-slate-900/50 border border-slate-800 rounded-2xl p-5 space-y-1">
          <span className="text-xs text-slate-400">In-Progress</span>
          <p className="text-2xl font-black text-amber-400 font-mono">{stats.in_progress_contributions}</p>
        </div>

        <div className="bg-slate-900/50 border border-slate-800 rounded-2xl p-5 space-y-1">
          <span className="text-xs text-slate-400">Rejected</span>
          <p className="text-2xl font-black text-slate-400 font-mono">{stats.rejected_contributions}</p>
        </div>
      </div>

      {/* Recent Merged Contributions */}
      <div className="space-y-4" data-testid="profile-merged-contributions">
        <h2 className="text-xl font-bold text-white">Recent Merged Contributions</h2>

        {(recent_merged_contributions || []).length === 0 ? (
          <div className="bg-slate-900/30 border border-slate-800/60 rounded-2xl p-8 text-center text-slate-400 text-sm">
            No merged contributions recorded yet.
          </div>
        ) : (
          <div className="bg-slate-900/50 border border-slate-800 rounded-2xl divide-y divide-slate-800/60 overflow-hidden">
            {recent_merged_contributions.map((c) => (
              <div
                key={c.id}
                className="p-5 flex flex-col sm:flex-row sm:items-center justify-between gap-3 hover:bg-slate-800/30 transition-colors"
              >
                <div className="space-y-1 flex-1">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-mono text-slate-400">{c.project_name}</span>
                    <span className="text-slate-600">•</span>
                    <span className="text-xs font-mono text-cyan-400">Issue #{c.issue_number}</span>
                  </div>
                  <h3 className="font-semibold text-white text-sm">{c.issue_title}</h3>
                </div>

                <div className="flex items-center gap-4 shrink-0 justify-between sm:justify-end">
                  <span className="text-sm font-mono font-bold text-emerald-400">
                    +{c.points} pts
                  </span>
                  {c.github_url && (
                    <a
                      href={c.github_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-xs text-slate-400 hover:text-white underline transition-colors"
                    >
                      PR on GitHub ↗
                    </a>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
