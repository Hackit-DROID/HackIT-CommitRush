import { useParams, Link } from 'react-router-dom';
import { useContribution } from '../api/contributions';
import { ContributionStatusBadge, getContributionStatusMeta } from '../components/ContributionStatusBadge';
import { ErrorState } from '../components/ErrorState';
import { ContributionDetailSkeleton } from '../components/Skeletons';

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

  if (isLoading) {
    return <ContributionDetailSkeleton />;
  }

  if (isError || !contribution) {
    return (
      <div className="max-w-4xl mx-auto space-y-4">
        <Link
          to="/contributions"
          className="inline-flex items-center gap-1.5 text-xs text-slate-400 hover:text-cyan-400 transition-colors"
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
          to="/contributions"
          className="inline-flex items-center gap-1.5 text-xs text-slate-400 hover:text-cyan-400 transition-colors"
        >
          &larr; Back to My Contributions
        </Link>

        <div className="flex items-center gap-2 text-xs text-slate-400">
          <span>Contribution ID:</span>
          <span className="font-mono text-slate-300 font-semibold">#{contribution.id}</span>
        </div>
      </div>

      {/* Main Status Hero Card */}
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 sm:p-8 space-y-6">
        <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4">
          <div className="space-y-2 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-xs font-mono font-medium text-slate-400 bg-slate-800 px-2 py-0.5 rounded">
                {contribution.pull_request?.repo || 'Repository'}
              </span>
              {contribution.issue?.points !== undefined && (
                <span className="text-xs px-2 py-0.5 rounded bg-cyan-950 text-cyan-300 border border-cyan-800 font-mono font-semibold">
                  {`${contribution.issue.points} Points`}
                </span>
              )}
            </div>

            <h1 className="text-xl sm:text-2xl font-bold text-white tracking-tight">
              {contribution.issue?.title || `Contribution #${contribution.id}`}
            </h1>

            <p className="text-sm text-slate-400">
              PR #{contribution.pull_request?.number} authored by{' '}
              <span className="text-slate-200 font-medium font-mono">
                @{contribution.participant?.github_username || 'you'}
              </span>
            </p>
          </div>

          <div>
            <ContributionStatusBadge
              status={contribution.status}
              subStatus={contribution.sub_status}
              size="lg"
            />
          </div>
        </div>

        {/* Status Explanation Box */}
        <div className="bg-slate-950/80 border border-slate-800 rounded-xl p-4 space-y-1">
          <div className="text-xs font-semibold text-cyan-400 uppercase tracking-wider">
            Current Status Explanation
          </div>
          <div className="text-sm text-slate-300">{meta.description}</div>
        </div>

        {/* Lifecycle Progress Flow */}
        {!isTerminalNegative && currentStageIdx >= 0 && (
          <div className="space-y-2 pt-2 border-t border-slate-800/80">
            <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">
              Contribution Lifecycle
            </div>
            <div className="grid grid-cols-3 sm:grid-cols-6 gap-2">
              {LIFECYCLE_STAGES.map((stage, idx) => {
                const isPassed = idx < currentStageIdx;
                const isCurrent = idx === currentStageIdx;
                return (
                  <div
                    key={stage.key}
                    className={`text-center p-2 rounded-lg border text-xs font-medium transition-all ${
                      isCurrent
                        ? 'bg-cyan-950/80 text-cyan-300 border-cyan-600 shadow-sm'
                        : isPassed
                        ? 'bg-slate-950 text-emerald-400 border-emerald-900/60'
                        : 'bg-slate-950/40 text-slate-600 border-slate-800/60'
                    }`}
                  >
                    <div className="text-[10px] font-mono text-slate-500 mb-0.5">
                      0{idx + 1}
                    </div>
                    <div>{stage.label}</div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Flagged / Rejected Notice */}
        {contribution.flagged_reason && (
          <div className="bg-amber-950/40 border border-amber-800/60 rounded-xl p-4 space-y-1 text-xs">
            <div className="font-semibold text-amber-300 uppercase tracking-wider">
              Review Details
            </div>
            <div className="text-amber-200">{contribution.flagged_reason}</div>
          </div>
        )}
      </div>

      {/* Linked Resources Section */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
        {/* Linked Issue Card */}
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold text-white uppercase tracking-wider">
              Linked Issue
            </h2>
            {contribution.issue?.status && (
              <span className="text-xs font-mono uppercase text-slate-400">
                Status: {contribution.issue.status}
              </span>
            )}
          </div>

          {contribution.issue ? (
            <div className="space-y-2 text-xs">
              <div className="text-sm font-medium text-slate-200">
                {contribution.issue.title}
              </div>
              <div className="text-slate-400">
                Issue #{contribution.issue.github_number} &bull; {contribution.issue.points} pts &bull;{' '}
                {contribution.issue.difficulty || 'standard'} &bull;{' '}
                {contribution.issue.category || 'general'}
              </div>
              <div className="pt-2 flex items-center gap-3">
                {contribution.issue.github_url && (
                  <a
                    href={contribution.issue.github_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-cyan-400 hover:text-cyan-300 font-medium inline-flex items-center gap-1"
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
                  className="text-slate-400 hover:text-slate-200"
                >
                  Internal Details &rarr;
                </Link>
              </div>
            </div>
          ) : (
            <div className="text-xs text-slate-500">No issue information available.</div>
          )}
        </div>

        {/* Pull Request Card */}
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold text-white uppercase tracking-wider">
              Pull Request
            </h2>
            {contribution.pull_request?.merged ? (
              <span className="text-xs px-2 py-0.5 rounded bg-emerald-950 text-emerald-300 border border-emerald-800 font-mono">
                Merged on GitHub
              </span>
            ) : (
              <span className="text-xs px-2 py-0.5 rounded bg-slate-800 text-slate-400 border border-slate-700 font-mono">
                Open / Unmerged
              </span>
            )}
          </div>

          {contribution.pull_request ? (
            <div className="space-y-2 text-xs">
              <div className="text-sm font-medium text-slate-200">
                PR #{contribution.pull_request.number} &bull; {contribution.pull_request.repo}
              </div>
              {contribution.pull_request.head_sha && (
                <div className="text-slate-400 font-mono text-[11px]">
                  Head SHA: {contribution.pull_request.head_sha.substring(0, 10)}
                </div>
              )}
              <div className="pt-2">
                {contribution.pull_request.github_url && (
                  <a
                    href={contribution.pull_request.github_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-cyan-400 hover:text-cyan-300 font-medium inline-flex items-center gap-1"
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
            <div className="text-xs text-slate-500">No pull request information available.</div>
          )}
        </div>
      </div>

      {/* Timestamps & Audit Info */}
      <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-4 text-xs text-slate-400 flex flex-wrap items-center justify-between gap-4">
        <div>
          <span>Created: </span>
          <span className="text-slate-300">
            {new Date(contribution.created_at).toLocaleString()}
          </span>
        </div>
        {contribution.approved_at && (
          <div>
            <span>Approved: </span>
            <span className="text-slate-300">
              {new Date(contribution.approved_at).toLocaleString()}
            </span>
          </div>
        )}
        {contribution.merged_at && (
          <div>
            <span>Merged: </span>
            <span className="text-slate-300">
              {new Date(contribution.merged_at).toLocaleString()}
            </span>
          </div>
        )}
        {contribution.retry_count > 0 && (
          <div>
            <span>Validation Retries: </span>
            <span className="text-orange-400 font-mono font-semibold">
              {contribution.retry_count}
            </span>
          </div>
        )}
      </div>
    </div>
  );
}
