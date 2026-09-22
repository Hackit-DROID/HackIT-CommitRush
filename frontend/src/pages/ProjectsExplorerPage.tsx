import { useState, useMemo } from 'react';
import { Link } from 'react-router-dom';
import { useMonorepoProjects, MonorepoProject } from '../api/github';
import { EmptyState } from '../components/EmptyState';
import { ErrorState } from '../components/ErrorState';
import { ProjectsListSkeleton } from '../components/Skeletons';
import { useDocumentTitle } from '../hooks/useDocumentTitle';

const CATEGORY_COLORS: Record<string, { bg: string; border: string; text: string }> = {
  'AI & Automation': { bg: 'bg-purple-50', border: 'border-purple-200', text: 'text-purple-700' },
  'Deep Learning & CV': { bg: 'bg-blue-50', border: 'border-blue-200', text: 'text-blue-700' },
  'Campus & Academic MIS': { bg: 'bg-emerald-50', border: 'border-emerald-200', text: 'text-emerald-700' },
  'Data Visualization': { bg: 'bg-amber-50', border: 'border-amber-200', text: 'text-amber-700' },
  'Enterprise Applications': { bg: 'bg-rose-50', border: 'border-rose-200', text: 'text-rose-700' },
  General: { bg: 'bg-[#f4f4f1]', border: 'border-[#d8d8d3]', text: 'text-[#555555]' },
};

const ITEMS_PER_PAGE = 12;

export function ProjectsExplorerPage() {
  useDocumentTitle(
    'CommitRush 2026 — Projects',
    'Browse real open-source projects from the HackIT Commit Rush monorepo.'
  );

  const [searchInput, setSearchInput] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [categoryFilter, setCategoryFilter] = useState('');
  const [page, setPage] = useState(1);

  const { data: projects, isLoading, isError, error, refetch } = useMonorepoProjects();

  // Derive unique categories from the data
  const categories = useMemo(() => {
    if (!projects) return [];
    const cats = new Set(projects.map((p) => p.category));
    return Array.from(cats).sort();
  }, [projects]);

  // Filter projects
  const filtered = useMemo(() => {
    if (!projects) return [];
    return projects.filter((p) => {
      const matchesSearch =
        !searchQuery ||
        p.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        p.baseName.toLowerCase().includes(searchQuery.toLowerCase());
      const matchesCategory = !categoryFilter || p.category === categoryFilter;
      return matchesSearch && matchesCategory;
    });
  }, [projects, searchQuery, categoryFilter]);

  // Pagination
  const totalPages = Math.max(1, Math.ceil(filtered.length / ITEMS_PER_PAGE));
  const paginated = filtered.slice((page - 1) * ITEMS_PER_PAGE, page * ITEMS_PER_PAGE);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setSearchQuery(searchInput.trim());
    setPage(1);
  };

  const handleResetFilters = () => {
    setSearchInput('');
    setSearchQuery('');
    setCategoryFilter('');
    setPage(1);
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-[#d8d8d3] pb-6">
        <div>
          <h1 className="text-2xl sm:text-3xl font-display font-bold tracking-tight text-[#111111]">
            Projects Explorer
          </h1>
          <p className="text-sm text-[#555555] mt-1">
            Browse <span className="font-semibold text-[#111111]">67 real projects</span> from the{' '}
            <a
              href="https://github.com/Hackit-DROID/Open-Source-Contribution-Drive"
              target="_blank"
              rel="noopener noreferrer"
              className="text-[#ff5a1f] hover:underline"
            >
              Open Source Contribution Drive
            </a>{' '}
            monorepo.
          </p>
        </div>
        {projects && (
          <div className="text-xs font-mono px-3.5 py-1.5 bg-white border border-[#d8d8d3] rounded-full text-[#555555] self-start md:self-auto shadow-sm">
            Total Projects: <span className="text-[#ff5a1f] font-semibold">{projects.length}</span>
            {searchQuery || categoryFilter ? (
              <>
                {' '}
                · Showing: <span className="text-[#111111] font-semibold">{filtered.length}</span>
              </>
            ) : null}
          </div>
        )}
      </div>

      {/* Filter Controls */}
      <div className="bg-white border border-[#d8d8d3] rounded-md p-4 sm:p-5 shadow-sm space-y-4">
        <form onSubmit={handleSearchSubmit} className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3.5">
          {/* Search */}
          <div className="lg:col-span-2 relative">
            <input
              type="text"
              aria-label="Search project name"
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              placeholder="Search project name..."
              className="w-full bg-[#f4f4f1] border border-[#d8d8d3] rounded-[4px] px-4 py-2.5 text-sm text-[#111111] placeholder-[#777777] focus:outline-none focus:border-[#111111] focus:ring-1 focus:ring-[#111111] transition-all"
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
                className="absolute right-3 top-3 text-[#777777] hover:text-[#111111] text-xs cursor-pointer"
              >
                Clear
              </button>
            )}
          </div>

          {/* Category Filter */}
          <div>
            <select
              aria-label="Filter by project category"
              value={categoryFilter}
              onChange={(e) => {
                setCategoryFilter(e.target.value);
                setPage(1);
              }}
              className="w-full bg-[#f4f4f1] border border-[#d8d8d3] rounded-[4px] px-4 py-2.5 text-sm text-[#111111] focus:outline-none focus:border-[#111111] focus:ring-1 focus:ring-[#111111] transition-all cursor-pointer"
            >
              <option value="">Category: All</option>
              {categories.map((cat) => (
                <option key={cat} value={cat}>
                  {cat}
                </option>
              ))}
            </select>
          </div>
        </form>

        {/* Active Filter Tags */}
        {(searchQuery || categoryFilter) && (
          <div className="flex flex-wrap items-center gap-2 pt-2 border-t border-[#d8d8d3] text-xs text-[#555555]">
            <span>Active filters:</span>
            {searchQuery && (
              <span className="bg-[#f4f4f1] text-[#111111] px-2.5 py-1 rounded-full border border-[#d8d8d3] flex items-center gap-1.5">
                Query: "{searchQuery}"
              </span>
            )}
            {categoryFilter && (
              <span className="bg-[#f4f4f1] text-[#111111] px-2.5 py-1 rounded-full border border-[#d8d8d3] flex items-center gap-1.5">
                {categoryFilter}
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

      {/* Main Content Area */}
      {isLoading ? (
        <ProjectsListSkeleton />
      ) : isError ? (
        <ErrorState error={error} onRetry={() => refetch()} />
      ) : filtered.length === 0 ? (
        <EmptyState
          title="No projects found"
          message="We could not find any projects matching your current filters."
          actionLabel="Reset filters"
          onAction={handleResetFilters}
        />
      ) : (
        <div className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5" data-testid="projects-list">
            {paginated.map((project) => (
              <ProjectCard key={project.baseName} project={project} />
            ))}
          </div>

          {/* Pagination Controls */}
          <div className="flex flex-col sm:flex-row items-center justify-between gap-4 pt-4 border-t border-[#d8d8d3]">
            <span className="text-xs text-[#555555] font-mono">
              Page <span className="font-semibold text-[#111111] tabular-nums">{page}</span> of{' '}
              <span className="font-semibold text-[#111111] tabular-nums">{totalPages}</span> (
              <span className="tabular-nums">{filtered.length}</span> projects)
            </span>

            <div className="flex items-center space-x-2">
              <button
                type="button"
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page <= 1}
                className="px-4 py-1.5 rounded-[4px] bg-white border border-[#d8d8d3] text-xs font-medium text-[#111111] hover:bg-[#f4f4f1] disabled:opacity-40 disabled:cursor-not-allowed transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-[#ff5a1f]"
              >
                Previous
              </button>
              <button
                type="button"
                onClick={() => setPage((p) => p + 1)}
                disabled={page >= totalPages}
                className="px-4 py-1.5 rounded-[4px] bg-white border border-[#d8d8d3] text-xs font-medium text-[#111111] hover:bg-[#f4f4f1] disabled:opacity-40 disabled:cursor-not-allowed transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-[#ff5a1f]"
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

// ---------------------------------------------------------------------------
// ProjectCard sub-component
// ---------------------------------------------------------------------------

function ProjectCard({ project }: { project: MonorepoProject }) {
  const colors = CATEGORY_COLORS[project.category] || CATEGORY_COLORS['General'];

  return (
    <Link
      to={`/projects/${encodeURIComponent(project.variants[0])}`}
      className="group bg-white hover:bg-[#fafaf8] border border-[#d8d8d3] hover:border-[#111111] rounded-md p-5 transition-all duration-200 flex flex-col justify-between shadow-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-[#ff5a1f]"
    >
      <div className="space-y-3">
        <div className="flex items-start justify-between gap-2">
          <h2 className="font-semibold text-[#111111] group-hover:text-[#ff5a1f] transition-colors line-clamp-2 break-words">
            {project.name}
          </h2>
          <span
            className={`text-[11px] font-mono font-medium px-2.5 py-0.5 rounded-full whitespace-nowrap ${colors.bg} ${colors.border} ${colors.text} border`}
          >
            {project.category}
          </span>
        </div>

        {project.variantCount > 1 && (
          <p className="text-xs text-[#555555]">
            <span className="font-mono font-semibold text-[#111111]">{project.variantCount}</span>{' '}
            variant{project.variantCount !== 1 ? 's' : ''} in the monorepo
          </p>
        )}
      </div>

      <div className="pt-4 mt-4 flex items-center justify-between border-t border-[#d8d8d3] text-xs text-[#777777]">
        <span className="flex items-center gap-1.5 font-mono text-[#555555]">
          <span className="w-2 h-2 rounded-full bg-[#ff5a1f]" />
          {project.baseName.split('_').slice(0, 2).join(' ')}
        </span>
        <span className="text-[#555555] group-hover:text-[#111111] group-hover:translate-x-0.5 transition-all">
          View Details →
        </span>
      </div>
    </Link>
  );
}
