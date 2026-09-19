import { useSearchParams, Link } from 'react-router-dom';
import { useIssues } from '../api/issues';
import { EmptyState } from '../components/EmptyState';
import { ErrorState } from '../components/ErrorState';
import { IssuesListSkeleton } from '../components/Skeletons';
import { useDocumentTitle } from '../hooks/useDocumentTitle';

export function IssuesExplorerPage() {
  useDocumentTitle(
    'CommitRush — Issues',
    'Browse and filter available open-source contribution issues across all tracked repositories.'
  );

  const [searchParams, setSearchParams] = useSearchParams();

  // Read filter state from query parameters
  const projectParam = searchParams.get('project') || '';
  const languageParam = searchParams.get('language') || '';
  const difficultyParam = searchParams.get('difficulty') || '';
  const categoryParam = searchParams.get('category') || '';
  const statusParam = searchParams.get('status') || '';
  const pointsMinParam = searchParams.get('points_min') || '';
  const pointsMaxParam = searchParams.get('points_max') || '';
  const sortParam = searchParams.get('sort') || '-points';
  const pageParam = parseInt(searchParams.get('page') || '1', 10);

  const filters = {
    project: projectParam || undefined,
    language: languageParam || undefined,
    difficulty: difficultyParam || undefined,
    category: categoryParam || undefined,
    status: statusParam || undefined,
    points_min: pointsMinParam ? parseInt(pointsMinParam, 10) : undefined,
    points_max: pointsMaxParam ? parseInt(pointsMaxParam, 10) : undefined,
    sort: sortParam || undefined,
    page: pageParam > 0 ? pageParam : 1,
    page_size: 25,
  };

  const { data, isLoading, isError, error, refetch, isPlaceholderData } = useIssues(filters);

  const updateParam = (key: string, value: string) => {
    const next = new URLSearchParams(searchParams);
    if (value && value.trim()) {
      next.set(key, value.trim());
    } else {
      next.delete(key);
    }
    next.set('page', '1');
    setSearchParams(next);
  };

  const handleResetFilters = () => {
    setSearchParams(new URLSearchParams());
  };

  const setPage = (newPage: number) => {
    const next = new URLSearchParams(searchParams);
    next.set('page', String(newPage));
    setSearchParams(next);
  };

  const totalPages = data ? Math.max(1, Math.ceil(data.count / 25)) : 1;

  const hasActiveFilters = Boolean(
    projectParam ||
    languageParam ||
    difficultyParam ||
    categoryParam ||
    statusParam ||
    pointsMinParam ||
    pointsMaxParam ||
    (sortParam && sortParam !== '-points')
  );

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-800/80 pb-6">
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-white">
            Issues Explorer
          </h1>
          <p className="text-sm text-slate-400 mt-1">
            Browse, filter, and discover available tasks across all tracked repositories.
          </p>
        </div>
        {data && (
          <div className="text-xs font-mono px-3 py-1.5 bg-slate-900 border border-slate-800 rounded-lg text-slate-400 self-start md:self-auto">
            Matching Issues: <span className="text-cyan-400 font-semibold">{data.count}</span>
          </div>
        )}
      </div>

      {/* Filter Toolbar */}
      <div className="bg-slate-900/50 border border-slate-800/80 rounded-2xl p-4 sm:p-5 shadow-sm space-y-4">
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3.5">
          {/* Project Filter */}
          <div>
            <input
              type="text"
              aria-label="Filter by project repository"
              value={projectParam}
              onChange={(e) => updateParam('project', e.target.value)}
              placeholder="Filter by Project (repo)..."
              className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-cyan-500 focus:border-transparent transition-all"
            />
          </div>

          {/* Language Filter */}
          <div>
            <input
              type="text"
              aria-label="Filter by programming language"
              value={languageParam}
              onChange={(e) => updateParam('language', e.target.value)}
              placeholder="Language (Python, Rust...)"
              className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-cyan-500 focus:border-transparent transition-all"
            />
          </div>

          {/* Difficulty Filter */}
          <div>
            <select
              aria-label="Filter by difficulty"
              value={difficultyParam}
              onChange={(e) => updateParam('difficulty', e.target.value)}
              className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2 text-xs text-slate-200 focus:outline-none focus:ring-2 focus:ring-cyan-500 focus:border-transparent transition-all"
            >
              <option value="">Difficulty: All Tiers</option>
              <option value="beginner">Beginner</option>
              <option value="intermediate">Intermediate</option>
              <option value="advanced">Advanced</option>
            </select>
          </div>

          {/* Category Filter */}
          <div>
            <select
              aria-label="Filter by domain category"
              value={categoryParam}
              onChange={(e) => updateParam('category', e.target.value)}
              className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2 text-xs text-slate-200 focus:outline-none focus:ring-2 focus:ring-cyan-500 focus:border-transparent transition-all"
            >
              <option value="">Category: All Domains</option>
              <option value="backend">Backend</option>
              <option value="frontend">Frontend</option>
              <option value="docs">Docs</option>
              <option value="devops">DevOps / Infra</option>
            </select>
          </div>

          {/* Status Filter */}
          <div>
            <select
              aria-label="Filter by issue status"
              value={statusParam}
              onChange={(e) => updateParam('status', e.target.value)}
              className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2 text-xs text-slate-200 focus:outline-none focus:ring-2 focus:ring-cyan-500 focus:border-transparent transition-all"
            >
              <option value="">Status: All Issues</option>
              <option value="open">Open Only</option>
              <option value="closed">Closed Only</option>
            </select>
          </div>

          {/* Points Range: Min & Max */}
          <div className="flex items-center gap-2">
            <input
              type="number"
              min="0"
              aria-label="Minimum points bounty"
              value={pointsMinParam}
              onChange={(e) => updateParam('points_min', e.target.value)}
              placeholder="Min Pts"
              className="w-1/2 bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-cyan-500 focus:border-transparent"
            />
            <span className="text-slate-600 text-xs">-</span>
            <input
              type="number"
              min="0"
              aria-label="Maximum points bounty"
              value={pointsMaxParam}
              onChange={(e) => updateParam('points_max', e.target.value)}
              placeholder="Max Pts"
              className="w-1/2 bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-cyan-500 focus:border-transparent"
            />
          </div>

          {/* Sort Selector */}
          <div className="sm:col-span-2 lg:col-span-2">
            <select
              aria-label="Sort issues"
              value={sortParam}
              onChange={(e) => updateParam('sort', e.target.value)}
              className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2 text-xs text-slate-200 focus:outline-none focus:ring-2 focus:ring-cyan-500 focus:border-transparent font-medium"
            >
              <option value="-points">Sort: Highest Points First</option>
              <option value="points">Sort: Lowest Points First</option>
              <option value="newest">Sort: Newest Issues First</option>
              <option value="oldest">Sort: Oldest Issues First</option>
            </select>
          </div>
        </div>

        {/* Active Filter Tags Bar */}
        {hasActiveFilters && (
          <div className="flex flex-wrap items-center gap-2 pt-2 border-t border-slate-800/40 text-xs text-slate-400">
            <span>Filters:</span>
            {projectParam && (
              <span className="bg-slate-800 text-cyan-400 px-2 py-0.5 rounded-md border border-slate-700/60">
                Repo: {projectParam}
              </span>
            )}
            {languageParam && (
              <span className="bg-slate-800 text-cyan-400 px-2 py-0.5 rounded-md border border-slate-700/60">
                Lang: {languageParam}
              </span>
            )}
            {difficultyParam && (
              <span className="bg-slate-800 text-cyan-400 px-2 py-0.5 rounded-md border border-slate-700/60">
                Difficulty: {difficultyParam}
              </span>
            )}
            {categoryParam && (
              <span className="bg-slate-800 text-cyan-400 px-2 py-0.5 rounded-md border border-slate-700/60">
                Cat: {categoryParam}
              </span>
            )}
            {statusParam && (
              <span className="bg-slate-800 text-cyan-400 px-2 py-0.5 rounded-md border border-slate-700/60">
                Status: {statusParam}
              </span>
            )}
            {(pointsMinParam || pointsMaxParam) && (
              <span className="bg-slate-800 text-cyan-400 px-2 py-0.5 rounded-md border border-slate-700/60">
                Pts: {pointsMinParam || '0'} - {pointsMaxParam || '∞'}
              </span>
            )}
            <button
              onClick={handleResetFilters}
              type="button"
              className="text-slate-400 hover:text-white underline ml-1 cursor-pointer"
            >
              Reset all
            </button>
          </div>
        )}
      </div>

      {/* Main Issue List */}
      {isLoading ? (
        <IssuesListSkeleton />
      ) : isError ? (
        <ErrorState error={error} onRetry={() => refetch()} />
      ) : !data || data.results.length === 0 ? (
        <EmptyState
          title="No issues match your filters"
          message="Try broadening your search criteria or resetting filters to see available issues."
          actionLabel="Reset filters"
          onAction={handleResetFilters}
        />
      ) : (
        <div className="space-y-4">
          <div className="space-y-3" data-testid="issues-list">
            {data.results.map((issue) => (
              <div
                key={issue.id}
                className="bg-slate-900/60 hover:bg-slate-850 border border-slate-800 hover:border-slate-700 rounded-xl p-4 sm:p-5 transition-all duration-150 flex flex-col sm:flex-row sm:items-center justify-between gap-4 shadow-sm"
              >
                <div className="space-y-2 flex-1 min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <Link
                      to={`/issues/${issue.id}`}
                      className="text-base font-semibold text-white hover:text-cyan-400 transition-colors break-words"
                    >
                      {issue.title}
                    </Link>
                    <span className="text-xs text-slate-500 font-mono">
                      #{issue.github_number}
                    </span>
                    {issue.is_featured && (
                      <span className="bg-amber-950/80 border border-amber-800/60 text-amber-400 text-[10px] font-bold px-2 py-0.5 rounded-full uppercase tracking-wider">
                        Featured
                      </span>
                    )}
                  </div>

                  <div className="flex flex-wrap items-center gap-3 text-xs text-slate-400">
                    <Link
                      to={`/projects/${encodeURIComponent(issue.project)}`}
                      className="text-cyan-400 hover:underline font-mono"
                    >
                      {issue.project}
                    </Link>

                    {issue.difficulty && (
                      <span className="capitalize px-2 py-0.5 rounded-md bg-slate-800 border border-slate-700/60 text-slate-300">
                        {issue.difficulty}
                      </span>
                    )}

                    {issue.category && (
                      <span className="capitalize px-2 py-0.5 rounded-md bg-slate-800 border border-slate-700/60 text-slate-300">
                        {issue.category}
                      </span>
                    )}

                    <span
                      className={`capitalize px-2 py-0.5 rounded-md ${
                        issue.status === 'open'
                          ? 'text-emerald-400 bg-emerald-950/40 border border-emerald-900/40'
                          : 'text-slate-400 bg-slate-800'
                      }`}
                    >
                      {issue.status}
                    </span>
                  </div>

                  {issue.labels && issue.labels.length > 0 && (
                    <div className="flex flex-wrap gap-1.5 pt-1">
                      {issue.labels.map((label) => (
                        <span
                          key={label}
                          className="px-2 py-0.5 text-[11px] rounded bg-slate-800/80 border border-slate-700/50 text-slate-400 font-mono"
                        >
                          {label}
                        </span>
                      ))}
                    </div>
                  )}
                </div>

                <div className="flex sm:flex-col items-center sm:items-end justify-between gap-3 pt-3 sm:pt-0 border-t sm:border-t-0 border-slate-800/60">
                  <div className="text-right">
                    <span className="text-lg font-bold text-cyan-400">
                      +{issue.points}
                    </span>
                    <span className="text-[11px] text-slate-500 block uppercase tracking-wider">
                      Points
                    </span>
                  </div>

                  <div className="flex items-center gap-2">
                    <Link
                      to={`/issues/${issue.id}`}
                      className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-xs font-medium text-slate-200 transition-colors"
                    >
                      Details
                    </Link>
                    <a
                      href={issue.github_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="px-3 py-1.5 rounded-lg bg-cyan-600/20 hover:bg-cyan-600/30 border border-cyan-500/40 text-xs font-medium text-cyan-300 transition-colors flex items-center gap-1"
                    >
                      <span>GitHub</span>
                      <span>↗</span>
                    </a>
                  </div>
                </div>
              </div>
            ))}
          </div>

          {/* Pagination Controls */}
          <div className="flex flex-col sm:flex-row items-center justify-between gap-4 pt-4 border-t border-slate-800/80">
            <span className="text-xs text-slate-400">
              Page <span className="font-semibold text-white">{filters.page}</span> of{' '}
              <span className="font-semibold text-white">{totalPages}</span> (
              {data.count} total matching issues)
            </span>

            <div className="flex items-center space-x-2">
              <button
                type="button"
                onClick={() => setPage(Math.max(1, filters.page - 1))}
                disabled={filters.page <= 1 || isPlaceholderData}
                className="px-3.5 py-1.5 rounded-lg bg-slate-900 border border-slate-800 text-xs font-medium text-slate-300 hover:bg-slate-800 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
              >
                Previous
              </button>
              <button
                type="button"
                onClick={() => setPage(filters.page + 1)}
                disabled={!data.next || filters.page >= totalPages || isPlaceholderData}
                className="px-3.5 py-1.5 rounded-lg bg-slate-900 border border-slate-800 text-xs font-medium text-slate-300 hover:bg-slate-800 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
              >
                Next
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
