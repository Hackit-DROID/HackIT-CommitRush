import { useSearchParams, Link } from 'react-router-dom';
import { useIssues, useIssueCategories } from '../api/issues';
import { CATEGORY_LABEL_MAP, ISSUE_CATEGORIES } from '../constants/categories';
import { EmptyState } from '../components/EmptyState';
import { ErrorState } from '../components/ErrorState';
import { IssuesListSkeleton } from '../components/Skeletons';
import { useDocumentTitle } from '../hooks/useDocumentTitle';

export function IssuesExplorerPage() {
  useDocumentTitle(
    'CommitRush 2026 — Issues',
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
  const { data: categoriesData } = useIssueCategories();
  const categories = Array.isArray(categoriesData) ? categoriesData : ISSUE_CATEGORIES;

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
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-[#d8d8d3] pb-6">
        <div>
          <h1 className="text-2xl sm:text-3xl font-display font-bold tracking-tight text-[#111111]">
            Issues Explorer
          </h1>
          <p className="text-sm text-[#555555] mt-1">
            Browse, filter, and discover available tasks across all tracked repositories.
          </p>
        </div>
        {data && (
          <div className="text-xs font-mono px-3.5 py-1.5 bg-white border border-[#d8d8d3] rounded-full text-[#555555] self-start md:self-auto shadow-sm">
            Matching Issues: <span className="text-[#ff5a1f] font-semibold">{data.count}</span>
          </div>
        )}
      </div>

      {/* Filter Toolbar */}
      <div className="bg-white border border-[#d8d8d3] rounded-md p-4 sm:p-5 shadow-sm space-y-4">
        <div className="flex items-center justify-between border-b border-[#d8d8d3]/60 pb-3">
          <div className="flex items-center gap-2">
            <svg className="w-3.5 h-3.5 text-[#555555]" viewBox="0 0 20 20" fill="currentColor">
              <path fillRule="evenodd" d="M2.628 1.601C5.028 1.206 7.49 1 10 1s4.972.206 7.372.601a.75.75 0 01.628.74v2.288a2.25 2.25 0 01-.659 1.59l-4.682 4.683a2.25 2.25 0 00-.659 1.59v3.037c0 .684-.31 1.33-.844 1.757l-1.937 1.55A.75.75 0 018 18.25v-5.757a2.25 2.25 0 00-.659-1.591L2.659 6.22A2.25 2.25 0 012 4.629V2.34a.75.75 0 01.628-.74z" clipRule="evenodd" />
            </svg>
            <span className="text-xs font-mono uppercase tracking-wider font-semibold text-[#111111]">
              Filters & Search
            </span>
          </div>
          {hasActiveFilters && (
            <button
              type="button"
              onClick={handleResetFilters}
              className="text-xs text-[#ff5a1f] hover:text-[#ff8a3d] font-medium transition-colors cursor-pointer flex items-center gap-1 font-mono"
            >
              <span>Reset all</span>
              <span>✕</span>
            </button>
          )}
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3.5">
          {/* Project Filter */}
          <div>
            <label className="block text-[10px] font-mono uppercase tracking-wider text-[#777777] mb-1.5 font-semibold">
              Repository
            </label>
            <div className="relative">
              <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-2.5 text-[#777777]">
                <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-4.35-4.35m0 0A7.5 7.5 0 105.65 5.65a7.5 7.5 0 0010.7 10.7z" />
                </svg>
              </div>
              <input
                type="text"
                aria-label="Filter by project repository"
                value={projectParam}
                onChange={(e) => updateParam('project', e.target.value)}
                placeholder="Filter by Project (repo)..."
                className="w-full bg-[#f4f4f1] hover:bg-[#eaeae5] border border-[#d8d8d3] hover:border-[#111111] rounded-[4px] pl-8 pr-7 py-2 text-xs text-[#111111] placeholder-[#777777] focus:outline-none focus:border-[#111111] focus:ring-1 focus:ring-[#111111] focus:bg-white transition-all"
              />
              {projectParam && (
                <button
                  type="button"
                  aria-label="Clear project filter"
                  onClick={() => updateParam('project', '')}
                  className="absolute right-2 top-1/2 -translate-y-1/2 text-[#777777] hover:text-[#111111] text-xs cursor-pointer p-0.5"
                >
                  ✕
                </button>
              )}
            </div>
          </div>

          {/* Language Filter */}
          <div>
            <label className="block text-[10px] font-mono uppercase tracking-wider text-[#777777] mb-1.5 font-semibold">
              Language
            </label>
            <div className="relative">
              <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-2.5 text-[#777777]">
                <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" />
                </svg>
              </div>
              <input
                type="text"
                aria-label="Filter by programming language"
                value={languageParam}
                onChange={(e) => updateParam('language', e.target.value)}
                placeholder="Language (Python, Rust...)"
                className="w-full bg-[#f4f4f1] hover:bg-[#eaeae5] border border-[#d8d8d3] hover:border-[#111111] rounded-[4px] pl-8 pr-7 py-2 text-xs text-[#111111] placeholder-[#777777] focus:outline-none focus:border-[#111111] focus:ring-1 focus:ring-[#111111] focus:bg-white transition-all"
              />
              {languageParam && (
                <button
                  type="button"
                  aria-label="Clear language filter"
                  onClick={() => updateParam('language', '')}
                  className="absolute right-2 top-1/2 -translate-y-1/2 text-[#777777] hover:text-[#111111] text-xs cursor-pointer p-0.5"
                >
                  ✕
                </button>
              )}
            </div>
          </div>

          {/* Difficulty Filter */}
          <div>
            <label className="block text-[10px] font-mono uppercase tracking-wider text-[#777777] mb-1.5 font-semibold">
              Difficulty
            </label>
            <div className="relative">
              <select
                aria-label="Filter by difficulty"
                value={difficultyParam}
                onChange={(e) => updateParam('difficulty', e.target.value)}
                className="w-full appearance-none bg-[#f4f4f1] hover:bg-[#eaeae5] border border-[#d8d8d3] hover:border-[#111111] rounded-[4px] pl-3 pr-8 py-2 text-xs text-[#111111] focus:outline-none focus:border-[#111111] focus:ring-1 focus:ring-[#111111] focus:bg-white transition-all cursor-pointer font-medium"
              >
                <option value="" className="bg-white text-[#111111]">Difficulty: All Tiers</option>
                <option value="beginner" className="bg-white text-[#111111]">Beginner</option>
                <option value="intermediate" className="bg-white text-[#111111]">Intermediate</option>
                <option value="advanced" className="bg-white text-[#111111]">Advanced</option>
              </select>
              <div className="pointer-events-none absolute inset-y-0 right-0 flex items-center pr-2.5 text-[#555555]">
                <svg className="w-3.5 h-3.5" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
                  <path fillRule="evenodd" d="M5.23 7.21a.75.75 0 011.06.02L10 11.168l3.71-3.938a.75.75 0 111.08 1.04l-4.25 4.5a.75.75 0 01-1.08 0l-4.25-4.5a.75.75 0 01.02-1.06z" clipRule="evenodd" />
                </svg>
              </div>
            </div>
          </div>

          {/* Category Filter */}
          <div>
            <label className="block text-[10px] font-mono uppercase tracking-wider text-[#777777] mb-1.5 font-semibold">
              Category
            </label>
            <div className="relative">
              <select
                aria-label="Filter by issue category"
                value={categoryParam}
                onChange={(e) => updateParam('category', e.target.value)}
                className="w-full appearance-none bg-[#f4f4f1] hover:bg-[#eaeae5] border border-[#d8d8d3] hover:border-[#111111] rounded-[4px] pl-3 pr-8 py-2 text-xs text-[#111111] focus:outline-none focus:border-[#111111] focus:ring-1 focus:ring-[#111111] focus:bg-white transition-all cursor-pointer font-medium"
              >
                <option value="" className="bg-white text-[#111111]">Category: All Categories</option>
                {categories.map((cat) => (
                  <option key={cat.value} value={cat.value} className="bg-white text-[#111111]">
                    {cat.label}
                  </option>
                ))}
              </select>
              <div className="pointer-events-none absolute inset-y-0 right-0 flex items-center pr-2.5 text-[#555555]">
                <svg className="w-3.5 h-3.5" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
                  <path fillRule="evenodd" d="M5.23 7.21a.75.75 0 011.06.02L10 11.168l3.71-3.938a.75.75 0 111.08 1.04l-4.25 4.5a.75.75 0 01-1.08 0l-4.25-4.5a.75.75 0 01.02-1.06z" clipRule="evenodd" />
                </svg>
              </div>
            </div>
          </div>

          {/* Status Filter */}
          <div>
            <label className="block text-[10px] font-mono uppercase tracking-wider text-[#777777] mb-1.5 font-semibold">
              Status
            </label>
            <div className="relative">
              <select
                aria-label="Filter by issue status"
                value={statusParam}
                onChange={(e) => updateParam('status', e.target.value)}
                className="w-full appearance-none bg-[#f4f4f1] hover:bg-[#eaeae5] border border-[#d8d8d3] hover:border-[#111111] rounded-[4px] pl-3 pr-8 py-2 text-xs text-[#111111] focus:outline-none focus:border-[#111111] focus:ring-1 focus:ring-[#111111] focus:bg-white transition-all cursor-pointer font-medium"
              >
                <option value="" className="bg-white text-[#111111]">Status: All Issues</option>
                <option value="open" className="bg-white text-[#111111]">Open Only</option>
                <option value="closed" className="bg-white text-[#111111]">Closed Only</option>
              </select>
              <div className="pointer-events-none absolute inset-y-0 right-0 flex items-center pr-2.5 text-[#555555]">
                <svg className="w-3.5 h-3.5" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
                  <path fillRule="evenodd" d="M5.23 7.21a.75.75 0 011.06.02L10 11.168l3.71-3.938a.75.75 0 111.08 1.04l-4.25 4.5a.75.75 0 01-1.08 0l-4.25-4.5a.75.75 0 01.02-1.06z" clipRule="evenodd" />
                </svg>
              </div>
            </div>
          </div>

          {/* Points Range: Min & Max */}
          <div>
            <label className="block text-[10px] font-mono uppercase tracking-wider text-[#777777] mb-1.5 font-semibold">
              Points Bounty
            </label>
            <div className="flex items-center gap-1.5">
              <input
                type="number"
                min="0"
                aria-label="Minimum points bounty"
                value={pointsMinParam}
                onChange={(e) => updateParam('points_min', e.target.value)}
                placeholder="Min Pts"
                className="w-1/2 bg-[#f4f4f1] hover:bg-[#eaeae5] border border-[#d8d8d3] hover:border-[#111111] rounded-[4px] px-2.5 py-2 text-xs text-[#111111] placeholder-[#777777] focus:outline-none focus:border-[#111111] focus:ring-1 focus:ring-[#111111] focus:bg-white font-mono transition-all"
              />
              <span className="text-[#777777] text-xs font-mono">—</span>
              <input
                type="number"
                min="0"
                aria-label="Maximum points bounty"
                value={pointsMaxParam}
                onChange={(e) => updateParam('points_max', e.target.value)}
                placeholder="Max Pts"
                className="w-1/2 bg-[#f4f4f1] hover:bg-[#eaeae5] border border-[#d8d8d3] hover:border-[#111111] rounded-[4px] px-2.5 py-2 text-xs text-[#111111] placeholder-[#777777] focus:outline-none focus:border-[#111111] focus:ring-1 focus:ring-[#111111] focus:bg-white font-mono transition-all"
              />
            </div>
          </div>

          {/* Sort Selector */}
          <div className="sm:col-span-2 lg:col-span-2">
            <label className="block text-[10px] font-mono uppercase tracking-wider text-[#777777] mb-1.5 font-semibold">
              Sort Order
            </label>
            <div className="relative">
              <select
                aria-label="Sort issues"
                value={sortParam}
                onChange={(e) => updateParam('sort', e.target.value)}
                className="w-full appearance-none bg-[#f4f4f1] hover:bg-[#eaeae5] border border-[#d8d8d3] hover:border-[#111111] rounded-[4px] pl-3 pr-8 py-2 text-xs text-[#111111] focus:outline-none focus:border-[#111111] focus:ring-1 focus:ring-[#111111] focus:bg-white font-medium cursor-pointer transition-all"
              >
                <option value="-points" className="bg-white text-[#111111]">Sort: Highest Points First</option>
                <option value="points" className="bg-white text-[#111111]">Sort: Lowest Points First</option>
                <option value="newest" className="bg-white text-[#111111]">Sort: Newest Issues First</option>
                <option value="oldest" className="bg-white text-[#111111]">Sort: Oldest Issues First</option>
                <option value="updated" className="bg-white text-[#111111]">Sort: Recently Updated</option>
              </select>
              <div className="pointer-events-none absolute inset-y-0 right-0 flex items-center pr-2.5 text-[#555555]">
                <svg className="w-3.5 h-3.5" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
                  <path fillRule="evenodd" d="M5.23 7.21a.75.75 0 011.06.02L10 11.168l3.71-3.938a.75.75 0 111.08 1.04l-4.25 4.5a.75.75 0 01-1.08 0l-4.25-4.5a.75.75 0 01.02-1.06z" clipRule="evenodd" />
                </svg>
              </div>
            </div>
          </div>
        </div>

        {/* Active Filter Tags Bar */}
        {hasActiveFilters && (
          <div className="flex flex-wrap items-center gap-2 pt-2 border-t border-[#d8d8d3] text-xs text-[#555555]">
            <span>Filters:</span>
            {projectParam && (
              <span className="bg-[#f4f4f1] text-[#111111] px-2.5 py-0.5 rounded-full border border-[#d8d8d3]">
                Repo: {projectParam}
              </span>
            )}
            {languageParam && (
              <span className="bg-[#f4f4f1] text-[#111111] px-2.5 py-0.5 rounded-full border border-[#d8d8d3]">
                Lang: {languageParam}
              </span>
            )}
            {difficultyParam && (
              <span className="bg-[#f4f4f1] text-[#111111] px-2.5 py-0.5 rounded-full border border-[#d8d8d3]">
                Difficulty: {difficultyParam}
              </span>
            )}
            {categoryParam && (
              <span className="bg-[#f4f4f1] text-[#111111] px-2.5 py-0.5 rounded-full border border-[#d8d8d3]">
                Category: {CATEGORY_LABEL_MAP[categoryParam] || categoryParam}
              </span>
            )}
            {statusParam && (
              <span className="bg-[#f4f4f1] text-[#111111] px-2.5 py-0.5 rounded-full border border-[#d8d8d3]">
                Status: {statusParam}
              </span>
            )}
            {(pointsMinParam || pointsMaxParam) && (
              <span className="bg-[#f4f4f1] text-[#111111] px-2.5 py-0.5 rounded-full border border-[#d8d8d3]">
                Pts: {pointsMinParam || '0'} - {pointsMaxParam || '∞'}
              </span>
            )}
            <button
              onClick={handleResetFilters}
              type="button"
              className="text-[#555555] hover:text-[#111111] underline ml-1 cursor-pointer"
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
                className="bg-white hover:bg-[#fafaf8] border border-[#d8d8d3] hover:border-[#111111] rounded-md p-5 transition-all duration-150 flex flex-col sm:flex-row sm:items-center justify-between gap-4 shadow-sm"
              >
                <div className="space-y-2 flex-1 min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <Link
                      to={`/issues/${issue.id}`}
                      className="text-base font-semibold text-[#111111] hover:text-[#ff5a1f] transition-colors break-words"
                    >
                      {issue.title}
                    </Link>
                    <span className="text-xs text-[#777777] font-mono">
                      #{issue.github_number}
                    </span>
                    {issue.is_featured && (
                      <span className="bg-orange-50 border border-orange-200 text-[#ff5a1f] text-[10px] font-bold px-2.5 py-0.5 rounded-full uppercase tracking-wider">
                        Featured
                      </span>
                    )}
                  </div>

                  <div className="flex flex-wrap items-center gap-3 text-xs text-[#555555]">
                    <Link
                      to={`/projects/${encodeURIComponent(issue.project)}`}
                      className="text-[#555555] hover:text-[#111111] hover:underline font-mono"
                    >
                      {issue.project}
                    </Link>

                    {issue.difficulty && (
                      <span className="capitalize px-2.5 py-0.5 rounded-full bg-[#f4f4f1] border border-[#d8d8d3] text-[#555555]">
                        {issue.difficulty}
                      </span>
                    )}

                    {issue.category && (
                      <span className="capitalize px-2.5 py-0.5 rounded-full bg-[#f4f4f1] border border-[#d8d8d3] text-[#555555]">
                        {CATEGORY_LABEL_MAP[issue.category] || issue.category}
                      </span>
                    )}

                    <span
                      className={`capitalize px-2.5 py-0.5 rounded-full font-mono text-[11px] ${
                        issue.status === 'open'
                          ? 'text-[#22443d] bg-[#eef5f3] border border-[#c0d8d0]'
                          : 'text-[#777777] bg-[#f4f4f1] border border-[#d8d8d3]'
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
                          className="px-2 py-0.5 text-[11px] rounded bg-[#f4f4f1] border border-[#d8d8d3] text-[#555555] font-mono"
                        >
                          {label}
                        </span>
                      ))}
                    </div>
                  )}
                </div>

                <div className="flex sm:flex-col items-center sm:items-end justify-between gap-3 pt-3 sm:pt-0 border-t sm:border-t-0 border-[#d8d8d3]">
                  <div className="text-right">
                    <span className="text-lg font-bold text-[#ff5a1f] font-mono tabular-nums">
                      +{issue.points}
                    </span>
                    <span className="text-[10px] text-[#777777] block uppercase tracking-wider font-mono">
                      Points
                    </span>
                  </div>

                  <div className="flex items-center gap-2">
                    <Link
                      to={`/issues/${issue.id}`}
                      className="px-3.5 py-1.5 rounded-[4px] bg-transparent hover:bg-black/5 text-xs font-medium text-[#050505] transition-colors border border-[#050505] focus:outline-none focus-visible:ring-2 focus-visible:ring-[#ff5a1f]"
                    >
                      Details
                    </Link>
                    <a
                      href={issue.github_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="px-3.5 py-1.5 rounded-[4px] bg-[#050505] hover:bg-[#1a1a1a] text-xs font-medium text-white transition-colors flex items-center gap-1 shadow-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-[#ff5a1f]"
                    >
                      <span>GitHub</span>
                      <span className="text-[10px]">↗</span>
                    </a>
                  </div>
                </div>
              </div>
            ))}
          </div>

          {/* Pagination Controls */}
          <div className="flex flex-col sm:flex-row items-center justify-between gap-4 pt-4 border-t border-[#d8d8d3]">
            <span className="text-xs text-[#555555]">
              Page <span className="font-semibold text-[#111111]">{filters.page}</span> of{' '}
              <span className="font-semibold text-[#111111]">{totalPages}</span> (
              {data.count} total matching issues)
            </span>

            <div className="flex items-center space-x-2">
              <button
                type="button"
                onClick={() => setPage(Math.max(1, filters.page - 1))}
                disabled={filters.page <= 1 || isPlaceholderData}
                className="px-4 py-1.5 rounded-[4px] bg-white border border-[#d8d8d3] text-xs font-medium text-[#111111] hover:bg-[#f4f4f1] disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
              >
                Previous
              </button>
              <button
                type="button"
                onClick={() => setPage(filters.page + 1)}
                disabled={!data.next || filters.page >= totalPages || isPlaceholderData}
                className="px-4 py-1.5 rounded-[4px] bg-white border border-[#d8d8d3] text-xs font-medium text-[#111111] hover:bg-[#f4f4f1] disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
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
