import { useSearchParams, Link } from 'react-router-dom';
import { useMyContributions } from '../api/contributions';
import { ContributionStatusBadge, getContributionStatusMeta } from '../components/ContributionStatusBadge';
import { EmptyState } from '../components/EmptyState';
import { ErrorState } from '../components/ErrorState';
import { ContributionsListSkeleton } from '../components/Skeletons';

const STATUS_FILTER_OPTIONS = [
  { label: 'All Statuses', value: '' },
  { label: 'Pending', value: 'PENDING' },
  { label: 'Queued', value: 'QUEUED' },
  { label: 'Under Review / Validating', value: 'UNDER_REVIEW' },
  { label: 'Approved', value: 'APPROVED' },
  { label: 'Merging', value: 'MERGING' },
  { label: 'Merged', value: 'MERGED' },
  { label: 'Flagged', value: 'FLAGGED' },
  { label: 'Retry', value: 'RETRY' },
  { label: 'Rejected', value: 'REJECTED' },
];

export function MyContributionsPage() {
  const [searchParams, setSearchParams] = useSearchParams();

  const statusParam = searchParams.get('status') || '';
  const pageParam = parseInt(searchParams.get('page') || '1', 10);

  const filters = {
    status: statusParam || undefined,
    page: pageParam > 0 ? pageParam : 1,
    page_size: 20,
  };

  const { data, isLoading, isError, error, refetch, isPlaceholderData } =
    useMyContributions(filters);

  const updateStatusFilter = (newStatus: string) => {
    const next = new URLSearchParams(searchParams);
    if (newStatus) {
      next.set('status', newStatus);
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

  const totalPages = data ? Math.max(1, Math.ceil(data.count / 20)) : 1;

  return (
    <div className="space-y-6">
      {/* Header section */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-800 pb-5">
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-white flex items-center gap-3">
            <span>My Contributions</span>
            {data && (
              <span className="text-xs px-2.5 py-1 rounded-full bg-slate-800 text-slate-300 font-mono font-medium border border-slate-700">
                {data.count} {data.count === 1 ? 'total' : 'total'}
              </span>
            )}
          </h1>
          <p className="text-sm text-slate-400 mt-1">
            Track real-time validation, approval, merge queue state, and points for your sprint contributions.
          </p>
        </div>

        {/* Live status polling indicator */}
        <div className="flex items-center gap-2 text-xs text-slate-400 bg-slate-900/80 px-3 py-1.5 rounded-lg border border-slate-800">
          <span className="w-2 h-2 rounded-full bg-cyan-400 animate-pulse" />
          <span>Real-time state sync</span>
        </div>
      </div>

      {/* Filter controls */}
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-xs font-medium text-slate-400 uppercase tracking-wider mr-1">
          Status:
        </span>
        {STATUS_FILTER_OPTIONS.map((opt) => {
          const isActive = statusParam === opt.value;
          return (
            <button
              key={opt.value}
              type="button"
              onClick={() => updateStatusFilter(opt.value)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                isActive
                  ? 'bg-cyan-950 text-cyan-300 border border-cyan-700/80 shadow-sm'
                  : 'bg-slate-900/80 text-slate-400 hover:text-slate-200 hover:bg-slate-800 border border-slate-800'
              }`}
            >
              {opt.label}
            </button>
          );
        })}
      </div>

      {/* Main Content Area */}
      {isLoading && <ContributionsListSkeleton />}

      {isError && (
        <ErrorState
          error={error}
          onRetry={() => refetch()}
          title="Failed to load contributions"
        />
      )}

      {!isLoading && !isError && data && data.results.length === 0 && (
        <EmptyState
          title={statusParam ? 'No matching contributions' : 'No contributions yet'}
          message={
            statusParam
              ? `No contributions found with status '${statusParam}'. Try selecting another status filter.`
              : 'You have not submitted any pull requests against tracked issues yet. Explore open issues and open a PR!'
          }
          actionLabel={statusParam ? 'Clear Status Filter' : 'Explore Issues'}
          onAction={() => {
            if (statusParam) {
              updateStatusFilter('');
            } else {
              window.location.href = '/issues';
            }
          }}
        />
      )}

      {!isLoading && !isError && data && data.results.length > 0 && (
        <div className="space-y-4">
          <div
            className={`space-y-3.5 transition-opacity ${
              isPlaceholderData ? 'opacity-60' : 'opacity-100'
            }`}
          >
            {data.results.map((item) => {
              const meta = getContributionStatusMeta(item.status, item.sub_status);
              return (
                <div
                  key={item.id}
                  className="bg-slate-900/70 hover:bg-slate-900 border border-slate-800 hover:border-slate-700 rounded-xl p-5 transition-all space-y-3 group"
                >
                  <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-3">
                    <div className="space-y-1.5 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <Link
                          to={`/contributions/${item.id}`}
                          className="text-base font-semibold text-white group-hover:text-cyan-400 transition-colors"
                        >
                          {item.issue?.title || `Contribution #${item.id}`}
                        </Link>
                        {item.issue?.points !== undefined && (
                          <span className="text-xs px-2 py-0.5 rounded bg-cyan-950 text-cyan-300 border border-cyan-800 font-mono font-medium">
                            {`${item.issue.points} pts`}
                          </span>
                        )}
                      </div>

                      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-slate-400">
                        {item.pull_request?.repo && (
                          <span className="font-mono text-slate-300">
                            {item.pull_request.repo}
                          </span>
                        )}
                        {item.pull_request?.number && (
                          <span>
                            PR #{item.pull_request.number}
                          </span>
                        )}
                        {item.issue?.github_number && (
                          <span>
                            Issue #{item.issue.github_number}
                          </span>
                        )}
                      </div>
                    </div>

                    <div className="flex flex-col sm:items-end gap-1">
                      <ContributionStatusBadge
                        status={item.status}
                        subStatus={item.sub_status}
                        size="md"
                      />
                    </div>
                  </div>

                  {/* One-line status explanation */}
                  <div className="text-xs text-slate-400 bg-slate-950/60 rounded-lg p-2.5 border border-slate-800/80 flex items-start gap-2">
                    <span className="text-cyan-400 font-semibold uppercase text-[10px] tracking-wider mt-0.5">
                      Status Info:
                    </span>
                    <span className="flex-1">{meta.description}</span>
                  </div>

                  {/* Flagged reason or retry count notice if present */}
                  {item.flagged_reason && (
                    <div className="text-xs text-amber-300 bg-amber-950/40 rounded-lg p-2.5 border border-amber-800/50">
                      <span className="font-semibold">Review note: </span>
                      <span>{item.flagged_reason}</span>
                    </div>
                  )}

                  {/* Metadata and links footer */}
                  <div className="pt-2 flex flex-wrap items-center justify-between gap-3 border-t border-slate-800/60 text-xs text-slate-400">
                    <div className="flex items-center gap-3">
                      <span>Submitted: {new Date(item.created_at).toLocaleDateString()}</span>
                      {item.retry_count > 0 && (
                        <span className="text-orange-400 font-mono">
                          Retries: {item.retry_count}
                        </span>
                      )}
                    </div>

                    <div className="flex items-center gap-3">
                      {item.pull_request?.github_url && (
                        <a
                          href={item.pull_request.github_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-slate-400 hover:text-cyan-400 transition-colors inline-flex items-center gap-1"
                        >
                          <span>GitHub PR</span>
                          <svg
                            className="w-3 h-3"
                            fill="none"
                            stroke="currentColor"
                            viewBox="0 0 24 24"
                          >
                            <path
                              strokeLinecap="round"
                              strokeLinejoin="round"
                              strokeWidth={2}
                              d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"
                            />
                          </svg>
                        </a>
                      )}
                      <Link
                        to={`/contributions/${item.id}`}
                        className="text-cyan-400 hover:text-cyan-300 font-medium"
                      >
                        View Details &rarr;
                      </Link>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>

          {/* Pagination Controls */}
          {totalPages > 1 && (
            <div className="flex items-center justify-between pt-4 border-t border-slate-800 text-xs text-slate-400">
              <div>
                Page {filters.page} of {totalPages} ({data.count} contributions)
              </div>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  disabled={filters.page <= 1}
                  onClick={() => setPage(filters.page - 1)}
                  className="px-3 py-1.5 rounded-lg bg-slate-900 border border-slate-800 hover:bg-slate-800 disabled:opacity-40 disabled:cursor-not-allowed text-slate-200"
                >
                  &larr; Previous
                </button>
                <button
                  type="button"
                  disabled={filters.page >= totalPages}
                  onClick={() => setPage(filters.page + 1)}
                  className="px-3 py-1.5 rounded-lg bg-slate-900 border border-slate-800 hover:bg-slate-800 disabled:opacity-40 disabled:cursor-not-allowed text-slate-200"
                >
                  Next &rarr;
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
