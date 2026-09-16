import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { IssueDetailPage } from '../pages/IssueDetailPage';

function renderWithProviders(issueId: string) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[`/issues/${issueId}`]}>
        <Routes>
          <Route path="/issues/:id" element={<IssueDetailPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

describe('IssueDetailPage', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('renders loading skeleton initially', () => {
    globalThis.fetch = vi.fn().mockImplementation(() => new Promise(() => {}));
    renderWithProviders('42');
    expect(screen.getByTestId('issue-detail-skeleton')).toBeInTheDocument();
  });

  it('renders complete issue details and canonical GitHub link', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        id: 42,
        github_issue_id: 998877,
        title: 'Fix deadlock on leaderboard cache write',
        project: 'hackit/backend-core',
        project_id: 1,
        project_name: 'backend-core',
        github_number: 88,
        points: 100,
        difficulty: 'advanced',
        category: 'backend',
        status: 'open',
        is_featured: true,
        labels: ['bug', 'concurrency'],
        github_url: 'https://github.com/hackit/backend-core/issues/88',
      }),
    } as Response);

    renderWithProviders('42');

    await waitFor(() => {
      expect(screen.getByText('Fix deadlock on leaderboard cache write')).toBeInTheDocument();
      expect(screen.getByText(/Issue #88/i)).toBeInTheDocument();
      expect(screen.getByText('+100 pts')).toBeInTheDocument();
      expect(screen.getByText('advanced')).toBeInTheDocument();
      expect(screen.getByText('backend')).toBeInTheDocument();
      expect(screen.getByText('998877')).toBeInTheDocument();
      expect(screen.getByText('bug')).toBeInTheDocument();
      expect(screen.getByText('concurrency')).toBeInTheDocument();
      
      const githubLink = screen.getByTestId('canonical-github-link');
      expect(githubLink).toHaveAttribute('href', 'https://github.com/hackit/backend-core/issues/88');
      expect(githubLink).toHaveAttribute('target', '_blank');
      expect(githubLink).toHaveAttribute('rel', 'noopener noreferrer');
    });
  });

  it('renders error state on 404', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 404,
      statusText: 'Not Found',
      json: async () => ({ detail: 'Issue not found.' }),
    } as Response);

    renderWithProviders('9999');

    await waitFor(() => {
      expect(screen.getByTestId('error-state')).toBeInTheDocument();
      expect(screen.getByText('Resource Not Found')).toBeInTheDocument();
    });
  });
});
