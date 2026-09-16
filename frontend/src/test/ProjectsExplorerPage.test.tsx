import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ProjectsExplorerPage } from '../pages/ProjectsExplorerPage';

function renderWithProviders(ui: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>{ui}</MemoryRouter>
    </QueryClientProvider>
  );
}

describe('ProjectsExplorerPage', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('renders loading skeleton initially', () => {
    globalThis.fetch = vi.fn().mockImplementation(() => new Promise(() => {}));
    renderWithProviders(<ProjectsExplorerPage />);
    expect(screen.getByTestId('projects-skeleton')).toBeInTheDocument();
  });

  it('renders project list successfully', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        count: 2,
        next: null,
        previous: null,
        results: [
          {
            id: 1,
            github_repo_id: 101,
            owner: 'hackit',
            name: 'backend-core',
            full_name: 'hackit/backend-core',
            language: 'Python',
            is_enabled: true,
            description: 'Core backend service',
          },
          {
            id: 2,
            github_repo_id: 102,
            owner: 'hackit',
            name: 'frontend-ui',
            full_name: 'hackit/frontend-ui',
            language: 'TypeScript',
            is_enabled: false,
            description: 'UI client',
          },
        ],
      }),
    } as Response);

    renderWithProviders(<ProjectsExplorerPage />);

    await waitFor(() => {
      expect(screen.getByText('hackit/backend-core')).toBeInTheDocument();
      expect(screen.getByText('hackit/frontend-ui')).toBeInTheDocument();
      expect(screen.getByText('Active')).toBeInTheDocument();
      expect(screen.getByText('Disabled')).toBeInTheDocument();
    });
  });

  it('renders empty state when no projects match filters', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        count: 0,
        next: null,
        previous: null,
        results: [],
      }),
    } as Response);

    renderWithProviders(<ProjectsExplorerPage />);

    await waitFor(() => {
      expect(screen.getByTestId('empty-state')).toBeInTheDocument();
      expect(screen.getByText('No projects found')).toBeInTheDocument();
    });
  });

  it('renders error state on API failure with retry action', async () => {
    const fetchMock = vi
      .fn()
      .mockRejectedValueOnce(new Error('Network error'))
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ count: 0, next: null, previous: null, results: [] }),
      } as Response);

    globalThis.fetch = fetchMock;

    renderWithProviders(<ProjectsExplorerPage />);

    await waitFor(() => {
      expect(screen.getByTestId('error-state')).toBeInTheDocument();
      expect(screen.getByText('Network error')).toBeInTheDocument();
    });

    const retryBtn = screen.getByRole('button', { name: /retry/i });
    fireEvent.click(retryBtn);
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it('renders rate-limit error message on HTTP 429', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 429,
      statusText: 'Too Many Requests',
      json: async () => ({ detail: 'Request was throttled.' }),
    } as Response);

    renderWithProviders(<ProjectsExplorerPage />);

    await waitFor(() => {
      expect(screen.getByText('Rate Limit Exceeded')).toBeInTheDocument();
    });
  });

  it('submitting search updates query and fetches filtered data', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        count: 1,
        next: null,
        previous: null,
        results: [
          {
            id: 1,
            github_repo_id: 101,
            owner: 'hackit',
            name: 'backend-core',
            full_name: 'hackit/backend-core',
            language: 'Python',
            is_enabled: true,
            description: 'Core backend service',
          },
        ],
      }),
    } as Response);

    globalThis.fetch = fetchMock;

    renderWithProviders(<ProjectsExplorerPage />);

    const searchInput = screen.getByPlaceholderText(/search repo name or description/i);
    fireEvent.change(searchInput, { target: { value: 'backend' } });
    fireEvent.submit(searchInput.closest('form')!);

    await waitFor(() => {
      const calls = fetchMock.mock.calls;
      const lastUrl = calls[calls.length - 1][0] as string;
      expect(lastUrl).toContain('search=backend');
    });
  });
});
