import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MyContributionsPage } from '../pages/MyContributionsPage';

function renderWithProviders(initialUrl = '/contributions') {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[initialUrl]}>
        <MyContributionsPage />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

describe('MyContributionsPage', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('renders loading skeleton initially', () => {
    globalThis.fetch = vi.fn().mockImplementation(() => new Promise(() => {}));
    renderWithProviders();
    expect(screen.getByTestId('contributions-skeleton')).toBeInTheDocument();
  });

  it('renders contribution cards with status badges and explanations', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        count: 2,
        next: null,
        previous: null,
        results: [
          {
            id: 1,
            participant: {
              id: 10,
              github_id: 12345,
              github_username: 'octocat',
              avatar_url: 'https://github.com/octocat.png',
            },
            issue: {
              id: 101,
              github_issue_id: 5001,
              title: 'Fix Redis connection leak in worker',
              project: 'hackit/backend-core',
              github_number: 42,
              points: 100,
              difficulty: 'intermediate',
              category: 'backend',
              status: 'open',
              github_url: 'https://github.com/hackit/backend-core/issues/42',
            },
            pull_request: {
              id: 201,
              github_pr_id: 6001,
              number: 88,
              repo: 'hackit/backend-core',
              merged: false,
              merged_at: null,
              head_sha: 'abc1234567890',
              github_url: 'https://github.com/hackit/backend-core/pull/88',
            },
            status: 'UNDER_REVIEW',
            sub_status: 'VALIDATING',
            retry_count: 0,
            flagged_reason: '',
            approved_at: null,
            merged_at: null,
            created_at: '2026-09-16T12:00:00Z',
            updated_at: '2026-09-16T12:00:00Z',
          },
          {
            id: 2,
            participant: {
              id: 10,
              github_id: 12345,
              github_username: 'octocat',
              avatar_url: 'https://github.com/octocat.png',
            },
            issue: {
              id: 102,
              github_issue_id: 5002,
              title: 'Add dark mode support',
              project: 'hackit/commitrush-ui',
              github_number: 15,
              points: 50,
              difficulty: 'beginner',
              category: 'frontend',
              status: 'closed',
              github_url: 'https://github.com/hackit/commitrush-ui/issues/15',
            },
            pull_request: {
              id: 202,
              github_pr_id: 6002,
              number: 22,
              repo: 'hackit/commitrush-ui',
              merged: true,
              merged_at: '2026-09-16T14:00:00Z',
              head_sha: 'def9876543210',
              github_url: 'https://github.com/hackit/commitrush-ui/pull/22',
            },
            status: 'MERGED',
            sub_status: '',
            retry_count: 0,
            flagged_reason: '',
            approved_at: '2026-09-16T13:00:00Z',
            merged_at: '2026-09-16T14:00:00Z',
            created_at: '2026-09-16T11:00:00Z',
            updated_at: '2026-09-16T14:00:00Z',
          },
        ],
      }),
    } as Response);

    renderWithProviders();

    await waitFor(() => {
      expect(screen.getByText('Fix Redis connection leak in worker')).toBeInTheDocument();
      expect(screen.getByText('Validating')).toBeInTheDocument();
      expect(screen.getByText(/100\s*pts/)).toBeInTheDocument();
      expect(screen.getByText(/PR #88/)).toBeInTheDocument();

      expect(screen.getByText('Add dark mode support')).toBeInTheDocument();
      expect(screen.getAllByText('Merged').length).toBeGreaterThanOrEqual(1);
      expect(screen.getByText(/50\s*pts/)).toBeInTheDocument();
      expect(screen.getByText(/PR #22/)).toBeInTheDocument();
    });
  });

  it('renders empty state when user has no contributions', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        count: 0,
        next: null,
        previous: null,
        results: [],
      }),
    } as Response);

    renderWithProviders();

    await waitFor(() => {
      expect(screen.getByTestId('empty-state')).toBeInTheDocument();
      expect(screen.getByText('No contributions yet')).toBeInTheDocument();
    });
  });

  it('filters by status when clicking status button', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        count: 0,
        next: null,
        previous: null,
        results: [],
      }),
    } as Response);
    globalThis.fetch = fetchMock;

    renderWithProviders();

    await waitFor(() => {
      expect(screen.getByText('Approved')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('Approved'));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining('status=APPROVED'),
        expect.anything()
      );
    });
  });
});
