import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { LandingPage } from '../pages/LandingPage';

function renderWithProviders(initialUrl = '/') {
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
        <LandingPage />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

describe('LandingPage', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('renders hero title, description, and primary GitHub CTA', async () => {
    globalThis.fetch = vi.fn().mockImplementation((url: string) => {
      if (url.includes('/stats/')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            event_status: 'active',
            system_status: { merge_paused: false, validation_paused: false, submissions_paused: false, leaderboard_frozen: false },
            participants: { total: 150, active: 45 },
            pull_requests: { total: 320, merged: 210 },
            contributions: { total: 320, by_status: { MERGED: 210 } },
            points: { total_awarded: 18500, points_past_hour: 400 },
            rates: { merges_past_hour: 5, points_past_hour: 400 },
            updated_at: new Date().toISOString(),
          }),
        });
      }
      if (url.includes('/issues/')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            count: 2,
            next: null,
            previous: null,
            results: [
              {
                id: 1,
                title: 'Add JWT Auth Validator',
                project: 'hackit/core',
                github_number: 10,
                points: 100,
                difficulty: 'intermediate',
                category: 'backend',
                status: 'open',
                is_featured: true,
                labels: ['backend', 'auth'],
                github_url: 'https://github.com/Hackit-DROID/Open-Source-Contribution-Drive/issues/10',
              },
            ],
          }),
        });
      }
      return Promise.resolve({
        ok: true,
        json: async () => ({}),
      });
    });

    renderWithProviders('/');

    expect(screen.getByTestId('landing-page')).toBeInTheDocument();
    expect(screen.getByText(/The Open-Source/i)).toBeInTheDocument();
    expect(screen.getAllByText(/Contribution Drive/i).length).toBeGreaterThan(0);
    expect(screen.getByTestId('github-login-cta')).toBeInTheDocument();
    expect(screen.getAllByText(/Explore 1,500\+ Issues/i).length).toBeGreaterThan(0);

    // Verify 4-step lifecycle instructions
    expect(screen.getByText(/How CommitRush Works/i)).toBeInTheDocument();
    expect(screen.getByText(/1\. Browse & Pick Issues/i)).toBeInTheDocument();
    expect(screen.getByText(/2\. Fork, Code & Solve/i)).toBeInTheDocument();
    expect(screen.getByText(/3\. Open PR with Link/i)).toBeInTheDocument();
    expect(screen.getByText(/4\. Validation & Points/i)).toBeInTheDocument();

    // Verify live stats display
    await waitFor(() => {
      expect(screen.getByText('18,500 pts')).toBeInTheDocument();
      expect(screen.getByText('Add JWT Auth Validator')).toBeInTheDocument();
    });
  });

  it('renders login required alert banner when redirected with query parameter', () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ count: 0, results: [] }),
    });

    renderWithProviders('/?login_required=1');

    expect(screen.getByTestId('login-required-banner')).toBeInTheDocument();
    expect(screen.getByText(/Authentication Required/i)).toBeInTheDocument();
  });
});
