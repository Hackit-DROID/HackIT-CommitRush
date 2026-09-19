import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { RootGate } from '../components/RootGate';

function renderRootGate() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={['/']}>
        <Routes>
          <Route path="/" element={<RootGate />} />
          <Route path="/profile" element={<div data-testid="my-profile-page">My Profile Page</div>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

describe('RootGate', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('shows loading placeholder while session is authenticating', () => {
    globalThis.fetch = vi.fn().mockImplementation(() => new Promise(() => {}));
    renderRootGate();
    expect(screen.getByTestId('root-loading')).toBeInTheDocument();
  });

  it('renders landing page when visitor is unauthenticated', async () => {
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

    renderRootGate();

    await waitFor(() => {
      expect(screen.getByTestId('landing-page')).toBeInTheDocument();
      expect(screen.queryByTestId('my-profile-page')).not.toBeInTheDocument();
    });
  });

  it('redirects to /profile when user is authenticated', async () => {
    globalThis.fetch = vi.fn().mockImplementation((url: string) => {
      if (url.includes('/auth/me/')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            id: 1,
            user_id: 1,
            github_id: 12345,
            github_username: 'dev_user',
            avatar_url: null,
            is_suspended: false,
            total_points: 100,
            is_staff: false,
            is_authenticated: true,
          }),
        });
      }
      return Promise.resolve({
        ok: true,
        json: async () => ({ count: 0, results: [] }),
      });
    });

    renderRootGate();

    await waitFor(() => {
      expect(screen.getByTestId('my-profile-page')).toBeInTheDocument();
      expect(screen.queryByTestId('landing-page')).not.toBeInTheDocument();
    });
  });
});
