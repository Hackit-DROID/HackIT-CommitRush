import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { NotFoundPage } from '../pages/NotFoundPage';

function renderWithProviders(initialUrl = '/unknown-path', mockUserResponse: any = null) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });

  globalThis.fetch = vi.fn().mockImplementation((url: string) => {
    if (url.includes('/auth/me/')) {
      if (mockUserResponse) {
        return Promise.resolve({
          ok: true,
          json: async () => mockUserResponse,
        });
      }
      return Promise.resolve({
        ok: false,
        status: 401,
        statusText: 'Unauthorized',
        json: async () => ({ detail: 'Authentication credentials were not provided.' }),
      });
    }
    return Promise.resolve({
      ok: true,
      json: async () => ({}),
    });
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[initialUrl]}>
        <NotFoundPage />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

describe('NotFoundPage', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('renders 404 heading, git error terminal, and navigation links for unauthenticated visitor', async () => {
    renderWithProviders('/not-found-route');

    expect(screen.getByTestId('not-found-page')).toBeInTheDocument();
    expect(screen.getByText(/ERR_COMMIT_NOT_FOUND • 404/i)).toBeInTheDocument();
    expect(screen.getByText('404')).toBeInTheDocument();
    expect(screen.getByText('Lost in the Commit Tree')).toBeInTheDocument();

    // Verify git terminal output displays the attempted route
    expect(
      screen.getAllByText((content) => content.includes('/not-found-route')).length
    ).toBeGreaterThanOrEqual(1);
    expect(
      screen.getByText((content) => content.includes("did not match any file(s) known to git"))
    ).toBeInTheDocument();

    // Unauthenticated user should see landing page link
    const homeBtn = screen.getByTestId('not-found-home-btn');
    expect(homeBtn).toHaveAttribute('href', '/');
    expect(homeBtn).toHaveTextContent('Back to Landing Page');

    // Quick navigation links
    expect(screen.getByTestId('not-found-issues-btn')).toHaveAttribute('href', '/issues');
    expect(screen.getByTestId('not-found-projects-btn')).toHaveAttribute('href', '/projects');
    expect(screen.getByTestId('not-found-leaderboard-btn')).toHaveAttribute('href', '/leaderboard');
  });

  it('renders "Back to My Profile" button when authenticated participant visits 404', async () => {
    const mockUser = {
      id: 1,
      user_id: 1,
      github_id: 12345,
      github_username: 'sarah_dev',
      avatar_url: 'https://avatars.githubusercontent.com/u/12345?v=4',
      is_suspended: false,
      total_points: 250,
      is_staff: false,
      is_authenticated: true,
    };

    renderWithProviders('/some/broken/deep/link', mockUser);

    await waitFor(() => {
      const homeBtn = screen.getByTestId('not-found-home-btn');
      expect(homeBtn).toHaveAttribute('href', '/profile');
      expect(homeBtn).toHaveTextContent('Back to My Profile');
    });

    expect(
      screen.getAllByText((content) => content.includes('/some/broken/deep/link')).length
    ).toBeGreaterThanOrEqual(1);
  });
});
