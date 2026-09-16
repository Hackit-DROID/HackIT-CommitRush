import { Link, useParams } from 'react-router-dom';
import { useIssue } from '../api/issues';
import { ErrorState } from '../components/ErrorState';
import { IssueDetailSkeleton } from '../components/Skeletons';

export function IssueDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { data: issue, isLoading, isError, error, refetch } = useIssue(id);

  if (isLoading) {
    return <IssueDetailSkeleton />;
  }

  if (isError || !issue) {
    return (
      <div className="space-y-6">
        <Link
          to="/issues"
          className="inline-flex items-center text-xs text-slate-400 hover:text-white transition-colors"
        >
          ← Back to Issues
        </Link>
        <ErrorState error={error} onRetry={() => refetch()} />
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-4xl mx-auto" data-testid="issue-detail-view">
      {/* Top Breadcrumb */}
      <div className="flex items-center justify-between">
        <Link
          to="/issues"
          className="inline-flex items-center gap-1.5 text-xs font-medium text-slate-400 hover:text-cyan-400 transition-colors"
        >
          <span>←</span> Back to Issues Explorer
        </Link>
        <div className="flex items-center gap-2">
          {issue.is_featured && (
            <span className="bg-amber-950/80 border border-amber-800/60 text-amber-400 text-xs font-bold px-2.5 py-0.5 rounded-full uppercase tracking-wider">
              Featured
            </span>
          )}
          <span
            className={`text-xs font-medium px-2.5 py-0.5 rounded-full capitalize ${
              issue.status === 'open'
                ? 'bg-emerald-950/70 border border-emerald-800/60 text-emerald-400'
                : 'bg-slate-800 text-slate-400 border border-slate-700'
            }`}
          >
            Status: {issue.status}
          </span>
        </div>
      </div>

      {/* Main Issue Card */}
      <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-6 sm:p-8 space-y-6 shadow-sm">
        {/* Header and Title */}
        <div className="space-y-3">
          <div className="flex items-center gap-2 text-xs font-mono text-slate-400">
            <Link
              to={`/projects/${encodeURIComponent(issue.project)}`}
              className="text-cyan-400 hover:underline font-semibold"
            >
              {issue.project}
            </Link>
            <span>/</span>
            <span>Issue #{issue.github_number}</span>
          </div>

          <h1 className="text-2xl sm:text-3xl font-bold text-white tracking-tight leading-tight">
            {issue.title}
          </h1>
        </div>

        {/* Core Metadata Badges Grid */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 py-5 border-y border-slate-800/80 text-xs">
          <div className="space-y-1">
            <span className="text-slate-500 uppercase tracking-wider text-[10px] block font-semibold">
              Reward Points
            </span>
            <span className="text-xl font-extrabold text-cyan-400">
              +{issue.points} pts
            </span>
          </div>

          <div className="space-y-1">
            <span className="text-slate-500 uppercase tracking-wider text-[10px] block font-semibold">
              Difficulty
            </span>
            <span className="text-sm font-semibold text-slate-200 capitalize">
              {issue.difficulty || 'Unassigned'}
            </span>
          </div>

          <div className="space-y-1">
            <span className="text-slate-500 uppercase tracking-wider text-[10px] block font-semibold">
              Category
            </span>
            <span className="text-sm font-semibold text-slate-200 capitalize">
              {issue.category || 'General'}
            </span>
          </div>

          <div className="space-y-1">
            <span className="text-slate-500 uppercase tracking-wider text-[10px] block font-semibold">
              GitHub Issue ID
            </span>
            <span className="text-xs font-mono text-slate-400">
              {issue.github_issue_id}
            </span>
          </div>
        </div>

        {/* Labels Section */}
        {issue.labels && issue.labels.length > 0 && (
          <div className="space-y-2">
            <h2 className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
              Issue Labels
            </h2>
            <div className="flex flex-wrap gap-2">
              {issue.labels.map((label) => (
                <span
                  key={label}
                  className="px-3 py-1 rounded-lg bg-slate-800 border border-slate-700/60 text-xs font-mono text-slate-300 shadow-sm"
                >
                  {label}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Canonical GitHub Action */}
        <div className="pt-4 flex flex-col sm:flex-row items-center justify-between gap-4 bg-slate-950/60 border border-slate-800/80 rounded-xl p-4 sm:p-5">
          <div className="text-xs text-slate-400 text-center sm:text-left">
            Ready to solve this challenge? Open the canonical issue on GitHub to start working on a Pull Request.
          </div>
          <a
            href={issue.github_url}
            target="_blank"
            rel="noopener noreferrer"
            data-testid="canonical-github-link"
            className="w-full sm:w-auto inline-flex items-center justify-center gap-2 px-5 py-2.5 rounded-xl bg-cyan-600 hover:bg-cyan-500 text-white text-sm font-semibold shadow-lg shadow-cyan-600/25 transition-all focus:outline-none focus:ring-2 focus:ring-cyan-500"
          >
            <span>Open on GitHub</span>
            <span>↗</span>
          </a>
        </div>
      </div>
    </div>
  );
}
