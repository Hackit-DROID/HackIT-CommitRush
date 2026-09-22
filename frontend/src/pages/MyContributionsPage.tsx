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
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-[#d8d8d3] pb-5">
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-[#111111] flex items-center gap-3">
            <span>My Contributions</span>
            {data && (
              <span className="text-xs px-2.5 py-1 rounded-[4px] bg-[#f4f4f1] text-[#111111] font-mono font-medium border border-[#d8d8d3]">
                {data.count} {data.count === 1 ? 'total' : 'total'}
              </span>
            )}
          </h1>
          <p className="text-sm text-[#555555] mt-1 font-sans">
            Track real-time validation, approval, merge queue state, and points for your sprint contributions.
          </p>
        </div>

        {/* Live status polling indicator */}
        <div className="flex items-center gap-2 text-xs font-mono text-[#555555] bg-white px-3 py-1.5 rounded-[4px] border border-[#d8d8d3]">
          <span className="w-2 h-2 rounded-full bg-[#ff5a1f] animate-pulse" />
          <span>Real-time state sync</span>
        </div>
      </div>

      {/* Filter controls */}
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-xs font-mono font-medium text-[#777777] uppercase tracking-wider mr-1">
          Status:
        </span>
        {STATUS_FILTER_OPTIONS.map((opt) => {
          const isActive = statusParam === opt.value;
          return (
            <button
              key={opt.value}
              type="button"
              onClick={() => updateStatusFilter(opt.value)}
              className={`px-3.5 py-1.5 rounded-[4px] text-xs font-mono font-medium transition-all cursor-pointer ${
                isActive
                  ? 'bg-[#050505] text-white border border-[#050505] shadow-sm'
                  : 'bg-white text-[#555555] hover:text-[#111111] hover:bg-[#f4f4f1] border border-[#d8d8d3]'
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
                  className="bg-white hover:border-[#111111] border border-[#d8d8d3] rounded-md p-5 sm:p-6 transition-all space-y-4 group shadow-sm"
                >
                  <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-3">
                    <div className="space-y-1.5 flex-1 min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <Link
                          to={`/contributions/${item.id}`}
                          className="text-base font-bold text-[#111111] group-hover:text-[#ff5a1f] transition-colors break-words focus:outline-none focus-visible:ring-2 focus-visible:ring-[#ff5a1f] rounded-sm"
                        >
                          {item.issue?.title || `Contribution #${item.id}`}
                        </Link>
                        {item.issue?.points !== undefined && (
                          <span className="text-xs px-2.5 py-0.5 rounded-[4px] bg-[#f4f4f1] text-[#111111] border border-[#d8d8d3] font-mono font-medium tabular-nums">
                            {`${item.issue.points} pts`}
                          </span>
                        )}
                      </div>

                      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-[#777777] font-mono">
                        {item.pull_request?.repo && (
                          <span className="text-[#111111] truncate max-w-[200px] sm:max-w-xs">
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

                    <div className="flex flex-col sm:items-end gap-1 shrink-0">
                      <ContributionStatusBadge
                        status={item.status}
                        subStatus={item.sub_status}
                        size="md"
                      />
                    </div>
                  </div>

                  {/* One-line status explanation */}
                  <div className="text-xs text-[#555555] bg-[#f4f4f1] rounded-[4px] p-3 border border-[#d8d8d3] flex items-start gap-2 font-mono">
                    <span className="text-[#111111] font-semibold uppercase text-[10px] tracking-wider mt-0.5">
                      Status Info:
                    </span>
                    <span className="flex-1 font-sans text-[#555555]">{meta.description}</span>
                  </div>

                  {/* Flagged reason or retry count notice if present */}
                  {item.flagged_reason && (
                    <div className="text-xs text-amber-900 bg-amber-50 rounded-[4px] p-3 border border-amber-200 font-mono">
                      <span className="font-semibold">Review note: </span>
                      <span>{item.flagged_reason}</span>
                    </div>
                  )}

                  {/* Metadata and links footer */}
                  <div className="pt-3 flex flex-wrap items-center justify-between gap-3 border-t border-[#d8d8d3] text-xs text-[#777777] font-mono">
                    <div className="flex items-center gap-3">
                      <span>Submitted: {new Date(item.created_at).toLocaleDateString()}</span>
                      {item.retry_count > 0 && (
                        <span className="text-[#ff5a1f] font-mono">
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
                          className="text-[#777777] hover:text-[#111111] transition-colors inline-flex items-center gap-1 font-mono focus:outline-none focus-visible:ring-2 focus-visible:ring-[#ff5a1f] rounded-sm"
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
                        className="text-[#111111] hover:text-[#ff5a1f] font-medium transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-[#ff5a1f] rounded-sm"
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
            <div className="flex items-center justify-between pt-4 border-t border-[#d8d8d3] text-xs text-[#777777] font-mono">
              <div>
                Page {filters.page} of {totalPages} ({data.count} contributions)
              </div>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  disabled={filters.page <= 1}
                  onClick={() => setPage(filters.page - 1)}
                  className="px-3.5 py-1.5 rounded-[4px] bg-white border border-[#d8d8d3] hover:bg-[#f4f4f1] hover:border-[#111111] disabled:opacity-40 disabled:cursor-not-allowed text-[#111111] transition-colors cursor-pointer"
                >
                  &larr; Previous
                </button>
                <button
                  type="button"
                  disabled={filters.page >= totalPages}
                  onClick={() => setPage(filters.page + 1)}
                  className="px-3.5 py-1.5 rounded-[4px] bg-white border border-[#d8d8d3] hover:bg-[#f4f4f1] hover:border-[#111111] disabled:opacity-40 disabled:cursor-not-allowed text-[#111111] transition-colors cursor-pointer"
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
