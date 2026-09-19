import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { App, queryClient } from '../App';

describe('App Routing and Auth Flow', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    queryClient.clear();
    window.history.pushState({}, 'Test', '/');
  });

  it('renders landing page on root / when user is unauthenticated', async () => {
    globalThis.fetch = vi.fn().mockImplementation((url: string) => {
      if (url.includes('/auth/me/')) {
        return Promise.resolve({
          ok: false,
          status: 401,
          statusText: 'Unauthorized',
          json: async () => ({ detail: 'Authentication credentials were not provided.' }),
        });
      }
      return Promise.resolve({
        ok: true,
        json: async () => ({ count: 0, results: [] }),
      });
    });

    render(<App />);

    await waitFor(() => {
      expect(screen.getByTestId('landing-page')).toBeInTheDocument();
      expect(screen.getByTestId('github-login-cta')).toBeInTheDocument();
    });
  });

  it('redirects to /profile on root / when user is authenticated', async () => {
    globalThis.fetch = vi.fn().mockImplementation((url: string) => {
      if (url.includes('/auth/me/')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            id: 1,
            user_id: 1,
            github_id: 12345,
            github_username: 'sarah_dev',
            avatar_url: null,
            is_suspended: false,
            total_points: 250,
            is_staff: false,
            is_authenticated: true,
          }),
        });
      }
      if (url.includes('/dashboard/')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            participant: { id: 1, github_id: 12345, github_username: 'sarah_dev', avatar_url: null },
            rank: 1,
            total_points: 250,
            merged_count: 3,
            daily_usage: { date: '2026-09-19', contributions_count: 1, max_contributions: 5, points_count: 100, max_points: 500 },
            in_progress_contributions: [],
            recent_activity: [],
          }),
        });
      }
      return Promise.resolve({
        ok: true,
        json: async () => ({ count: 0, results: [] }),
      });
    });

    render(<App />);

    await waitFor(
      () => {
        expect(screen.getByTestId('my-profile-page')).toBeInTheDocument();
      },
      { timeout: 3000 }
    );

    expect(screen.getAllByText('sarah_dev').length).toBeGreaterThan(0);
  });

  it('redirects unauthenticated visitor from /profile to landing page with login_required', async () => {
    window.history.pushState({}, 'Test', '/profile');

    globalThis.fetch = vi.fn().mockImplementation((url: string) => {
      if (url.includes('/auth/me/')) {
        return Promise.resolve({
          ok: false,
          status: 401,
          statusText: 'Unauthorized',
          json: async () => ({ detail: 'Authentication credentials were not provided.' }),
        });
      }
      return Promise.resolve({
        ok: true,
        json: async () => ({ count: 0, results: [] }),
      });
    });

    render(<App />);

    await waitFor(() => {
      expect(screen.getByTestId('landing-page')).toBeInTheDocument();
      expect(screen.getByTestId('login-required-banner')).toBeInTheDocument();
    });
  });

  it('redirects deprecated /dashboard route to /profile', async () => {
    window.history.pushState({}, 'Test', '/dashboard');

    globalThis.fetch = vi.fn().mockImplementation((url: string) => {
      if (url.includes('/auth/me/')) {
        return Promise.resolve({
          ok: false,
          status: 401,
          statusText: 'Unauthorized',
          json: async () => ({ detail: 'Authentication credentials were not provided.' }),
        });
      }
      return Promise.resolve({
        ok: true,
        json: async () => ({ count: 0, results: [] }),
      });
    });

    render(<App />);

    await waitFor(() => {
      expect(screen.getByTestId('landing-page')).toBeInTheDocument();
      expect(screen.getByTestId('login-required-banner')).toBeInTheDocument();
    });
  });

  it('redirects deprecated /contributions route to /profile?tab=contributions', async () => {
    window.history.pushState({}, 'Test', '/contributions');

    globalThis.fetch = vi.fn().mockImplementation((url: string) => {
      if (url.includes('/auth/me/')) {
        return Promise.resolve({
          ok: false,
          status: 401,
          statusText: 'Unauthorized',
          json: async () => ({ detail: 'Authentication credentials were not provided.' }),
        });
      }
      return Promise.resolve({
        ok: true,
        json: async () => ({ count: 0, results: [] }),
      });
    });

    render(<App />);

    await waitFor(() => {
      expect(screen.getByTestId('landing-page')).toBeInTheDocument();
      expect(screen.getByTestId('login-required-banner')).toBeInTheDocument();
    });
  });

  it('redirects deprecated /stats route to /profile', async () => {
    window.history.pushState({}, 'Test', '/stats');

    globalThis.fetch = vi.fn().mockImplementation((url: string) => {
      if (url.includes('/auth/me/')) {
        return Promise.resolve({
          ok: false,
          status: 401,
          statusText: 'Unauthorized',
          json: async () => ({ detail: 'Authentication credentials were not provided.' }),
        });
      }
      return Promise.resolve({
        ok: true,
        json: async () => ({ count: 0, results: [] }),
      });
    });

    render(<App />);

    await waitFor(() => {
      expect(screen.getByTestId('landing-page')).toBeInTheDocument();
      expect(screen.getByTestId('login-required-banner')).toBeInTheDocument();
    });
  });

  it('renders custom NotFoundPage when navigating to an unknown route', async () => {
    window.history.pushState({}, 'Test', '/some-completely-unknown-route');

    globalThis.fetch = vi.fn().mockImplementation((url: string) => {
      if (url.includes('/auth/me/')) {
        return Promise.resolve({
          ok: false,
          status: 401,
          statusText: 'Unauthorized',
          json: async () => ({ detail: 'Authentication credentials were not provided.' }),
        });
      }
      return Promise.resolve({
        ok: true,
        json: async () => ({ count: 0, results: [] }),
      });
    });

    render(<App />);

    await waitFor(() => {
      expect(screen.getByTestId('not-found-page')).toBeInTheDocument();
      expect(screen.getByText('Lost in the Commit Tree')).toBeInTheDocument();
      expect(screen.getByTestId('not-found-home-btn')).toHaveAttribute('href', '/');
    });
  });
});

