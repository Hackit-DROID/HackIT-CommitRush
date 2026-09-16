import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { DashboardPage } from '../pages/DashboardPage';

function renderWithProviders(initialUrl = '/dashboard') {
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
        <DashboardPage />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

describe('DashboardPage', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('renders loading skeleton initially', () => {
    globalThis.fetch = vi.fn().mockImplementation(() => new Promise(() => {}));
    renderWithProviders();
    expect(screen.getByTestId('dashboard-skeleton')).toBeInTheDocument();
  });

  it('renders participant identity, rank, points, daily usage, and active contributions', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        participant: {
          id: 10,
          github_id: 123456,
          github_username: 'superdev',
          avatar_url: 'https://github.com/superdev.png',
        },
        rank: 3,
        total_points: 450,
        merged_count: 4,
        daily_usage: {
          date: '2026-09-16',
          contributions_count: 2,
          max_contributions: 5,
          points_count: 200,
          max_points: 500,
        },
        in_progress_contributions: [
          {
            id: 101,
            status: 'UNDER_REVIEW',
            sub_status: 'validating_rules',
            issue: {
              id: 55,
              github_number: 12,
              title: 'Implement OAuth Token Refresh',
              points: 100,
              project: 'hackit/core',
            },
            pull_request: {
              repo: 'hackit/core',
              number: 88,
            },
          },
        ],
        recent_activity: [
          {
            id: 99,
            status: 'MERGED',
            issue: {
              id: 40,
              github_number: 8,
              title: 'Add Redis rate limiter',
              points: 150,
              project: 'hackit/core',
            },
            pull_request: {
              repo: 'hackit/core',
              number: 77,
            },
          },
        ],
      }),
    });

    renderWithProviders();

    await waitFor(() => {
      expect(screen.getByTestId('dashboard-page')).toBeInTheDocument();
    });

    expect(screen.getByText('superdev')).toBeInTheDocument();
    expect(screen.getByText('#3')).toBeInTheDocument();
    expect(screen.getByText('450')).toBeInTheDocument();

    // Daily caps
    expect(screen.getByText(/300 pts capacity remaining today/i)).toBeInTheDocument();
    expect(screen.getByText(/3 credited PRs remaining today/i)).toBeInTheDocument();

    // In-progress items
    expect(screen.getByTestId('in-progress-item-101')).toBeInTheDocument();
    expect(screen.getByText('Implement OAuth Token Refresh')).toBeInTheDocument();

    // Recent activity
    expect(screen.getByTestId('activity-item-99')).toBeInTheDocument();
    expect(screen.getByText('Add Redis rate limiter')).toBeInTheDocument();
  });

  it('renders error state on failure with retry', async () => {
    let callCount = 0;
    globalThis.fetch = vi.fn().mockImplementation(async () => {
      callCount++;
      if (callCount === 1) {
        return {
          ok: false,
          status: 401,
          statusText: 'Unauthorized',
          json: async () => ({ detail: 'Authentication credentials were not provided.' }),
        };
      }
      return {
        ok: true,
        json: async () => ({
          participant: { id: 1, github_id: 1, github_username: 'u1', avatar_url: null },
          rank: 1,
          total_points: 0,
          merged_count: 0,
          daily_usage: { date: '2026-09-16', contributions_count: 0, max_contributions: 5, points_count: 0, max_points: 500 },
          in_progress_contributions: [],
          recent_activity: [],
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
      expect(screen.getByTestId('dashboard-page')).toBeInTheDocument();
    });
  });
});
