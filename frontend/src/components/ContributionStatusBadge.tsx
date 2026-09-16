import React from 'react';

export interface StatusMeta {
  label: string;
  description: string;
  badgeClass: string;
  dotClass: string;
  borderClass: string;
}

export function getContributionStatusMeta(
  status: string | undefined,
  subStatus?: string | null
): StatusMeta {
  const normStatus = (status || '').toUpperCase().trim();
  const normSubStatus = (subStatus || '').toUpperCase().trim();

  if (normStatus === 'UNDER_REVIEW' && normSubStatus === 'VALIDATING') {
    return {
      label: 'Validating',
      description:
        'Automated rule checks are actively running (abuse prevention, duplicate checks).',
      badgeClass: 'bg-cyan-950/80 text-cyan-300 border-cyan-700/60',
      dotClass: 'bg-cyan-400 animate-pulse',
      borderClass: 'border-cyan-500/40',
    };
  }

  switch (normStatus) {
    case 'PENDING':
      return {
        label: 'Pending',
        description:
          'Webhook received; awaiting initial repository and issue validation pre-checks.',
        badgeClass: 'bg-slate-800 text-slate-300 border-slate-700',
        dotClass: 'bg-slate-400',
        borderClass: 'border-slate-700',
      };
    case 'QUEUED':
      return {
        label: 'Queued',
        description:
          'Passed initial pre-checks; waiting in line for the automated validation worker.',
        badgeClass: 'bg-blue-950/80 text-blue-300 border-blue-700/60',
        dotClass: 'bg-blue-400 animate-pulse',
        borderClass: 'border-blue-500/40',
      };
    case 'UNDER_REVIEW':
      return {
        label: 'Under Review',
        description:
          'Contribution is being evaluated by the validation pipeline.',
        badgeClass: 'bg-indigo-950/80 text-indigo-300 border-indigo-700/60',
        dotClass: 'bg-indigo-400 animate-pulse',
        borderClass: 'border-indigo-500/40',
      };
    case 'APPROVED':
      return {
        label: 'Approved',
        description:
          'Passed validation checks and is eligible to enter the merge queue.',
        badgeClass: 'bg-teal-950/80 text-teal-300 border-teal-700/60',
        dotClass: 'bg-teal-400',
        borderClass: 'border-teal-500/40',
      };
    case 'MERGING':
      return {
        label: 'Merging',
        description:
          'Active in the concurrency-capped merge queue awaiting GitHub merge confirmation.',
        badgeClass: 'bg-purple-950/80 text-purple-300 border-purple-700/60',
        dotClass: 'bg-purple-400 animate-pulse',
        borderClass: 'border-purple-500/40',
      };
    case 'MERGED':
      return {
        label: 'Merged',
        description:
          'Successfully merged into the target repository on GitHub and credited.',
        badgeClass: 'bg-emerald-950/80 text-emerald-300 border-emerald-700/60',
        dotClass: 'bg-emerald-400',
        borderClass: 'border-emerald-500/40',
      };
    case 'REJECTED':
      return {
        label: 'Rejected',
        description:
          'Did not pass validation pre-checks, automated rules, or was closed without merge.',
        badgeClass: 'bg-rose-950/80 text-rose-300 border-rose-700/60',
        dotClass: 'bg-rose-400',
        borderClass: 'border-rose-500/40',
      };
    case 'FLAGGED':
      return {
        label: 'Flagged',
        description:
          'Held for manual administrator review due to a detected pattern or exhausted retries.',
        badgeClass: 'bg-amber-950/80 text-amber-300 border-amber-700/60',
        dotClass: 'bg-amber-400',
        borderClass: 'border-amber-500/40',
      };
    case 'RETRY':
      return {
        label: 'Retry',
        description:
          'Encountered a transient failure and is scheduled to be reprocessed automatically.',
        badgeClass: 'bg-orange-950/80 text-orange-300 border-orange-700/60',
        dotClass: 'bg-orange-400 animate-pulse',
        borderClass: 'border-orange-500/40',
      };
    default:
      return {
        label: status || 'Unknown',
        description: 'Contribution status recorded in CommitRush.',
        badgeClass: 'bg-slate-800 text-slate-300 border-slate-700',
        dotClass: 'bg-slate-400',
        borderClass: 'border-slate-700',
      };
  }
}

interface ContributionStatusBadgeProps {
  status: string | undefined;
  subStatus?: string | null;
  showExplanation?: boolean;
  size?: 'sm' | 'md' | 'lg';
}

export const ContributionStatusBadge: React.FC<ContributionStatusBadgeProps> = ({
  status,
  subStatus,
  showExplanation = false,
  size = 'md',
}) => {
  const meta = getContributionStatusMeta(status, subStatus);

  const sizeClasses = {
    sm: 'px-2 py-0.5 text-xs',
    md: 'px-2.5 py-1 text-xs font-semibold',
    lg: 'px-3 py-1.5 text-sm font-semibold',
  }[size];

  return (
    <div className="inline-flex flex-col gap-1">
      <span
        className={`inline-flex items-center gap-1.5 rounded-full border shadow-sm ${sizeClasses} ${meta.badgeClass}`}
      >
        <span className={`w-1.5 h-1.5 rounded-full ${meta.dotClass}`} />
        <span>{meta.label}</span>
      </span>
      {showExplanation && (
        <span className="text-xs text-slate-400">{meta.description}</span>
      )}
    </div>
  );
};
