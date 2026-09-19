import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ProtectedRoute } from '../components/ProtectedRoute';

function renderProtectedRoute({
  initialUrl = '/protected',
  requireStaff = false,
}: {
  initialUrl?: string;
  requireStaff?: boolean;
} = {}) {
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
          <Route
            path="/protected"
            element={
              <ProtectedRoute requireStaff={requireStaff}>
                <div data-testid="protected-content">Secret Protected Area</div>
              </ProtectedRoute>
            }
          />
          <Route path="/" element={<div data-testid="landing-destination">Public Landing Page</div>} />
          <Route path="/profile" element={<div data-testid="profile-destination">Profile</div>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

describe('ProtectedRoute', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('renders loading state while checking session', () => {
    globalThis.fetch = vi.fn().mockImplementation(() => new Promise(() => {}));
    renderProtectedRoute();
    expect(screen.getByTestId('auth-loading')).toBeInTheDocument();
  });

  it('redirects unauthenticated users to landing page', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 401,
      statusText: 'Unauthorized',
      json: async () => ({ detail: 'Authentication credentials were not provided.' }),
    });

    renderProtectedRoute({ initialUrl: '/protected' });

    await waitFor(() => {
      expect(screen.getByTestId('landing-destination')).toBeInTheDocument();
      expect(screen.queryByTestId('protected-content')).not.toBeInTheDocument();
    });
  });

  it('renders children when user is authenticated', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
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

    renderProtectedRoute();

    await waitFor(() => {
      expect(screen.getByTestId('protected-content')).toBeInTheDocument();
      expect(screen.getByText('Secret Protected Area')).toBeInTheDocument();
    });
  });

  it('shows unauthorized screen if requireStaff is true and user is not staff', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
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

    renderProtectedRoute({ requireStaff: true });

    await waitFor(() => {
      expect(screen.getByTestId('unauthorized-state')).toBeInTheDocument();
      expect(screen.getByText(/Staff Access Required/i)).toBeInTheDocument();
      expect(screen.queryByTestId('protected-content')).not.toBeInTheDocument();
    });
  });

  it('renders children when requireStaff is true and user is staff', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        id: 2,
        user_id: 2,
        github_id: 99999,
        github_username: 'admin_user',
        avatar_url: null,
        is_suspended: false,
        total_points: 0,
        is_staff: true,
        is_authenticated: true,
      }),
    });

    renderProtectedRoute({ requireStaff: true });

    await waitFor(() => {
      expect(screen.getByTestId('protected-content')).toBeInTheDocument();
    });
  });
});
