import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Layout } from '../components/Layout';

function renderLayout(initialUrl = '/', mockUser: any = null) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
    },
  });

  globalThis.fetch = vi.fn().mockImplementation((url: string) => {
    if (url.includes('/auth/me/')) {
      if (mockUser) {
        return Promise.resolve({
          ok: true,
          json: async () => mockUser,
        });
      }
      return Promise.resolve({
        ok: false,
        status: 401,
        json: async () => ({ detail: 'Unauthenticated' }),
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
        <Layout>
          <div>Page Content</div>
        </Layout>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

describe('Responsive Mobile Navigation', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('renders mobile menu trigger with proper ARIA attributes', () => {
    renderLayout();
    const trigger = screen.getByTestId('mobile-menu-trigger');
    expect(trigger).toBeInTheDocument();
    expect(trigger).toHaveAttribute('aria-expanded', 'false');
    expect(trigger).toHaveAttribute('aria-controls', 'mobile-navigation');
    expect(trigger).toHaveAttribute('aria-label', 'Open navigation menu');
  });

  it('opens mobile navigation drawer on trigger click and closes on second click', () => {
    renderLayout();
    const trigger = screen.getByTestId('mobile-menu-trigger');

    // Open menu
    fireEvent.click(trigger);
    expect(trigger).toHaveAttribute('aria-expanded', 'true');
    expect(screen.getByTestId('mobile-navigation-menu')).toBeInTheDocument();
    expect(screen.getByTestId('mobile-nav-issues')).toBeInTheDocument();
    expect(screen.getByTestId('mobile-nav-projects')).toBeInTheDocument();
    expect(screen.getByTestId('mobile-nav-leaderboard')).toBeInTheDocument();
    expect(screen.getByTestId('mobile-nav-login')).toBeInTheDocument();

    // Close menu
    fireEvent.click(trigger);
    expect(trigger).toHaveAttribute('aria-expanded', 'false');
    expect(screen.queryByTestId('mobile-navigation-menu')).not.toBeInTheDocument();
  });

  it('shows My Profile in mobile navigation when authenticated', async () => {
    const mockUser = {
      id: 1,
      user_id: 1,
      github_id: 12345,
      github_username: 'sarah_dev',
      avatar_url: null,
      is_suspended: false,
      total_points: 420,
      is_staff: false,
      is_authenticated: true,
    };

    renderLayout('/', mockUser);

    // Wait for user query to resolve
    await waitFor(() => {
      expect(screen.getByTestId('profile-avatar-button')).toBeInTheDocument();
    });

    const trigger = screen.getByTestId('mobile-menu-trigger');
    fireEvent.click(trigger);

    expect(screen.getByTestId('mobile-nav-profile')).toBeInTheDocument();
    expect(screen.getByText('420 pts')).toBeInTheDocument();
    expect(screen.getByTestId('mobile-nav-logout')).toBeInTheDocument();
  });

  it('closes mobile menu on Escape key and restores focus', () => {
    renderLayout();
    const trigger = screen.getByTestId('mobile-menu-trigger');

    fireEvent.click(trigger);
    expect(screen.getByTestId('mobile-navigation-menu')).toBeInTheDocument();

    fireEvent.keyDown(document, { key: 'Escape' });
    expect(screen.queryByTestId('mobile-navigation-menu')).not.toBeInTheDocument();
  });

  it('closes mobile menu when clicking outside', () => {
    renderLayout();
    const trigger = screen.getByTestId('mobile-menu-trigger');

    fireEvent.click(trigger);
    expect(screen.getByTestId('mobile-navigation-menu')).toBeInTheDocument();

    fireEvent.mouseDown(document.body);
    expect(screen.queryByTestId('mobile-navigation-menu')).not.toBeInTheDocument();
  });

  it('closes mobile navigation when a nav link is clicked', () => {
    renderLayout();
    const trigger = screen.getByTestId('mobile-menu-trigger');

    fireEvent.click(trigger);
    const issuesLink = screen.getByTestId('mobile-nav-issues');
    fireEvent.click(issuesLink);

    expect(screen.queryByTestId('mobile-navigation-menu')).not.toBeInTheDocument();
  });

  it('renders clean accessible footer with current year and valid links', () => {
    renderLayout();
    const currentYear = new Date().getFullYear().toString();
    expect(screen.getByText(new RegExp(`© ${currentYear} CommitRush`))).toBeInTheDocument();
    expect(screen.getAllByRole('link', { name: 'Issues' }).length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByRole('link', { name: 'Projects' }).length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByRole('link', { name: 'Leaderboard' }).length).toBeGreaterThanOrEqual(1);
    expect(screen.getByLabelText(/Official HackIT repository on GitHub/i)).toHaveAttribute(
      'href',
      'https://github.com/Hackit-DROID/Open-Source-Contribution-Drive'
    );
  });
});
