import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MyProfilePage } from '../pages/MyProfilePage';

function renderWithProviders(initialUrl = '/profile') {
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
        <MyProfilePage />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

const MOCK_DASHBOARD_DATA = {
  participant: {
    id: 10,
    github_id: 123456,
    github_username: 'superdev',
    avatar_url: 'https://github.com/superdev.png',
    is_suspended: false,
  },
  rank: 3,
  total_points: 450,
  merged_count: 4,
  daily_usage: {
    date: '2026-09-19',
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
};

const MOCK_CONTRIBUTIONS_LIST = {
  count: 2,
  next: null,
  previous: null,
  results: [
    {
      id: 101,
      status: 'UNDER_REVIEW',
      sub_status: 'validating_rules',
      status_message: 'Automated static analysis in progress',
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
    {
      id: 99,
      status: 'MERGED',
      sub_status: null,
      status_message: 'Merged and points credited',
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
};

describe('MyProfilePage', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('renders loading skeleton initially', () => {
    globalThis.fetch = vi.fn().mockImplementation(() => new Promise(() => {}));
    renderWithProviders();
    expect(screen.getByTestId('my-profile-loading')).toBeInTheDocument();
  });

  it('renders participant identity, GitHub link, authoritative rank, and personal statistics', async () => {
    globalThis.fetch = vi.fn().mockImplementation((url: string) => {
      if (url.includes('/dashboard/')) {
        return Promise.resolve({
          ok: true,
          json: async () => MOCK_DASHBOARD_DATA,
        });
      }
      if (url.includes('/contributions/mine/')) {
        return Promise.resolve({
          ok: true,
          json: async () => MOCK_CONTRIBUTIONS_LIST,
        });
      }
      return Promise.resolve({ ok: true, json: async () => ({}) });
    });

    renderWithProviders();

    await waitFor(() => {
      expect(screen.getByTestId('my-profile-page')).toBeInTheDocument();
    });

    // Identity & GitHub Link
    expect(screen.getByText('superdev')).toBeInTheDocument();
    expect(screen.getByText(/github\.com\/superdev/i)).toBeInTheDocument();

    // Authoritative Rank, Score, and Merged count
    expect(screen.getByTestId('profile-rank')).toHaveTextContent('#3');
    expect(screen.getByTestId('profile-points')).toHaveTextContent('450');
    expect(screen.getByTestId('profile-merged-count')).toHaveTextContent('4');

    // Daily Quotas
    expect(screen.getByText(/300 pts capacity remaining today/i)).toBeInTheDocument();
    expect(screen.getByText(/3 credited PRs remaining today/i)).toBeInTheDocument();

    // Active in-progress contributions
    expect(screen.getByTestId('in-progress-item-101')).toBeInTheDocument();
    expect(screen.getByText('Implement OAuth Token Refresh')).toBeInTheDocument();

    // Recent activity item
    expect(screen.getByTestId('activity-item-99')).toBeInTheDocument();
  });

  it('displays "Not ranked yet" when rank is null', async () => {
    globalThis.fetch = vi.fn().mockImplementation((url: string) => {
      if (url.includes('/dashboard/')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            ...MOCK_DASHBOARD_DATA,
            rank: null,
            total_points: 0,
            merged_count: 0,
          }),
        });
      }
      return Promise.resolve({
        ok: true,
        json: async () => ({ count: 0, results: [] }),
      });
    });

    renderWithProviders();

    await waitFor(() => {
      expect(screen.getByTestId('profile-rank')).toHaveTextContent('Not ranked yet');
    });
  });

  it('supports internal tab switching to Contributions, Activity, and Personal Statistics', async () => {
    globalThis.fetch = vi.fn().mockImplementation((url: string) => {
      if (url.includes('/dashboard/')) {
        return Promise.resolve({
          ok: true,
          json: async () => MOCK_DASHBOARD_DATA,
        });
      }
      if (url.includes('/contributions/mine/')) {
        return Promise.resolve({
          ok: true,
          json: async () => MOCK_CONTRIBUTIONS_LIST,
        });
      }
      return Promise.resolve({ ok: true, json: async () => ({}) });
    });

    renderWithProviders('/profile?tab=overview');

    await waitFor(() => {
      expect(screen.getByTestId('overview-section')).toBeInTheDocument();
    });

    // Switch to Contributions tab
    fireEvent.click(screen.getByTestId('tab-contributions'));
    await waitFor(() => {
      expect(screen.getByTestId('contributions-section')).toBeInTheDocument();
      expect(screen.getByText('Automated static analysis in progress')).toBeInTheDocument();
    });

    // Switch to Activity tab
    fireEvent.click(screen.getByTestId('tab-activity'));
    await waitFor(() => {
      expect(screen.getByTestId('activity-section')).toBeInTheDocument();
      expect(screen.getByText(/Chronological Sprint Activity/i)).toBeInTheDocument();
    });

    // Switch to Statistics tab
    fireEvent.click(screen.getByTestId('tab-statistics'));
    await waitFor(() => {
      expect(screen.getByTestId('statistics-section')).toBeInTheDocument();
      expect(screen.getByText(/Personal Sprint Capacity Breakdown/i)).toBeInTheDocument();
    });
  });

  it('renders error state on API failure with retry mechanism', async () => {
    let callCount = 0;
    globalThis.fetch = vi.fn().mockImplementation(async () => {
      callCount++;
      if (callCount === 1) {
        return {
          ok: false,
          status: 500,
          statusText: 'Internal Server Error',
          json: async () => ({ detail: 'Failed to retrieve profile data' }),
        };
      }
      return {
        ok: true,
        json: async () => MOCK_DASHBOARD_DATA,
      };
    });

    renderWithProviders();

    await waitFor(() => {
      expect(screen.getByTestId('my-profile-error')).toBeInTheDocument();
    });

    const retryBtn = screen.getByRole('button', { name: /retry/i });
    fireEvent.click(retryBtn);

    await waitFor(() => {
      expect(screen.getByTestId('my-profile-page')).toBeInTheDocument();
    });
  });
});
