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
            className="text-xs font-mono text-[#777777] hover:text-[#111111] transition-colors inline-flex items-center gap-1 mb-2"
          >
            ← Back to Leaderboard
          </Link>
          <h1 className="text-3xl font-bold text-[#111111] tracking-tight">Contributor Profile</h1>
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
          className="text-xs font-mono text-[#777777] hover:text-[#111111] transition-colors inline-flex items-center gap-1 mb-2"
        >
          ← Back to Leaderboard
        </Link>
        {is404 ? (
          <div
            className="bg-white border border-[#d8d8d3] rounded-md p-10 text-center max-w-md mx-auto my-8 shadow-sm"
            data-testid="profile-not-found"
          >
            <div className="w-14 h-14 rounded-md bg-[#f4f4f1] border border-[#d8d8d3] flex items-center justify-center mx-auto mb-4 text-2xl">
              👤
            </div>
            <h2 className="text-xl font-bold text-[#111111] mb-2">Contributor Not Found</h2>
            <p className="text-sm text-[#555555] mb-6">
              The contributor <span className="font-mono text-[#ff5a1f] font-semibold">@{username}</span> was not found or is currently suspended.
            </p>
            <Link
              to="/leaderboard"
              className="inline-flex items-center px-5 py-2.5 rounded-[4px] bg-[#050505] hover:bg-[#222222] text-xs font-mono font-medium text-white transition-colors"
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
        className="text-xs font-mono text-[#777777] hover:text-[#111111] transition-colors inline-flex items-center gap-1 focus:outline-none focus-visible:ring-2 focus-visible:ring-[#ff5a1f] rounded-sm"
      >
        ← Back to Leaderboard
      </Link>

      {/* Header Contributor Card */}
      <div className="bg-white border border-[#d8d8d3] rounded-md p-6 sm:p-8 shadow-sm flex flex-col sm:flex-row items-center sm:items-start justify-between gap-6 relative overflow-hidden">
        <div className="flex flex-col sm:flex-row items-center gap-5 text-center sm:text-left relative min-w-0">
          {avatar_url ? (
            <img
              src={avatar_url}
              alt={github_username}
              width="80"
              height="80"
              loading="eager"
              decoding="async"
              className="w-20 h-20 rounded-md border border-[#d8d8d3] bg-[#f4f4f1] object-cover shadow-sm shrink-0"
            />
          ) : (
            <div className="w-20 h-20 rounded-md border border-[#d8d8d3] bg-[#f4f4f1] flex items-center justify-center font-bold text-2xl text-[#111111] shadow-sm shrink-0">
              {github_username.charAt(0).toUpperCase()}
            </div>
          )}

          <div className="space-y-1.5 min-w-0">
            <h1 className="text-2xl sm:text-3xl font-bold text-[#111111] tracking-tight truncate max-w-[220px] sm:max-w-sm">
              {github_username}
            </h1>
            <a
              href={`https://github.com/${github_username}`}
              target="_blank"
              rel="noopener noreferrer"
              className="text-xs text-[#777777] hover:text-[#ff5a1f] font-mono inline-flex items-center gap-1 transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-[#ff5a1f] rounded-sm"
            >
              github.com/{github_username} ↗
            </a>
          </div>
        </div>

        {/* Highlight Stats */}
        <div className="flex items-center gap-2.5 sm:gap-3 w-full sm:w-auto justify-center sm:justify-end relative shrink-0">
          <div className="bg-[#f4f4f1] border border-[#d8d8d3] rounded-[4px] p-3 sm:p-3.5 text-center min-w-0 sm:min-w-[100px] flex-1 sm:flex-initial">
            <span className="text-[10px] uppercase font-mono tracking-wider text-[#777777] block mb-1">
              Global Rank
            </span>
            <span className="text-xl font-bold text-[#111111] font-mono tabular-nums">
              {rank ? `#${rank}` : '-'}
            </span>
          </div>

          <div className="bg-[#f4f4f1] border border-[#d8d8d3] rounded-[4px] p-3 sm:p-3.5 text-center min-w-0 sm:min-w-[100px] flex-1 sm:flex-initial">
            <span className="text-[10px] uppercase font-mono tracking-wider text-[#777777] block mb-1">
              Total Points
            </span>
            <span className="text-xl font-bold text-[#ff5a1f] font-mono tabular-nums">
              {total_points}
            </span>
          </div>

          <div className="bg-[#f4f4f1] border border-[#d8d8d3] rounded-[4px] p-3 sm:p-3.5 text-center min-w-0 sm:min-w-[100px] flex-1 sm:flex-initial">
            <span className="text-[10px] uppercase font-mono tracking-wider text-[#777777] block mb-1">
              Merged PRs
            </span>
            <span className="text-xl font-bold text-[#111111] font-mono tabular-nums">
              {merged_count}
            </span>
          </div>
        </div>
      </div>

      {/* Aggregate Stats Grid */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4" data-testid="profile-stats-grid">
        <div className="bg-white border border-[#d8d8d3] rounded-md p-5 space-y-1 shadow-sm">
          <span className="text-xs text-[#777777] font-mono uppercase tracking-wider">Total Submissions</span>
          <p className="text-2xl font-bold text-[#111111] font-mono tabular-nums">{stats.total_contributions}</p>
        </div>

        <div className="bg-white border border-[#d8d8d3] rounded-md p-5 space-y-1 shadow-sm">
          <span className="text-xs text-[#777777] font-mono uppercase tracking-wider">Merged PRs</span>
          <p className="text-2xl font-bold text-[#111111] font-mono tabular-nums">{stats.merged_contributions}</p>
        </div>

        <div className="bg-white border border-[#d8d8d3] rounded-md p-5 space-y-1 shadow-sm">
          <span className="text-xs text-[#777777] font-mono uppercase tracking-wider">In-Progress</span>
          <p className="text-2xl font-bold text-[#555555] font-mono tabular-nums">{stats.in_progress_contributions}</p>
        </div>

        <div className="bg-white border border-[#d8d8d3] rounded-md p-5 space-y-1 shadow-sm">
          <span className="text-xs text-[#777777] font-mono uppercase tracking-wider">Rejected</span>
          <p className="text-2xl font-bold text-[#777777] font-mono tabular-nums">{stats.rejected_contributions}</p>
        </div>
      </div>

      {/* Recent Merged Contributions */}
      <div className="space-y-4" data-testid="profile-merged-contributions">
        <h2 className="text-xl font-bold text-[#111111]">Recent Merged Contributions</h2>

        {(recent_merged_contributions || []).length === 0 ? (
          <div className="bg-white border border-[#d8d8d3] rounded-md p-8 text-center text-[#777777] text-sm shadow-sm">
            No merged contributions recorded yet.
          </div>
        ) : (
          <div className="bg-white border border-[#d8d8d3] rounded-md divide-y divide-[#d8d8d3] overflow-hidden shadow-sm">
            {recent_merged_contributions.map((c) => (
              <div
                key={c.id}
                className="p-5 flex flex-col sm:flex-row sm:items-center justify-between gap-3 hover:bg-[#f4f4f1]/60 transition-colors"
              >
                <div className="space-y-1 flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-xs font-mono text-[#ff5a1f] truncate max-w-[200px]">{c.project_name}</span>
                    <span className="text-[#d8d8d3]">•</span>
                    <span className="text-xs font-mono text-[#777777] shrink-0">Issue #{c.issue_number}</span>
                  </div>
                  <h3 className="font-semibold text-[#111111] text-sm font-sans break-words">{c.issue_title}</h3>
                </div>

                <div className="flex items-center gap-4 shrink-0 justify-between sm:justify-end">
                  <span className="text-sm font-mono font-bold text-[#111111] tabular-nums">
                    +{c.points} pts
                  </span>
                  {c.github_url && (
                    <a
                      href={c.github_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-xs text-[#777777] hover:text-[#111111] font-mono underline transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-[#ff5a1f] rounded-sm"
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
