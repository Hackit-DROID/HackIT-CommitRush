import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useLeaderboard } from '../api/leaderboard';
import { EmptyState } from '../components/EmptyState';
import { ErrorState } from '../components/ErrorState';
import { LeaderboardSkeleton } from '../components/Skeletons';
import { useDocumentTitle } from '../hooks/useDocumentTitle';

export function LeaderboardPage() {
  useDocumentTitle(
    'CommitRush 2026 — Leaderboard',
    'Real-time standings of open source contributors across all tracked repositories.'
  );

  const [page, setPage] = useState(1);
  const pageSize = 50;

  const { data, isLoading, isError, error, refetch, isFetching } = useLeaderboard({
    page,
    page_size: pageSize,
    include_me: true,
  });

  const handlePrevPage = () => {
    if (page > 1) {
      setPage((p) => p - 1);
      window.scrollTo({ top: 0, behavior: 'smooth' });
    }
  };

  const handleNextPage = () => {
    if (data && page < data.num_pages) {
      setPage((p) => p + 1);
      window.scrollTo({ top: 0, behavior: 'smooth' });
    }
  };

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div className="space-y-1">
          <h1 className="text-3xl font-display font-bold text-[#111111] tracking-tight">Leaderboard</h1>
          <p className="text-[#555555] text-sm">Real-time standings of open source contributors across all tracked repositories.</p>
        </div>
        <LeaderboardSkeleton />
      </div>
    );
  }

  if (isError) {
    return (
      <div className="space-y-6">
        <div className="space-y-1">
          <h1 className="text-3xl font-display font-bold text-[#111111] tracking-tight">Leaderboard</h1>
          <p className="text-[#555555] text-sm">Real-time standings of open source contributors across all tracked repositories.</p>
        </div>
        <ErrorState error={error} onRetry={() => refetch()} />
      </div>
    );
  }

  const results = data?.results || [];
  const me = data?.me;
  const isFrozen = Boolean(data?.frozen);

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-[#d8d8d3] pb-6">
        <div className="space-y-1">
          <div className="flex items-center gap-3">
            <h1 className="text-3xl font-display font-bold text-[#111111] tracking-tight">Leaderboard</h1>
            {isFrozen && (
              <span
                data-testid="frozen-badge"
                className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-mono font-medium bg-[#f4f4f1] border border-[#d8d8d3] text-[#111111]"
              >
                ❄️ Frozen Standings
              </span>
            )}
            {isFetching && !isLoading && (
              <span className="text-xs text-[#777777] animate-pulse font-mono">
                Refreshing...
              </span>
            )}
          </div>
          <p className="text-[#555555] text-sm">
            {isFrozen
              ? 'Leaderboard is currently frozen. Standings are locked.'
              : 'Rankings calculated deterministically: Total Points → Merged Count → User ID.'}
          </p>
        </div>

        <div className="text-xs text-[#555555] bg-white border border-[#d8d8d3] px-4 py-2 rounded-full self-start md:self-auto font-mono shadow-sm">
          Total Participants: <span className="text-[#ff5a1f] font-bold">{data?.count || 0}</span>
        </div>
      </div>

      {/* Leaderboard Freeze Notice */}
      {isFrozen && (
        <div
          data-testid="frozen-notice"
          className="bg-white border border-[#d8d8d3] rounded-md p-5 flex items-start gap-3.5 text-[#111111] shadow-sm"
        >
          <div className="w-8 h-8 rounded-full bg-[#f4f4f1] border border-[#d8d8d3] flex items-center justify-center shrink-0 text-sm">
            ❄️
          </div>
          <div className="space-y-0.5 text-sm">
            <h2 className="font-display font-bold text-[#111111]">Event Leaderboard Frozen</h2>
            <p className="text-[#555555] leading-relaxed text-xs sm:text-sm">
              Public rankings are frozen. Background merges and point awards continue to be processed and verified in the database, but standings are snapshot.
            </p>
          </div>
        </div>
      )}

      {/* Authenticated Requester Standing (if available) */}
      {me && (
        <div
          data-testid="me-rank-card"
          className="bg-white border border-[#d8d8d3] rounded-md p-5 sm:p-6 shadow-sm flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4"
        >
          <div className="flex items-center gap-3.5 min-w-0">
            {me.avatar_url ? (
              <img
                src={me.avatar_url}
                alt={me.github_username}
                width="48"
                height="48"
                loading="lazy"
                decoding="async"
                className="w-12 h-12 rounded-full border border-[#d8d8d3] bg-[#f4f4f1] object-cover shrink-0"
              />
            ) : (
              <div className="w-12 h-12 rounded-full border border-[#d8d8d3] bg-[#f4f4f1] flex items-center justify-center font-bold text-[#111111] shrink-0">
                {me.github_username.charAt(0).toUpperCase()}
              </div>
            )}
            <div className="min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="font-bold text-[#111111] text-base truncate max-w-[180px] sm:max-w-xs">{me.github_username}</span>
                <span className="px-2 py-0.5 rounded-full text-[10px] font-mono uppercase bg-orange-50 text-[#ff5a1f] border border-orange-200 font-semibold shrink-0">
                  You
                </span>
              </div>
              <p className="text-xs text-[#555555]">
                {me.rank ? `Currently ranked #${me.rank}` : 'Not yet ranked'}
              </p>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-4 sm:gap-6 w-full sm:w-auto justify-between sm:justify-end border-t sm:border-t-0 border-[#d8d8d3] pt-3 sm:pt-0 font-mono">
            <div className="text-center sm:text-right">
              <span className="text-[10px] uppercase tracking-wider text-[#777777] block">Merged PRs</span>
              <span className="text-sm font-bold text-[#111111] tabular-nums">{me.merged_count}</span>
            </div>
            <div className="text-center sm:text-right">
              <span className="text-[10px] uppercase tracking-wider text-[#777777] block">Today / Limit</span>
              <span className="text-sm font-bold text-[#111111] tabular-nums">
                {me.points_today ?? 0} / {me.daily_limit ?? 120}
              </span>
            </div>
            <div className="text-center sm:text-right">
              <span className="text-[10px] uppercase tracking-wider text-[#777777] block">Remaining</span>
              <span className="text-sm font-bold text-emerald-700 tabular-nums">
                {me.remaining_daily_allowance ?? 120} pts
              </span>
            </div>
            <div className="text-center sm:text-right">
              <span className="text-[10px] uppercase tracking-wider text-[#777777] block">Total Points</span>
              <span className="text-lg font-black text-[#ff5a1f] tabular-nums">{me.total_points}</span>
            </div>
            <div className="text-center sm:text-right">
              <span className="text-[10px] uppercase tracking-wider text-[#777777] block">Rank</span>
              <span className="text-lg font-black text-[#111111] tabular-nums">#{me.rank || '-'}</span>
            </div>
          </div>
        </div>
      )}

      {/* Leaderboard Table */}
      {results.length === 0 ? (
        <EmptyState
          title="No Ranked Contributors Yet"
          message="Contributions are being processed. As pull requests get merged, standings will appear here."
        />
      ) : (
        <div className="bg-white border border-[#d8d8d3] rounded-md overflow-hidden shadow-sm">
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse" data-testid="leaderboard-table">
              <thead>
                <tr className="border-b border-[#d8d8d3] bg-[#f4f4f1] text-[11px] font-mono uppercase tracking-wider text-[#555555]">
                  <th scope="col" className="py-3.5 px-4 sm:px-6 w-16 sm:w-20 text-center">Rank</th>
                  <th scope="col" className="py-3.5 px-4 sm:px-6">Contributor</th>
                  <th scope="col" className="py-3.5 px-4 sm:px-6 text-center">Contributions</th>
                  <th scope="col" className="py-3.5 px-4 sm:px-6 text-center">Daily Allowance</th>
                  <th scope="col" className="py-3.5 px-4 sm:px-6 text-right">Total Points</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#d8d8d3] text-sm">
                {results.map((entry) => {
                  const isTop1 = entry.rank === 1;
                  const isTop2 = entry.rank === 2;
                  const isTop3 = entry.rank === 3;
                  const isMe = me && me.participant_id === entry.participant_id;
                  const isCapped = Boolean(
                    entry.is_daily_limit_reached ||
                    (entry.remaining_daily_allowance !== undefined && entry.remaining_daily_allowance <= 0)
                  );

                  return (
                    <tr
                      key={entry.participant_id}
                      className={`transition-colors hover:bg-[#fafaf8] ${
                        isMe ? 'bg-[#f4f4f1]/60' : ''
                      }`}
                      data-testid={`leaderboard-row-${entry.rank}`}
                    >
                      {/* Rank */}
                      <td className="py-4 px-4 sm:px-6 text-center font-bold font-mono">
                        {isTop1 && <span className="text-[#ff5a1f] text-sm font-extrabold tabular-nums">#1</span>}
                        {isTop2 && <span className="text-[#111111] text-sm font-bold tabular-nums">#2</span>}
                        {isTop3 && <span className="text-[#555555] text-sm font-bold tabular-nums">#3</span>}
                        {!isTop1 && !isTop2 && !isTop3 && (
                          <span className="text-[#777777] text-xs tabular-nums">#{entry.rank}</span>
                        )}
                      </td>

                      {/* Contributor Profile */}
                      <td className="py-4 px-4 sm:px-6">
                        <div className="flex items-center gap-3 min-w-0">
                          {entry.avatar_url ? (
                            <img
                              src={entry.avatar_url}
                              alt={entry.github_username}
                              width="36"
                              height="36"
                              loading="lazy"
                              decoding="async"
                              className="w-9 h-9 rounded-full border border-[#d8d8d3] bg-[#f4f4f1] object-cover shrink-0"
                            />
                          ) : (
                            <div className="w-9 h-9 rounded-full border border-[#d8d8d3] bg-[#f4f4f1] flex items-center justify-center font-bold text-xs text-[#111111] shrink-0">
                              {entry.github_username.charAt(0).toUpperCase()}
                            </div>
                          )}
                          <div className="flex flex-col min-w-0">
                            <Link
                              to={`/profile/${entry.github_username}`}
                              className="font-semibold text-[#111111] hover:text-[#ff5a1f] transition-colors inline-flex items-center gap-1.5 focus:outline-none focus-visible:ring-2 focus-visible:ring-[#ff5a1f] rounded-sm min-w-0"
                            >
                              <span className="truncate max-w-[130px] sm:max-w-[200px] md:max-w-xs">{entry.github_username}</span>
                              {isMe && (
                                <span className="px-1.5 py-0.2 rounded text-[9px] font-mono uppercase bg-orange-50 text-[#ff5a1f] border border-orange-200 shrink-0">
                                  you
                                </span>
                              )}
                            </Link>
                          </div>
                        </div>
                      </td>

                      {/* Contributions */}
                      <td className="py-4 px-4 sm:px-6 text-center font-mono text-[#555555] font-medium tabular-nums">
                        {entry.merged_count}
                      </td>

                      {/* Daily Allowance & Limits */}
                      <td className="py-4 px-4 sm:px-6 text-center font-mono text-xs">
                        <div className="flex flex-col items-center gap-1">
                          <div className="flex items-center gap-1.5 text-[#111111]">
                            <span className="font-semibold tabular-nums">{entry.points_today ?? 0}</span>
                            <span className="text-[#777777]">/ {entry.daily_limit ?? 120} today</span>
                          </div>
                          <div className="flex items-center gap-1.5">
                            <span className={`text-[11px] tabular-nums ${entry.remaining_daily_allowance === 0 ? 'text-amber-800 font-semibold' : 'text-[#777777]'}`}>
                              {entry.remaining_daily_allowance ?? 120} remaining
                            </span>
                            {isCapped && (
                              <span
                                data-testid="daily-limit-indicator"
                                className="px-1.5 py-0.2 rounded text-[9px] font-mono font-semibold bg-amber-100 text-amber-900 border border-amber-300"
                                title="Daily limit reached"
                              >
                                Capped
                              </span>
                            )}
                          </div>
                        </div>
                      </td>

                      {/* Points */}
                      <td className="py-4 px-4 sm:px-6 text-right font-mono">
                        <span className="font-extrabold text-[#ff5a1f] text-base tabular-nums">
                          {entry.total_points}
                        </span>
                        <span className="text-xs text-[#777777] ml-1">pts</span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {/* Server-Side Pagination */}
          {data && data.num_pages > 1 && (
            <div
              className="border-t border-[#d8d8d3] bg-white px-4 sm:px-6 py-4 flex items-center justify-between gap-4"
              data-testid="pagination-controls"
            >
              <div className="text-xs text-[#555555] font-mono">
                Page <span className="text-[#111111] font-bold">{data.page}</span> of{' '}
                <span className="text-[#111111] font-bold">{data.num_pages}</span>
              </div>

              <div className="flex items-center gap-2">
                <button
                  onClick={handlePrevPage}
                  disabled={page <= 1}
                  type="button"
                  data-testid="prev-page-button"
                  className="px-4 py-1.5 rounded-[4px] bg-white hover:bg-[#f4f4f1] text-xs font-medium text-[#111111] border border-[#d8d8d3] disabled:opacity-40 disabled:cursor-not-allowed transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-[#ff5a1f]"
                >
                  Previous
                </button>
                <button
                  onClick={handleNextPage}
                  disabled={page >= data.num_pages}
                  type="button"
                  data-testid="next-page-button"
                  className="px-4 py-1.5 rounded-[4px] bg-white hover:bg-[#f4f4f1] text-xs font-medium text-[#111111] border border-[#d8d8d3] disabled:opacity-40 disabled:cursor-not-allowed transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-[#ff5a1f]"
                >
                  Next
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
