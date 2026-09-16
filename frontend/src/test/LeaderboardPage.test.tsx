import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { LeaderboardPage } from '../pages/LeaderboardPage';

function renderWithProviders(initialUrl = '/leaderboard') {
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
        <LeaderboardPage />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

describe('LeaderboardPage', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('renders loading skeleton initially', () => {
    globalThis.fetch = vi.fn().mockImplementation(() => new Promise(() => {}));
    renderWithProviders();
    expect(screen.getByTestId('leaderboard-skeleton')).toBeInTheDocument();
  });

  it('renders ranked participants table and own rank card', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        count: 2,
        page: 1,
        page_size: 50,
        num_pages: 1,
        frozen: false,
        frozen_at: null,
        results: [
          {
            rank: 1,
            participant_id: 10,
            github_username: 'alice',
            avatar_url: 'https://github.com/alice.png',
            total_points: 350,
            merged_count: 4,
          },
          {
            rank: 2,
            participant_id: 20,
            github_username: 'bob',
            avatar_url: 'https://github.com/bob.png',
            total_points: 200,
            merged_count: 2,
          },
        ],
        me: {
          rank: 2,
          participant_id: 20,
          github_username: 'bob',
          avatar_url: 'https://github.com/bob.png',
          total_points: 200,
          merged_count: 2,
        },
      }),
    });

    renderWithProviders();

    await waitFor(() => {
      expect(screen.getByTestId('leaderboard-table')).toBeInTheDocument();
    });

    expect(screen.getByText('alice')).toBeInTheDocument();
    expect(screen.getByText('350')).toBeInTheDocument();
    expect(screen.getAllByText('bob').length).toBeGreaterThanOrEqual(1);

    // Verify own rank card
    expect(screen.getByTestId('me-rank-card')).toBeInTheDocument();
    expect(screen.getByText('Currently ranked #2')).toBeInTheDocument();
  });

  it('renders frozen state badge and notice when event leaderboard is frozen', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        count: 1,
        page: 1,
        page_size: 50,
        num_pages: 1,
        frozen: true,
        frozen_at: '2026-09-16T12:00:00Z',
        results: [
          {
            rank: 1,
            participant_id: 10,
            github_username: 'alice',
            avatar_url: null,
            total_points: 350,
            merged_count: 4,
          },
        ],
      }),
    });

    renderWithProviders();

    await waitFor(() => {
      expect(screen.getByTestId('frozen-badge')).toBeInTheDocument();
    });

    expect(screen.getByTestId('frozen-notice')).toBeInTheDocument();
    expect(screen.getByText('Event Leaderboard Frozen')).toBeInTheDocument();
  });

  it('handles server-side pagination controls', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        count: 100,
        page: 1,
        page_size: 50,
        num_pages: 2,
        frozen: false,
        frozen_at: null,
        results: [
          {
            rank: 1,
            participant_id: 1,
            github_username: 'user1',
            avatar_url: null,
            total_points: 500,
            merged_count: 5,
          },
        ],
      }),
    });
    globalThis.fetch = fetchMock;

    renderWithProviders();

    await waitFor(() => {
      expect(screen.getByTestId('pagination-controls')).toBeInTheDocument();
    });

    const nextButton = screen.getByTestId('next-page-button');
    expect(nextButton).not.toBeDisabled();
    expect(screen.getByTestId('prev-page-button')).toBeDisabled();

    fireEvent.click(nextButton);

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledTimes(2);
    });
  });

  it('renders empty state when there are no ranked participants', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        count: 0,
        page: 1,
        page_size: 50,
        num_pages: 1,
        frozen: false,
        frozen_at: null,
        results: [],
      }),
    });

    renderWithProviders();

    await waitFor(() => {
      expect(screen.getByTestId('empty-state')).toBeInTheDocument();
    });
    expect(screen.getByText('No Ranked Contributors Yet')).toBeInTheDocument();
  });

  it('renders error state on API failure with working retry button', async () => {
    let callCount = 0;
    globalThis.fetch = vi.fn().mockImplementation(async () => {
      callCount++;
      if (callCount === 1) {
        return {
          ok: false,
          status: 500,
          statusText: 'Internal Server Error',
          json: async () => ({ detail: 'Database connection failed' }),
        };
      }
      return {
        ok: true,
        json: async () => ({
          count: 0,
          page: 1,
          page_size: 50,
          num_pages: 1,
          frozen: false,
          frozen_at: null,
          results: [],
        }),
      };
    });

    renderWithProviders();

    await waitFor(() => {
      expect(screen.getByTestId('error-state')).toBeInTheDocument();
    });

    const retryBtn = screen.getByRole('button', { name: /retry/i });
    fireEvent.click(retryBtn);

    await waitFor(() => {
      expect(screen.getByTestId('empty-state')).toBeInTheDocument();
    });
  });
});
