import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { StatsPage } from '../pages/StatsPage';

function renderWithProviders(initialUrl = '/stats') {
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
        <StatsPage />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

describe('StatsPage', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('renders loading skeleton initially', () => {
    globalThis.fetch = vi.fn().mockImplementation(() => new Promise(() => {}));
    renderWithProviders();
    expect(screen.getByTestId('stats-skeleton')).toBeInTheDocument();
  });

  it('renders overview metrics, status counts, and runtime controls', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        event_status: 'active',
        system_status: {
          merge_paused: false,
          validation_paused: false,
          submissions_paused: false,
          leaderboard_frozen: false,
        },
        participants: {
          total: 45,
          active: 42,
        },
        pull_requests: {
          total: 120,
          merged: 80,
        },
        contributions: {
          total: 120,
          by_status: {
            PENDING: 5,
            QUEUED: 10,
            UNDER_REVIEW: 8,
            APPROVED: 12,
            MERGING: 3,
            MERGED: 80,
            REJECTED: 2,
            FLAGGED: 0,
            RETRY: 0,
          },
        },
        points: {
          total_awarded: 4500,
          points_past_hour: 400,
        },
        rates: {
          merges_past_hour: 8,
          points_past_hour: 400,
        },
        updated_at: '2026-09-16T18:00:00Z',
      }),
    });

    renderWithProviders();

    await waitFor(() => {
      expect(screen.getByTestId('stats-page')).toBeInTheDocument();
    });

    expect(screen.getByText('45')).toBeInTheDocument();
    expect(screen.getByText('42 active contributors')).toBeInTheDocument();
    expect(screen.getByText('4500')).toBeInTheDocument();
    expect(screen.getByText('+400 in the past hour')).toBeInTheDocument();

    // Status breakdown
    expect(screen.getByTestId('status-count-MERGED')).toHaveTextContent('80');
    expect(screen.getByTestId('status-count-PENDING')).toHaveTextContent('5');
    expect(screen.getByTestId('status-count-APPROVED')).toHaveTextContent('12');

    // System runtime controls
    expect(screen.getByTestId('stats-system-status')).toBeInTheDocument();
  });

  it('renders error state on API failure with retry', async () => {
    let callCount = 0;
    globalThis.fetch = vi.fn().mockImplementation(async () => {
      callCount++;
      if (callCount === 1) {
        return {
          ok: false,
          status: 500,
          statusText: 'Internal Server Error',
          json: async () => ({ detail: 'Failed fetching stats' }),
        };
      }
      return {
        ok: true,
        json: async () => ({
          event_status: 'active',
          system_status: { merge_paused: false, validation_paused: false, submissions_paused: false, leaderboard_frozen: false },
          participants: { total: 0, active: 0 },
          pull_requests: { total: 0, merged: 0 },
          contributions: { total: 0, by_status: {} },
          points: { total_awarded: 0, points_past_hour: 0 },
          rates: { merges_past_hour: 0, points_past_hour: 0 },
          updated_at: '2026-09-16T18:00:00Z',
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
      expect(screen.getByTestId('stats-page')).toBeInTheDocument();
    });
  });
});
