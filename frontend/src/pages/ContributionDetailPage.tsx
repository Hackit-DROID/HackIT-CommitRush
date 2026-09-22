import { useParams, Link } from 'react-router-dom';
import { useContribution } from '../api/contributions';
import { ContributionStatusBadge, getContributionStatusMeta } from '../components/ContributionStatusBadge';
import { ErrorState } from '../components/ErrorState';
import { ContributionDetailSkeleton } from '../components/Skeletons';
import { useDocumentTitle } from '../hooks/useDocumentTitle';

const LIFECYCLE_STAGES = [
  { key: 'PENDING', label: 'Pending' },
  { key: 'QUEUED', label: 'Queued' },
  { key: 'UNDER_REVIEW', label: 'Validating' },
  { key: 'APPROVED', label: 'Approved' },
  { key: 'MERGING', label: 'Merging' },
  { key: 'MERGED', label: 'Merged' },
];

function getStageIndex(status: string | undefined): number {
  const norm = (status || '').toUpperCase().trim();
  switch (norm) {
    case 'PENDING':
      return 0;
    case 'QUEUED':
      return 1;
    case 'UNDER_REVIEW':
      return 2;
    case 'APPROVED':
      return 3;
    case 'MERGING':
      return 4;
    case 'MERGED':
      return 5;
    default:
      return -1;
  }
}

export function ContributionDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { data: contribution, isLoading, isError, error, refetch } = useContribution(id);

  useDocumentTitle(
    contribution ? `CommitRush — Contribution #${contribution.id}` : 'CommitRush — Contribution Details',
    'Track automated validation, merge queue status, and point rewards for your sprint contribution.'
  );

  if (isLoading) {
    return <ContributionDetailSkeleton />;
  }

  if (isError || !contribution) {
    return (
      <div className="max-w-4xl mx-auto space-y-4">
        <Link
          to="/profile?tab=contributions"
          className="inline-flex items-center gap-1.5 text-xs font-mono text-[#777777] hover:text-[#111111] transition-colors"
        >
          &larr; Back to My Contributions
        </Link>
        <ErrorState
          error={error}
          onRetry={() => refetch()}
          title="Contribution not found"
        />
      </div>
    );
  }

  const meta = getContributionStatusMeta(contribution.status, contribution.sub_status);
  const currentStageIdx = getStageIndex(contribution.status);
  const isTerminalNegative =
    contribution.status === 'REJECTED' ||
    contribution.status === 'FLAGGED' ||
    contribution.status === 'RETRY';

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* Breadcrumb Navigation */}
      <div className="flex items-center justify-between">
        <Link
          to="/profile?tab=contributions"
          className="inline-flex items-center gap-1.5 text-xs font-mono text-[#777777] hover:text-[#111111] transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-[#ff5a1f] rounded-sm"
        >
          &larr; Back to My Contributions
        </Link>

        <div className="flex items-center gap-2 text-xs font-mono text-[#777777]">
          <span>Contribution ID:</span>
          <span className="text-[#111111] font-semibold">#{contribution.id}</span>
        </div>
      </div>

      {/* Main Status Hero Card */}
      <div className="bg-white border border-[#d8d8d3] rounded-md p-6 sm:p-8 space-y-6 shadow-sm relative overflow-hidden">
        <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4 relative">
          <div className="space-y-2 flex-1 min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-xs font-mono font-medium text-[#111111] bg-[#f4f4f1] border border-[#d8d8d3] px-2.5 py-0.5 rounded-[4px] truncate max-w-[280px] sm:max-w-md">
                {contribution.pull_request?.repo || 'Repository'}
              </span>
              {contribution.issue?.points !== undefined && (
                <span className="text-xs px-2.5 py-0.5 rounded-[4px] bg-[#f4f4f1] text-[#111111] border border-[#d8d8d3] font-mono font-semibold tabular-nums">
                  {`${contribution.issue.points} Points`}
                </span>
              )}
            </div>

            <h1 className="text-xl sm:text-2xl font-bold text-[#111111] tracking-tight break-words">
              {contribution.issue?.title || `Contribution #${contribution.id}`}
            </h1>

            <p className="text-sm text-[#555555] font-sans break-words">
              PR #{contribution.pull_request?.number} authored by{' '}
              <span className="text-[#111111] font-medium font-mono">
                @{contribution.participant?.github_username || 'you'}
              </span>
            </p>
          </div>

          <div className="relative shrink-0">
            <ContributionStatusBadge
              status={contribution.status}
              subStatus={contribution.sub_status}
              size="lg"
            />
          </div>
        </div>

        {/* Status Explanation Box */}
        <div className="bg-[#f4f4f1] border border-[#d8d8d3] rounded-[4px] p-4 space-y-1 relative">
          <div className="text-xs font-mono font-semibold text-[#111111] uppercase tracking-wider">
            Current Status Explanation
          </div>
          <div className="text-sm text-[#555555] font-sans leading-relaxed">{meta.description}</div>
        </div>

        {/* Lifecycle Progress Flow */}
        {!isTerminalNegative && currentStageIdx >= 0 && (
          <div className="space-y-2 pt-2 border-t border-[#d8d8d3] relative">
            <div className="text-xs font-mono font-semibold text-[#777777] uppercase tracking-wider mb-3">
              Contribution Lifecycle
            </div>
            <div className="grid grid-cols-3 sm:grid-cols-6 gap-2">
              {LIFECYCLE_STAGES.map((stage, idx) => {
                const isPassed = idx < currentStageIdx;
                const isCurrent = idx === currentStageIdx;
                return (
                  <div
                    key={stage.key}
                    className={`text-center p-2.5 rounded-[4px] border text-xs font-medium font-mono transition-all min-w-0 ${
                      isCurrent
                        ? 'bg-[#050505] text-white border-[#050505] shadow-sm'
                        : isPassed
                        ? 'bg-[#f4f4f1] text-[#3d5f58] border-[#3d5f58]/30 font-semibold'
                        : 'bg-white text-[#777777] border-[#d8d8d3]'
                    }`}
                  >
                    <div className="text-[10px] font-mono text-[#777777] mb-0.5">
                      0{idx + 1}
                    </div>
                    <div className="truncate">{stage.label}</div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Flagged / Rejected Notice */}
        {contribution.flagged_reason && (
          <div className="bg-amber-50 border border-amber-200 rounded-[4px] p-4 space-y-1 text-xs font-mono relative">
            <div className="font-semibold text-amber-900 uppercase tracking-wider">
              Review Details
            </div>
            <div className="text-amber-800">{contribution.flagged_reason}</div>
          </div>
        )}
      </div>

      {/* Points Breakdown Section (Deliverable 8 & 9) */}
      {(() => {
        const breakdown = contribution.scoring_breakdown;
        const basePts = breakdown?.base_points ?? (contribution.issue?.points || 0);
        const categoryLabel = breakdown?.category_label || (contribution.issue?.category ? contribution.issue.category.charAt(0).toUpperCase() + contribution.issue.category.slice(1) : 'Feature');
        const multiplierText = breakdown ? `${breakdown.multiplier}×` : '1.0×';
        const calculatedPts = breakdown?.calculated_points ?? (contribution.issue?.points || 0);
        const pointsAwarded = breakdown ? breakdown.final_awarded_points : (contribution.status === 'MERGED' ? (contribution.issue?.points || 0) : 0);
        const capApplied = breakdown?.cap_applied || 'Not reached';

        return (
          <div
            className="bg-white border border-[#d8d8d3] rounded-md p-5 sm:p-6 space-y-4 shadow-sm"
            data-testid="scoring-breakdown-card"
          >
            <div className="flex items-center justify-between border-b border-[#d8d8d3] pb-3">
              <div className="flex items-center gap-2">
                <h2 className="text-sm font-mono font-semibold text-[#111111] uppercase tracking-wider">
                  Points Breakdown
                </h2>
                <span className="text-[10px] font-mono text-[#777777] bg-[#f4f4f1] px-2 py-0.5 rounded border border-[#d8d8d3]">
                  Authoritative
                </span>
              </div>
              <div className="font-mono text-sm font-bold text-[#ff5a1f] tabular-nums">
                {contribution.status === 'MERGED'
                  ? `${pointsAwarded} Points Awarded`
                  : `${calculatedPts} Points Potential`}
              </div>
            </div>

            {capApplied !== 'Not reached' && (
              <div className="flex items-center gap-2 p-3 bg-amber-50 border border-amber-200 rounded-[4px] text-xs font-mono text-amber-900">
                <span className="font-bold">Cap Notice:</span>
                <span>{capApplied} adjusted final reward to {pointsAwarded} points.</span>
              </div>
            )}

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs font-mono">
              <div className="space-y-2.5">
                <div className="flex items-center justify-between py-1 border-b border-[#f4f4f1]">
                  <span className="text-[#777777]">Base Points</span>
                  <span className="font-semibold text-[#111111] tabular-nums">{basePts}</span>
                </div>
                <div className="flex items-center justify-between py-1 border-b border-[#f4f4f1]">
                  <span className="text-[#777777]">Contribution</span>
                  <span className="font-semibold text-[#111111]">{categoryLabel}</span>
                </div>
                <div className="flex items-center justify-between py-1 border-b border-[#f4f4f1]">
                  <span className="text-[#777777]">Multiplier</span>
                  <span className="font-semibold text-[#111111]">{multiplierText}</span>
                </div>
              </div>

              <div className="space-y-2.5">
                <div className="flex items-center justify-between py-1 border-b border-[#f4f4f1]">
                  <span className="text-[#777777]">Calculated Points</span>
                  <span className="font-semibold text-[#111111] tabular-nums">{calculatedPts}</span>
                </div>
                <div className="flex items-center justify-between py-1 border-b border-[#f4f4f1]">
                  <span className="text-[#777777]">Points Awarded</span>
                  <span className="font-bold text-[#ff5a1f] text-sm tabular-nums">{pointsAwarded}</span>
                </div>
                <div className="flex items-center justify-between py-1 border-b border-[#f4f4f1]">
                  <span className="text-[#777777]">Cap Applied</span>
                  <span className={`font-semibold ${capApplied !== 'Not reached' ? 'text-amber-700' : 'text-[#555555]'}`}>
                    {capApplied}
                  </span>
                </div>
              </div>
            </div>
          </div>
        );
      })()}

      {/* Linked Resources Section */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-5">

        {/* Linked Issue Card */}
        <div className="bg-white border border-[#d8d8d3] rounded-md p-5 sm:p-6 space-y-3 shadow-sm">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-mono font-semibold text-[#111111] uppercase tracking-wider">
              Linked Issue
            </h2>
            {contribution.issue?.status && (
              <span className="text-xs font-mono uppercase text-[#777777]">
                Status: {contribution.issue.status}
              </span>
            )}
          </div>

          {contribution.issue ? (
            <div className="space-y-2 text-xs">
              <div className="text-sm font-medium text-[#111111] font-sans break-words">
                {contribution.issue.title}
              </div>
              <div className="text-[#777777] font-mono">
                Issue #{contribution.issue.github_number} &bull; <span className="tabular-nums">{contribution.issue.points}</span> pts &bull;{' '}
                {contribution.issue.difficulty || 'standard'} &bull;{' '}
                {contribution.issue.category || 'general'}
              </div>
              <div className="pt-2 flex items-center gap-3 flex-wrap">
                {contribution.issue.github_url && (
                  <a
                    href={contribution.issue.github_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-[#ff5a1f] hover:underline font-mono font-medium inline-flex items-center gap-1 transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-[#ff5a1f] rounded-sm"
                  >
                    <span>View Issue on GitHub</span>
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
                  to={`/issues/${contribution.issue.id}`}
                  className="text-[#777777] hover:text-[#111111] font-mono transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-[#ff5a1f] rounded-sm"
                >
                  Internal Details &rarr;
                </Link>
              </div>
            </div>
          ) : (
            <div className="text-xs text-[#777777] font-mono">No issue information available.</div>
          )}
        </div>

        {/* Pull Request Card */}
        <div className="bg-white border border-[#d8d8d3] rounded-md p-5 sm:p-6 space-y-3 shadow-sm min-w-0">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-mono font-semibold text-[#111111] uppercase tracking-wider">
              Pull Request
            </h2>
            {contribution.pull_request?.merged ? (
              <span className="text-xs px-2.5 py-0.5 rounded-[4px] bg-emerald-50 text-emerald-800 border border-emerald-200 font-mono">
                Merged on GitHub
              </span>
            ) : (
              <span className="text-xs px-2.5 py-0.5 rounded-[4px] bg-[#f4f4f1] text-[#777777] border border-[#d8d8d3] font-mono">
                Open / Unmerged
              </span>
            )}
          </div>

          {contribution.pull_request ? (
            <div className="space-y-2 text-xs font-mono">
              <div className="text-sm font-medium text-[#111111] break-all">
                PR #{contribution.pull_request.number} &bull; {contribution.pull_request.repo}
              </div>
              {contribution.pull_request.head_sha && (
                <div className="text-[#777777] text-[11px] font-mono">
                  Head SHA: {contribution.pull_request.head_sha.substring(0, 10)}
                </div>
              )}
              <div className="pt-2">
                {contribution.pull_request.github_url && (
                  <a
                    href={contribution.pull_request.github_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-[#ff5a1f] hover:underline font-medium inline-flex items-center gap-1 transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-[#ff5a1f] rounded-sm"
                  >
                    <span>View PR on GitHub</span>
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
              </div>
            </div>
          ) : (
            <div className="text-xs text-[#777777] font-mono">No pull request information available.</div>
          )}
        </div>
      </div>

      {/* Timestamps & Audit Info */}
      <div className="bg-white border border-[#d8d8d3] rounded-md p-4 text-xs font-mono text-[#777777] flex flex-wrap items-center justify-between gap-4 shadow-sm">
        <div>
          <span>Created: </span>
          <span className="text-[#111111]">
            {new Date(contribution.created_at).toLocaleString()}
          </span>
        </div>
        {contribution.approved_at && (
          <div>
            <span>Approved: </span>
            <span className="text-[#111111]">
              {new Date(contribution.approved_at).toLocaleString()}
            </span>
          </div>
        )}
        {contribution.merged_at && (
          <div>
            <span>Merged: </span>
            <span className="text-[#111111]">
              {new Date(contribution.merged_at).toLocaleString()}
            </span>
          </div>
        )}
        {contribution.retry_count > 0 && (
          <div>
            <span>Validation Retries: </span>
            <span className="text-[#ff5a1f] font-semibold">
              {contribution.retry_count}
            </span>
          </div>
        )}
      </div>
    </div>
  );
}
