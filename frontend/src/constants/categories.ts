/**
 * Authoritative issue category definitions for CommitRush.
 * Mirrors backend/core/categories.py.
 */

export interface IssueCategory {
  value: string;
  label: string;
  count?: number;
}

export const ISSUE_CATEGORIES: IssueCategory[] = [
  { value: 'feature', label: 'Features' },
  { value: 'test', label: 'Testing & QA' },
  { value: 'bug', label: 'Bug Fixes' },
  { value: 'security', label: 'Security' },
  { value: 'performance', label: 'Performance' },
  { value: 'docs', label: 'Documentation' },
  { value: 'refactor', label: 'Refactoring' },
  { value: 'validation', label: 'Validation' },
  { value: 'ui', label: 'UI' },
  { value: 'database', label: 'Database & Storage' },
  { value: 'networking', label: 'Networking' },
  { value: 'frontend', label: 'Frontend' },
  { value: 'backend', label: 'Backend' },
  { value: 'devops', label: 'DevOps / Infrastructure' },
  { value: 'fullstack', label: 'Fullstack' },
  { value: 'dx', label: 'Developer Experience' },
];

export const CATEGORY_LABEL_MAP: Record<string, string> = Object.fromEntries(
  ISSUE_CATEGORIES.map((c) => [c.value, c.label])
);
