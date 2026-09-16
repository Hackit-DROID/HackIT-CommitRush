import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { IssuesExplorerPage } from '../pages/IssuesExplorerPage';

function renderWithProviders(initialUrl = '/issues') {
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
        <IssuesExplorerPage />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

describe('IssuesExplorerPage', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('renders loading skeleton initially', () => {
    globalThis.fetch = vi.fn().mockImplementation(() => new Promise(() => {}));
    renderWithProviders();
    expect(screen.getByTestId('issues-skeleton')).toBeInTheDocument();
  });

  it('renders issue list items with title, project, points, labels, and github link', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        count: 1,
        next: null,
        previous: null,
        results: [
          {
            id: 42,
            title: 'Implement database connection pooling',
            project: 'hackit/backend-core',
            github_number: 101,
            points: 100,
            difficulty: 'advanced',
            category: 'backend',
            status: 'open',
            is_featured: true,
            labels: ['performance', 'database'],
            github_url: 'https://github.com/hackit/backend-core/issues/101',
          },
        ],
      }),
    } as Response);

    renderWithProviders();

    await waitFor(() => {
      expect(screen.getByText('Implement database connection pooling')).toBeInTheDocument();
      expect(screen.getByText('#101')).toBeInTheDocument();
      expect(screen.getByText('hackit/backend-core')).toBeInTheDocument();
      expect(screen.getByText('+100')).toBeInTheDocument();
      expect(screen.getByText('Featured')).toBeInTheDocument();
      expect(screen.getByText('performance')).toBeInTheDocument();
      expect(screen.getByText('database')).toBeInTheDocument();
    });
  });

  it('renders empty state when no issues match filters', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        count: 0,
        next: null,
        previous: null,
        results: [],
      }),
    } as Response);

    renderWithProviders();

    await waitFor(() => {
      expect(screen.getByTestId('empty-state')).toBeInTheDocument();
      expect(screen.getByText('No issues match your filters')).toBeInTheDocument();
    });
  });

  it('changing difficulty filter updates fetch query', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        count: 0,
        next: null,
        previous: null,
        results: [],
      }),
    } as Response);

    globalThis.fetch = fetchMock;

    renderWithProviders();

    const difficultySelect = screen.getByDisplayValue(/difficulty: all tiers/i);
    fireEvent.change(difficultySelect, { target: { value: 'beginner' } });

    await waitFor(() => {
      const calls = fetchMock.mock.calls;
      const lastUrl = calls[calls.length - 1][0] as string;
      expect(lastUrl).toContain('difficulty=beginner');
    });
  });

  it('changing sort selector triggers fetch with chosen sort key', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        count: 0,
        next: null,
        previous: null,
        results: [],
      }),
    } as Response);

    globalThis.fetch = fetchMock;

    renderWithProviders();

    const sortSelect = screen.getByDisplayValue(/sort: highest points first/i);
    fireEvent.change(sortSelect, { target: { value: 'newest' } });

    await waitFor(() => {
      const calls = fetchMock.mock.calls;
      const lastUrl = calls[calls.length - 1][0] as string;
      expect(lastUrl).toContain('sort=newest');
    });
  });
});
