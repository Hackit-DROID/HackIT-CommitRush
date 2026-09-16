import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ContributionDetailPage } from '../pages/ContributionDetailPage';

function renderWithProviders(initialUrl = '/contributions/10') {
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
        <Routes>
          <Route path="/contributions/:id" element={<ContributionDetailPage />} />
          <Route path="/contributions" element={<div>My Contributions List</div>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

describe('ContributionDetailPage', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('renders loading skeleton initially', () => {
    globalThis.fetch = vi.fn().mockImplementation(() => new Promise(() => {}));
    renderWithProviders('/contributions/10');
    expect(screen.getByTestId('contribution-detail-skeleton')).toBeInTheDocument();
  });

  it('renders complete contribution detail view with status, issue, PR, and lifecycle', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        id: 10,
        participant: {
          id: 5,
          github_id: 99999,
          github_username: 'supercoder',
          avatar_url: 'https://github.com/supercoder.png',
        },
        issue: {
          id: 105,
          github_issue_id: 8005,
          title: 'Implement distributed locking mechanism',
          project: 'hackit/backend-core',
          github_number: 77,
          points: 200,
          difficulty: 'advanced',
          category: 'backend',
          status: 'open',
          github_url: 'https://github.com/hackit/backend-core/issues/77',
        },
        pull_request: {
          id: 305,
          github_pr_id: 9005,
          number: 142,
          repo: 'hackit/backend-core',
          merged: false,
          merged_at: null,
          head_sha: 'a1b2c3d4e5f6',
          github_url: 'https://github.com/hackit/backend-core/pull/142',
        },
        status: 'APPROVED',
        sub_status: '',
        retry_count: 0,
        flagged_reason: '',
        approved_at: '2026-09-16T15:00:00Z',
        merged_at: null,
        created_at: '2026-09-16T14:30:00Z',
        updated_at: '2026-09-16T15:00:00Z',
      }),
    } as Response);

    renderWithProviders('/contributions/10');

    await waitFor(() => {
      expect(screen.getByRole('heading', { level: 1, name: 'Implement distributed locking mechanism' })).toBeInTheDocument();
    });

    expect(screen.getAllByText('Approved').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('200 Points')).toBeInTheDocument();
    expect(screen.getByText('@supercoder')).toBeInTheDocument();
    expect(screen.getByText('Passed validation checks and is eligible to enter the merge queue.')).toBeInTheDocument();
    expect(screen.getByText('Linked Issue')).toBeInTheDocument();
    expect(screen.getByText('Pull Request')).toBeInTheDocument();
    expect(screen.getByText('View Issue on GitHub')).toBeInTheDocument();
    expect(screen.getByText('View PR on GitHub')).toBeInTheDocument();
  });

  it('renders not found error state on 404', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 404,
      json: async () => ({ detail: 'Not found.' }),
    } as Response);

    renderWithProviders('/contributions/9999');

    await waitFor(() => {
      expect(screen.getByText('Contribution not found')).toBeInTheDocument();
      expect(screen.getByText(/Back to My Contributions/)).toBeInTheDocument();
    });
  });
});
