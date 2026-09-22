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
      badgeClass: 'bg-[#f4f4f1] text-[#111111] border-[#d8d8d3]',
      dotClass: 'bg-[#3d5f58] animate-pulse',
      borderClass: 'border-[#d8d8d3]',
    };
  }

  switch (normStatus) {
    case 'PENDING':
      return {
        label: 'Pending',
        description:
          'Webhook received; awaiting initial repository and issue validation pre-checks.',
        badgeClass: 'bg-[#f4f4f1] text-[#555555] border-[#d8d8d3]',
        dotClass: 'bg-[#777777]',
        borderClass: 'border-[#d8d8d3]',
      };
    case 'QUEUED':
      return {
        label: 'Queued',
        description:
          'Passed initial pre-checks; waiting in line for the automated validation worker.',
        badgeClass: 'bg-[#f4f4f1] text-[#111111] border-[#d8d8d3]',
        dotClass: 'bg-[#ff5a1f] animate-pulse',
        borderClass: 'border-[#d8d8d3]',
      };
    case 'UNDER_REVIEW':
      return {
        label: 'Under Review',
        description:
          'Contribution is being evaluated by the validation pipeline.',
        badgeClass: 'bg-[#f4f4f1] text-[#111111] border-[#d8d8d3]',
        dotClass: 'bg-[#3d5f58] animate-pulse',
        borderClass: 'border-[#d8d8d3]',
      };
    case 'APPROVED':
      return {
        label: 'Approved',
        description:
          'Passed validation checks and is eligible to enter the merge queue.',
        badgeClass: 'bg-[#eef5f3] text-[#22443d] border-[#c0d8d0]',
        dotClass: 'bg-[#3d5f58]',
        borderClass: 'border-[#c0d8d0]',
      };
    case 'MERGING':
      return {
        label: 'Merging',
        description:
          'Active in the concurrency-capped merge queue awaiting GitHub merge confirmation.',
        badgeClass: 'bg-amber-50 text-amber-900 border-amber-200',
        dotClass: 'bg-amber-500 animate-pulse',
        borderClass: 'border-amber-200',
      };
    case 'MERGED':
      return {
        label: 'Merged',
        description:
          'Successfully merged into the target repository on GitHub and credited.',
        badgeClass: 'bg-[#eaf1ef] text-[#1e3b34] border-[#a9c4bd]',
        dotClass: 'bg-[#3d5f58]',
        borderClass: 'border-[#a9c4bd]',
      };
    case 'REJECTED':
      return {
        label: 'Rejected',
        description:
          'Did not pass validation pre-checks, automated rules, or was closed without merge.',
        badgeClass: 'bg-rose-50 text-rose-900 border-rose-200',
        dotClass: 'bg-[#ff5a1f]',
        borderClass: 'border-rose-200',
      };
    case 'FLAGGED':
      return {
        label: 'Flagged',
        description:
          'Held for manual administrator review due to a detected pattern or exhausted retries.',
        badgeClass: 'bg-amber-50 text-amber-900 border-amber-200',
        dotClass: 'bg-amber-500',
        borderClass: 'border-amber-200',
      };
    case 'RETRY':
      return {
        label: 'Retry',
        description:
          'Encountered a transient failure and is scheduled to be reprocessed automatically.',
        badgeClass: 'bg-orange-50 text-orange-900 border-orange-200',
        dotClass: 'bg-[#ff5a1f] animate-pulse',
        borderClass: 'border-orange-200',
      };
    default:
      return {
        label: status || 'Unknown',
        description: 'Contribution status recorded in CommitRush.',
        badgeClass: 'bg-[#f4f4f1] text-[#555555] border-[#d8d8d3]',
        dotClass: 'bg-[#777777]',
        borderClass: 'border-[#d8d8d3]',
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
    sm: 'px-2.5 py-0.5 text-[11px] font-mono',
    md: 'px-3 py-1 text-xs font-mono font-medium',
    lg: 'px-3.5 py-1.5 text-xs font-mono font-semibold',
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
        <span className="text-xs text-[#555555]">{meta.description}</span>
      )}
    </div>
  );
};
