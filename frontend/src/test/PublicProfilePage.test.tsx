import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { PublicProfilePage } from '../pages/PublicProfilePage';

function renderWithProviders(username = 'alice') {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[`/profile/${username}`]}>
        <Routes>
          <Route path="/profile/:username" element={<PublicProfilePage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

describe('PublicProfilePage', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('renders loading skeleton initially', () => {
    globalThis.fetch = vi.fn().mockImplementation(() => new Promise(() => {}));
    renderWithProviders('alice');
    expect(screen.getByTestId('profile-skeleton')).toBeInTheDocument();
  });

  it('renders public profile data, stats grid, and merged contributions', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        id: 10,
        github_id: 99999,
        github_username: 'alice',
        avatar_url: 'https://github.com/alice.png',
        total_points: 600,
        merged_count: 5,
        rank: 1,
        stats: {
          total_contributions: 8,
          merged_contributions: 5,
          in_progress_contributions: 2,
          rejected_contributions: 1,
        },
        recent_merged_contributions: [
          {
            id: 1,
            project_name: 'hackit/core',
            issue_number: 12,
            issue_title: 'Implement OAuth Token Refresh',
            points: 100,
            merged_at: '2026-09-16T15:00:00Z',
            github_url: 'https://github.com/hackit/core/pull/12',
          },
        ],
      }),
    });

    renderWithProviders('alice');

    await waitFor(() => {
      expect(screen.getByTestId('profile-page')).toBeInTheDocument();
    });

    expect(screen.getByText('alice')).toBeInTheDocument();
    expect(screen.getByText('#1')).toBeInTheDocument();
    expect(screen.getByText('600')).toBeInTheDocument();

    // Stats grid
    expect(screen.getByText('Total Submissions')).toBeInTheDocument();
    expect(screen.getByText('8')).toBeInTheDocument();
    expect(screen.getAllByText('5').length).toBeGreaterThanOrEqual(1);

    // Merged contributions
    expect(screen.getByText('Implement OAuth Token Refresh')).toBeInTheDocument();
    expect(screen.getByText('+100 pts')).toBeInTheDocument();
  });

  it('renders 404 not found / suspended notice when user does not exist', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 404,
      statusText: 'Not Found',
      json: async () => ({ detail: "Participant 'unknown_user' not found." }),
    });

    renderWithProviders('unknown_user');

    await waitFor(() => {
      expect(screen.getByTestId('profile-not-found')).toBeInTheDocument();
    });

    expect(screen.getByText(/Contributor Not Found/i)).toBeInTheDocument();
    expect(screen.getByText(/@unknown_user/i)).toBeInTheDocument();
  });

  it('renders error state on 500 error with working retry', async () => {
    let callCount = 0;
    globalThis.fetch = vi.fn().mockImplementation(async () => {
      callCount++;
      if (callCount === 1) {
        return {
          ok: false,
          status: 500,
          statusText: 'Internal Server Error',
          json: async () => ({ detail: 'Database error' }),
        };
      }
      return {
        ok: true,
        json: async () => ({
          id: 10,
          github_id: 1,
          github_username: 'alice',
          avatar_url: null,
          total_points: 0,
          merged_count: 0,
          rank: null,
          stats: { total_contributions: 0, merged_contributions: 0, in_progress_contributions: 0, rejected_contributions: 0 },
          recent_merged_contributions: [],
        }),
      };
    });

    renderWithProviders('alice');

    await waitFor(() => {
      expect(screen.getByTestId('error-state')).toBeInTheDocument();
    });

    const retryBtn = screen.getByRole('button', { name: /retry/i });
    fireEvent.click(retryBtn);

    await waitFor(() => {
      expect(screen.getByTestId('profile-page')).toBeInTheDocument();
    });
  });
});
