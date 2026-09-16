import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import {
  ContributionStatusBadge,
  getContributionStatusMeta,
} from '../components/ContributionStatusBadge';

describe('ContributionStatusBadge and getContributionStatusMeta', () => {
  const canonicalStatuses = [
    { status: 'PENDING', subStatus: '', expectedLabel: 'Pending', checkText: 'Webhook received' },
    { status: 'QUEUED', subStatus: '', expectedLabel: 'Queued', checkText: 'Passed initial pre-checks' },
    { status: 'UNDER_REVIEW', subStatus: 'VALIDATING', expectedLabel: 'Validating', checkText: 'Automated rule checks are actively running' },
    { status: 'UNDER_REVIEW', subStatus: '', expectedLabel: 'Under Review', checkText: 'evaluated by the validation pipeline' },
    { status: 'APPROVED', subStatus: '', expectedLabel: 'Approved', checkText: 'Passed validation checks' },
    { status: 'MERGING', subStatus: '', expectedLabel: 'Merging', checkText: 'Active in the concurrency-capped merge queue' },
    { status: 'MERGED', subStatus: '', expectedLabel: 'Merged', checkText: 'Successfully merged' },
    { status: 'REJECTED', subStatus: '', expectedLabel: 'Rejected', checkText: 'Did not pass validation' },
    { status: 'FLAGGED', subStatus: '', expectedLabel: 'Flagged', checkText: 'Held for manual administrator review' },
    { status: 'RETRY', subStatus: '', expectedLabel: 'Retry', checkText: 'transient failure' },
  ];

  canonicalStatuses.forEach(({ status, subStatus, expectedLabel, checkText }) => {
    it(`maps status='${status}' with subStatus='${subStatus}' to label '${expectedLabel}'`, () => {
      const meta = getContributionStatusMeta(status, subStatus);
      expect(meta.label).toBe(expectedLabel);
      expect(meta.description).toContain(checkText);

      render(
        <ContributionStatusBadge
          status={status}
          subStatus={subStatus}
          showExplanation={true}
        />
      );
      expect(screen.getByText(expectedLabel)).toBeInTheDocument();
      expect(screen.getByText(meta.description)).toBeInTheDocument();
    });
  });
});
