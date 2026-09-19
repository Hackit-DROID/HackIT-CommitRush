import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useLeaderboard } from '../api/leaderboard';
import { EmptyState } from '../components/EmptyState';
import { ErrorState } from '../components/ErrorState';
import { LeaderboardSkeleton } from '../components/Skeletons';
import { useDocumentTitle } from '../hooks/useDocumentTitle';

export function LeaderboardPage() {
  useDocumentTitle(
    'CommitRush — Leaderboard',
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
        <div className="space-y-2">
          <h1 className="text-3xl font-extrabold text-white tracking-tight">Leaderboard</h1>
          <p className="text-slate-400 text-sm">Real-time standings of open source contributors across all tracked repositories.</p>
        </div>
        <LeaderboardSkeleton />
      </div>
    );
  }

  if (isError) {
    return (
      <div className="space-y-6">
        <div className="space-y-2">
          <h1 className="text-3xl font-extrabold text-white tracking-tight">Leaderboard</h1>
          <p className="text-slate-400 text-sm">Real-time standings of open source contributors across all tracked repositories.</p>
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
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="space-y-1">
          <div className="flex items-center gap-3">
            <h1 className="text-3xl font-extrabold text-white tracking-tight">Leaderboard</h1>
            {isFrozen && (
              <span
                data-testid="frozen-badge"
                className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-cyan-950/80 border border-cyan-800 text-cyan-300 shadow-sm"
              >
                ❄️ Frozen Standings
              </span>
            )}
            {isFetching && !isLoading && (
              <span className="text-xs text-slate-500 animate-pulse font-mono">
                Refreshing...
              </span>
            )}
          </div>
          <p className="text-slate-400 text-sm">
            {isFrozen
              ? 'Leaderboard is currently frozen. Standings are locked.'
              : 'Rankings calculated deterministically: Total Points → Merged Count → User ID.'}
          </p>
        </div>

        <div className="text-xs text-slate-400 bg-slate-900/60 border border-slate-800 px-3.5 py-2 rounded-xl self-start md:self-auto font-mono">
          Total Participants: <span className="text-cyan-400 font-bold">{data?.count || 0}</span>
        </div>
      </div>

      {/* Leaderboard Freeze Notice */}
      {isFrozen && (
        <div
          data-testid="frozen-notice"
          className="bg-cyan-950/40 border border-cyan-800/60 rounded-2xl p-4 sm:p-5 flex items-start gap-3.5 text-cyan-200"
        >
          <div className="w-8 h-8 rounded-lg bg-cyan-900/80 border border-cyan-700/60 flex items-center justify-center shrink-0 text-cyan-300 font-bold">
            ❄️
          </div>
          <div className="space-y-0.5 text-sm">
            <h2 className="font-semibold text-white">Event Leaderboard Frozen</h2>
            <p className="text-cyan-300/80 leading-relaxed">
              Public rankings are frozen. Background merges and point awards continue to be processed and verified in the database, but standings are snapshot.
            </p>
          </div>
        </div>
      )}

      {/* Authenticated Requester Standing (if available) */}
      {me && (
        <div
          data-testid="me-rank-card"
          className="bg-gradient-to-r from-slate-900 via-slate-900 to-indigo-950/40 border border-indigo-900/40 rounded-2xl p-5 shadow-lg shadow-indigo-950/10 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4"
        >
          <div className="flex items-center gap-3.5">
            {me.avatar_url ? (
              <img
                src={me.avatar_url}
                alt={me.github_username}
                width="48"
                height="48"
                loading="lazy"
                decoding="async"
                className="w-12 h-12 rounded-full border-2 border-indigo-500/60 bg-slate-800 object-cover"
              />
            ) : (
              <div className="w-12 h-12 rounded-full border-2 border-indigo-500/60 bg-slate-800 flex items-center justify-center font-bold text-white">
                {me.github_username.charAt(0).toUpperCase()}
              </div>
            )}
            <div>
              <div className="flex items-center gap-2">
                <span className="font-bold text-white text-base">{me.github_username}</span>
                <span className="px-2 py-0.5 rounded text-[10px] font-semibold tracking-wide uppercase bg-indigo-900/80 text-indigo-300 border border-indigo-700/50">
                  You
                </span>
              </div>
              <p className="text-xs text-slate-400">
                {me.rank ? `Currently ranked #${me.rank}` : 'Not yet ranked'}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-6 w-full sm:w-auto justify-between sm:justify-end border-t sm:border-t-0 border-slate-800/80 pt-3 sm:pt-0">
            <div className="text-center sm:text-right">
              <span className="text-[10px] uppercase font-mono tracking-wider text-slate-500 block">Merged PRs</span>
              <span className="text-sm font-bold text-slate-200">{me.merged_count}</span>
            </div>
            <div className="text-center sm:text-right">
              <span className="text-[10px] uppercase font-mono tracking-wider text-slate-500 block">Total Points</span>
              <span className="text-lg font-black text-cyan-400">{me.total_points}</span>
            </div>
            <div className="text-center sm:text-right">
              <span className="text-[10px] uppercase font-mono tracking-wider text-slate-500 block">Rank</span>
              <span className="text-lg font-black text-indigo-400">#{me.rank || '-'}</span>
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
        <div className="bg-slate-900/50 border border-slate-800 rounded-2xl overflow-hidden shadow-xl shadow-slate-950/40">
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse" data-testid="leaderboard-table">
              <thead>
                <tr className="border-b border-slate-800 bg-slate-900/90 text-[11px] font-mono uppercase tracking-wider text-slate-400">
                  <th scope="col" className="py-3.5 px-4 sm:px-6 w-16 sm:w-20 text-center">Rank</th>
                  <th scope="col" className="py-3.5 px-4 sm:px-6">Contributor</th>
                  <th scope="col" className="py-3.5 px-4 sm:px-6 text-center">Merged PRs</th>
                  <th scope="col" className="py-3.5 px-4 sm:px-6 text-right">Points</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60 text-sm">
                {results.map((entry) => {
                  const isTop1 = entry.rank === 1;
                  const isTop2 = entry.rank === 2;
                  const isTop3 = entry.rank === 3;
                  const isMe = me && me.participant_id === entry.participant_id;

                  return (
                    <tr
                      key={entry.participant_id}
                      className={`transition-colors hover:bg-slate-800/40 ${
                        isMe ? 'bg-indigo-950/20' : ''
                      }`}
                      data-testid={`leaderboard-row-${entry.rank}`}
                    >
                      {/* Rank */}
                      <td className="py-4 px-4 sm:px-6 text-center font-bold">
                        {isTop1 && <span className="text-amber-400 text-base">🥇 #1</span>}
                        {isTop2 && <span className="text-slate-300 text-base">🥈 #2</span>}
                        {isTop3 && <span className="text-amber-600 text-base">🥉 #3</span>}
                        {!isTop1 && !isTop2 && !isTop3 && (
                          <span className="text-slate-400 font-mono">#{entry.rank}</span>
                        )}
                      </td>

                      {/* Contributor Profile */}
                      <td className="py-4 px-4 sm:px-6">
                        <div className="flex items-center gap-3">
                          {entry.avatar_url ? (
                            <img
                              src={entry.avatar_url}
                              alt={entry.github_username}
                              width="36"
                              height="36"
                              loading="lazy"
                              decoding="async"
                              className="w-9 h-9 rounded-full border border-slate-700 bg-slate-800 object-cover"
                            />
                          ) : (
                            <div className="w-9 h-9 rounded-full border border-slate-700 bg-slate-800 flex items-center justify-center font-bold text-xs text-slate-300">
                              {entry.github_username.charAt(0).toUpperCase()}
                            </div>
                          )}
                          <div className="flex flex-col">
                            <Link
                              to={`/profile/${entry.github_username}`}
                              className="font-semibold text-white hover:text-cyan-400 transition-colors inline-flex items-center gap-1.5 focus:outline-none focus:underline"
                            >
                              {entry.github_username}
                              {isMe && (
                                <span className="px-1.5 py-0.2 rounded text-[9px] font-mono uppercase bg-indigo-900 text-indigo-300">
                                  you
                                </span>
                              )}
                            </Link>
                          </div>
                        </div>
                      </td>

                      {/* Merged PRs */}
                      <td className="py-4 px-4 sm:px-6 text-center font-mono text-slate-300 font-medium">
                        {entry.merged_count}
                      </td>

                      {/* Points */}
                      <td className="py-4 px-4 sm:px-6 text-right">
                        <span className="font-extrabold text-cyan-400 font-mono text-base">
                          {entry.total_points}
                        </span>
                        <span className="text-xs text-slate-500 ml-1">pts</span>
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
              className="border-t border-slate-800 bg-slate-900/60 px-4 sm:px-6 py-4 flex items-center justify-between gap-4"
              data-testid="pagination-controls"
            >
              <div className="text-xs text-slate-400 font-mono">
                Page <span className="text-white font-bold">{data.page}</span> of{' '}
                <span className="text-white font-bold">{data.num_pages}</span>
              </div>

              <div className="flex items-center gap-2">
                <button
                  onClick={handlePrevPage}
                  disabled={page <= 1}
                  type="button"
                  data-testid="prev-page-button"
                  className="px-3.5 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-xs font-medium text-slate-200 border border-slate-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors focus:outline-none focus:ring-2 focus:ring-cyan-500"
                >
                  Previous
                </button>
                <button
                  onClick={handleNextPage}
                  disabled={page >= data.num_pages}
                  type="button"
                  data-testid="next-page-button"
                  className="px-3.5 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-xs font-medium text-slate-200 border border-slate-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors focus:outline-none focus:ring-2 focus:ring-cyan-500"
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
