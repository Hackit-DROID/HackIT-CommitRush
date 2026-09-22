import { Link, useParams } from 'react-router-dom';
import { useIssue } from '../api/issues';
import { ErrorState } from '../components/ErrorState';
import { IssueDetailSkeleton } from '../components/Skeletons';
import { useDocumentTitle } from '../hooks/useDocumentTitle';

export function IssueDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { data: issue, isLoading, isError, error, refetch } = useIssue(id);

  useDocumentTitle(
    issue ? `CommitRush 2026 — Issue #${issue.github_number}: ${issue.title}` : 'CommitRush 2026 — Issue Details',
    issue
      ? `View details and bounties for issue #${issue.github_number} (${issue.title}) on CommitRush.`
      : 'View open-source issue details and reward points on CommitRush.'
  );

  if (isLoading) {
    return <IssueDetailSkeleton />;
  }

  if (isError || !issue) {
    return (
      <div className="space-y-6">
        <Link
          to="/issues"
          className="inline-flex items-center text-xs text-[#555555] hover:text-[#111111] transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-[#ff5a1f] rounded-sm"
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
          className="inline-flex items-center gap-1.5 text-xs font-medium text-[#555555] hover:text-[#111111] transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-[#ff5a1f] rounded-sm"
        >
          <span>←</span> Back to Issues Explorer
        </Link>
        <div className="flex items-center gap-2 font-mono">
          {issue.is_featured && (
            <span className="bg-orange-50 border border-orange-200 text-[#ff5a1f] text-xs font-bold px-3 py-0.5 rounded-full uppercase tracking-wider">
              Featured
            </span>
          )}
          <span
            className={`text-xs font-medium px-3 py-0.5 rounded-full capitalize ${
              issue.status === 'open'
                ? 'bg-[#eef5f3] border border-[#c0d8d0] text-[#22443d]'
                : 'bg-[#f4f4f1] text-[#777777] border border-[#d8d8d3]'
            }`}
          >
            Status: {issue.status}
          </span>
        </div>
      </div>

      {/* Main Issue Card */}
      <div className="bg-white border border-[#d8d8d3] rounded-md p-6 sm:p-8 space-y-6 shadow-sm">
        {/* Header and Title */}
        <div className="space-y-3">
          <div className="flex items-center gap-2 text-xs font-mono text-[#555555] flex-wrap">
            <Link
              to={`/projects/${encodeURIComponent(issue.project)}`}
              className="text-[#ff5a1f] hover:underline font-semibold focus:outline-none focus-visible:ring-2 focus-visible:ring-[#ff5a1f] rounded-sm"
            >
              {issue.project}
            </Link>
            <span>/</span>
            <span>Issue #{issue.github_number}</span>
          </div>

          <h1 className="text-xl sm:text-3xl font-display font-bold text-[#111111] tracking-tight leading-tight break-words">
            {issue.title}
          </h1>
        </div>

        {/* Core Metadata Badges Grid */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 py-5 border-y border-[#d8d8d3] text-xs">
          <div className="space-y-1">
            <span className="text-[#777777] uppercase tracking-wider text-[10px] block font-mono font-semibold">
              Reward Points
            </span>
            <span className="text-xl font-extrabold text-[#ff5a1f] font-mono tabular-nums">
              +{issue.points} pts
            </span>
          </div>

          <div className="space-y-1">
            <span className="text-[#777777] uppercase tracking-wider text-[10px] block font-mono font-semibold">
              Difficulty
            </span>
            <span className="text-sm font-semibold text-[#111111] capitalize">
              {issue.difficulty || 'Unassigned'}
            </span>
          </div>

          <div className="space-y-1">
            <span className="text-[#777777] uppercase tracking-wider text-[10px] block font-mono font-semibold">
              Category
            </span>
            <span className="text-sm font-semibold text-[#111111] capitalize">
              {issue.category || 'General'}
            </span>
          </div>

          <div className="space-y-1">
            <span className="text-[#777777] uppercase tracking-wider text-[10px] block font-mono font-semibold">
              GitHub Issue ID
            </span>
            <span className="text-xs font-mono text-[#555555]">
              {issue.github_issue_id}
            </span>
          </div>
        </div>

        {/* Labels Section */}
        {issue.labels && issue.labels.length > 0 && (
          <div className="space-y-2">
            <h2 className="text-xs font-semibold text-[#777777] font-mono uppercase tracking-wider">
              Issue Labels
            </h2>
            <div className="flex flex-wrap gap-2">
              {issue.labels.map((label) => (
                <span
                  key={label}
                  className="px-3 py-1 rounded-full bg-[#f4f4f1] border border-[#d8d8d3] text-xs font-mono text-[#555555]"
                >
                  {label}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Canonical GitHub Action */}
        <div className="pt-4 flex flex-col sm:flex-row items-center justify-between gap-4 bg-[#f4f4f1] border border-[#d8d8d3] rounded-md p-5">
          <div className="text-xs text-[#555555] text-center sm:text-left">
            Ready to solve this challenge? Open the canonical issue on GitHub to start working on a Pull Request.
          </div>
          <a
            href={issue.github_url}
            target="_blank"
            rel="noopener noreferrer"
            data-testid="canonical-github-link"
            className="w-full sm:w-auto inline-flex items-center justify-center gap-2 px-6 py-2.5 rounded-[4px] bg-[#050505] hover:bg-[#1a1a1a] text-white text-sm font-semibold shadow-sm transition-all focus:outline-none focus-visible:ring-2 focus-visible:ring-[#ff5a1f]"
          >
            <span>Open on GitHub</span>
            <span>↗</span>
          </a>
        </div>
      </div>
    </div>
  );
}
