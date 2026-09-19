import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useProjects } from '../api/projects';
import { EmptyState } from '../components/EmptyState';
import { ErrorState } from '../components/ErrorState';
import { ProjectsListSkeleton } from '../components/Skeletons';
import { useDocumentTitle } from '../hooks/useDocumentTitle';

export function ProjectsExplorerPage() {
  useDocumentTitle(
    'CommitRush — Projects',
    'Browse and explore active open-source repositories tracked in CommitRush.'
  );

  const [searchInput, setSearchInput] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [language, setLanguage] = useState('');
  const [enabledFilter, setEnabledFilter] = useState<'all' | 'true' | 'false'>('all');
  const [page, setPage] = useState(1);

  const filters = {
    search: searchQuery || undefined,
    language: language || undefined,
    enabled: enabledFilter === 'all' ? undefined : enabledFilter === 'true',
    page,
    page_size: 12,
  };

  const { data, isLoading, isError, error, refetch, isPlaceholderData } = useProjects(filters);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setSearchQuery(searchInput.trim());
    setPage(1);
  };

  const handleResetFilters = () => {
    setSearchInput('');
    setSearchQuery('');
    setLanguage('');
    setEnabledFilter('all');
    setPage(1);
  };

  const totalPages = data ? Math.max(1, Math.ceil(data.count / 12)) : 1;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-800/80 pb-6">
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-white">
            Projects Explorer
          </h1>
          <p className="text-sm text-slate-400 mt-1">
            Browse and explore active open source repositories tracked in CommitRush.
          </p>
        </div>
        {data && (
          <div className="text-xs font-mono px-3 py-1.5 bg-slate-900 border border-slate-800 rounded-lg text-slate-400 self-start md:self-auto">
            Total Tracked: <span className="text-cyan-400 font-semibold">{data.count}</span>
          </div>
        )}
      </div>

      {/* Filter Controls */}
      <div className="bg-slate-900/50 border border-slate-800/80 rounded-2xl p-4 sm:p-5 shadow-sm space-y-4">
        <form onSubmit={handleSearchSubmit} className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3.5">
          {/* Search */}
          <div className="lg:col-span-2 relative">
            <input
              type="text"
              aria-label="Search repository name or description"
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              placeholder="Search repo name or description..."
              className="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-2.5 text-sm text-slate-200 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-cyan-500 focus:border-transparent transition-all"
            />
            {searchInput && (
              <button
                type="button"
                aria-label="Clear search query"
                onClick={() => {
                  setSearchInput('');
                  setSearchQuery('');
                  setPage(1);
                }}
                className="absolute right-3 top-3 text-slate-500 hover:text-slate-300 text-xs cursor-pointer"
              >
                Clear
              </button>
            )}
          </div>

          {/* Language Filter */}
          <div>
            <input
              type="text"
              aria-label="Filter by programming language"
              value={language}
              onChange={(e) => {
                setLanguage(e.target.value);
                setPage(1);
              }}
              placeholder="Language (e.g. Python, TypeScript)"
              className="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-2.5 text-sm text-slate-200 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-cyan-500 focus:border-transparent transition-all"
            />
          </div>

          {/* Enabled Status Filter */}
          <div>
            <select
              aria-label="Filter by repository active status"
              value={enabledFilter}
              onChange={(e) => {
                setEnabledFilter(e.target.value as 'all' | 'true' | 'false');
                setPage(1);
              }}
              className="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-2.5 text-sm text-slate-200 focus:outline-none focus:ring-2 focus:ring-cyan-500 focus:border-transparent transition-all"
            >
              <option value="all">Status: All Projects</option>
              <option value="true">Active / Enabled Only</option>
              <option value="false">Disabled Only</option>
            </select>
          </div>
        </form>

        {/* Active Filter Tags */}
        {(searchQuery || language || enabledFilter !== 'all') && (
          <div className="flex flex-wrap items-center gap-2 pt-2 border-t border-slate-800/40 text-xs text-slate-400">
            <span>Active filters:</span>
            {searchQuery && (
              <span className="bg-slate-800 text-cyan-400 px-2.5 py-1 rounded-md border border-slate-700/60 flex items-center gap-1.5">
                Query: "{searchQuery}"
              </span>
            )}
            {language && (
              <span className="bg-slate-800 text-cyan-400 px-2.5 py-1 rounded-md border border-slate-700/60 flex items-center gap-1.5">
                Lang: {language}
              </span>
            )}
            {enabledFilter !== 'all' && (
              <span className="bg-slate-800 text-cyan-400 px-2.5 py-1 rounded-md border border-slate-700/60 flex items-center gap-1.5">
                {enabledFilter === 'true' ? 'Enabled' : 'Disabled'}
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

      {/* Main Content Area */}
      {isLoading ? (
        <ProjectsListSkeleton />
      ) : isError ? (
        <ErrorState error={error} onRetry={() => refetch()} />
      ) : !data || data.results.length === 0 ? (
        <EmptyState
          title="No projects found"
          message="We could not find any tracked repositories matching your current filters."
          actionLabel="Reset filters"
          onAction={handleResetFilters}
        />
      ) : (
        <div className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5" data-testid="projects-list">
            {data.results.map((project) => {
              // Convert full_name owner/repo into hyphenated or direct URL-safe slug
              const projectSlug = encodeURIComponent(project.full_name);

              return (
                <Link
                  key={project.id}
                  to={`/projects/${projectSlug}`}
                  className="group bg-slate-900/60 hover:bg-slate-850 border border-slate-800 hover:border-slate-700 rounded-xl p-5 transition-all duration-200 flex flex-col justify-between shadow-sm hover:shadow-md hover:shadow-cyan-950/20"
                >
                  <div className="space-y-3">
                    <div className="flex items-start justify-between gap-2">
                      <h2 className="font-semibold text-white group-hover:text-cyan-400 transition-colors line-clamp-1">
                        {project.full_name}
                      </h2>
                      <span
                        className={`text-[11px] font-medium px-2 py-0.5 rounded-full whitespace-nowrap ${
                          project.is_enabled
                            ? 'bg-emerald-950/70 border border-emerald-800/60 text-emerald-400'
                            : 'bg-slate-800 text-slate-400 border border-slate-700'
                        }`}
                      >
                        {project.is_enabled ? 'Active' : 'Disabled'}
                      </span>
                    </div>

                    <p className="text-xs text-slate-400 line-clamp-2 leading-relaxed">
                      {project.description || 'No description provided for this repository.'}
                    </p>
                  </div>

                  <div className="pt-4 mt-4 flex items-center justify-between border-t border-slate-800/60 text-xs text-slate-400">
                    <span className="flex items-center gap-1.5">
                      <span className="w-2 h-2 rounded-full bg-cyan-400" />
                      {project.language || 'General'}
                    </span>
                    <span className="text-cyan-500 group-hover:translate-x-0.5 transition-transform">
                      View Details →
                    </span>
                  </div>
                </Link>
              );
            })}
          </div>

          {/* Pagination Controls */}
          <div className="flex flex-col sm:flex-row items-center justify-between gap-4 pt-4 border-t border-slate-800/80">
            <span className="text-xs text-slate-400">
              Page <span className="font-semibold text-white">{page}</span> of{' '}
              <span className="font-semibold text-white">{totalPages}</span> (
              {data.count} total items)
            </span>

            <div className="flex items-center space-x-2">
              <button
                type="button"
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page <= 1 || isPlaceholderData}
                className="px-3.5 py-1.5 rounded-lg bg-slate-900 border border-slate-800 text-xs font-medium text-slate-300 hover:bg-slate-800 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
              >
                Previous
              </button>
              <button
                type="button"
                onClick={() => setPage((p) => p + 1)}
                disabled={!data.next || page >= totalPages || isPlaceholderData}
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
