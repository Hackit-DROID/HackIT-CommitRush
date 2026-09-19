import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ProfileMenu } from '../components/ProfileMenu';
import { CurrentUser } from '../types/api';

const MOCK_USER: CurrentUser = {
  id: 1,
  user_id: 1,
  github_id: 12345,
  github_username: 'octodev',
  avatar_url: 'https://avatars.githubusercontent.com/u/12345',
  is_suspended: false,
  total_points: 350,
  is_staff: false,
  is_authenticated: true,
};

function renderProfileMenu(user: CurrentUser = MOCK_USER) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
    },
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <ProfileMenu user={user} />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

describe('ProfileMenu Component', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('renders circular avatar image with accessible alt text', () => {
    renderProfileMenu();
    const img = screen.getByTestId('profile-avatar-img');
    expect(img).toBeInTheDocument();
    expect(img).toHaveAttribute('src', 'https://avatars.githubusercontent.com/u/12345');
    expect(img).toHaveAttribute('alt', "octodev's profile avatar");
  });

  it('renders deterministic fallback initial when avatar_url is missing or fails to load', () => {
    const userWithoutAvatar: CurrentUser = {
      ...MOCK_USER,
      avatar_url: null,
    };
    renderProfileMenu(userWithoutAvatar);

    const fallback = screen.getByTestId('profile-avatar-fallback');
    expect(fallback).toBeInTheDocument();
    expect(fallback).toHaveTextContent('O');
  });

  it('toggles menu open and closed when clicking the avatar button', async () => {
    renderProfileMenu();
    const btn = screen.getByTestId('profile-avatar-button');
    expect(btn).toHaveAttribute('aria-expanded', 'false');
    expect(screen.queryByTestId('profile-dropdown-menu')).not.toBeInTheDocument();

    // Open menu
    fireEvent.click(btn);
    expect(btn).toHaveAttribute('aria-expanded', 'true');
    expect(screen.getByTestId('profile-dropdown-menu')).toBeInTheDocument();
    expect(screen.getByTestId('menu-username')).toHaveTextContent('@octodev');

    // Menu items
    expect(screen.getByTestId('menu-item-my-profile')).toBeInTheDocument();
    const ghLink = screen.getByTestId('menu-item-github-profile');
    expect(ghLink).toHaveAttribute('href', 'https://github.com/octodev');
    expect(ghLink).toHaveAttribute('target', '_blank');
    expect(screen.getByTestId('menu-item-logout')).toBeInTheDocument();

    // Close menu
    fireEvent.click(btn);
    expect(btn).toHaveAttribute('aria-expanded', 'false');
    expect(screen.queryByTestId('profile-dropdown-menu')).not.toBeInTheDocument();
  });

  it('closes menu when Escape key is pressed', () => {
    renderProfileMenu();
    const btn = screen.getByTestId('profile-avatar-button');

    fireEvent.click(btn);
    expect(screen.getByTestId('profile-dropdown-menu')).toBeInTheDocument();

    fireEvent.keyDown(document, { key: 'Escape' });
    expect(screen.queryByTestId('profile-dropdown-menu')).not.toBeInTheDocument();
  });

  it('closes menu when clicking outside', () => {
    renderProfileMenu();
    const btn = screen.getByTestId('profile-avatar-button');

    fireEvent.click(btn);
    expect(screen.getByTestId('profile-dropdown-menu')).toBeInTheDocument();

    fireEvent.mouseDown(document.body);
    expect(screen.queryByTestId('profile-dropdown-menu')).not.toBeInTheDocument();
  });

  it('calls logout mutation when clicking Sign Out', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ detail: 'Successfully logged out.' }),
    });

    renderProfileMenu();
    const btn = screen.getByTestId('profile-avatar-button');
    fireEvent.click(btn);

    const logoutBtn = screen.getByTestId('menu-item-logout');
    fireEvent.click(logoutBtn);

    await waitFor(() => {
      expect(screen.queryByTestId('profile-dropdown-menu')).not.toBeInTheDocument();
    });
  });
});
