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

  it('renders category selector with "Category: All Categories" and all 16 supported categories', async () => {
    globalThis.fetch = vi.fn().mockImplementation(async (url: string) => {
      if (url.includes('/issues/categories/')) {
        return {
          ok: true,
          json: async () => [
            { value: 'feature', label: 'Features', count: 844 },
            { value: 'test', label: 'Testing & QA', count: 147 },
            { value: 'bug', label: 'Bug Fixes', count: 132 },
            { value: 'security', label: 'Security', count: 112 },
            { value: 'performance', label: 'Performance', count: 99 },
            { value: 'docs', label: 'Documentation', count: 75 },
            { value: 'refactor', label: 'Refactoring', count: 32 },
            { value: 'validation', label: 'Validation', count: 30 },
            { value: 'ui', label: 'UI', count: 30 },
            { value: 'database', label: 'Database & Storage', count: 3 },
            { value: 'networking', label: 'Networking', count: 3 },
            { value: 'frontend', label: 'Frontend', count: 3 },
            { value: 'backend', label: 'Backend', count: 3 },
            { value: 'devops', label: 'DevOps / Infrastructure', count: 1 },
            { value: 'fullstack', label: 'Fullstack', count: 1 },
            { value: 'dx', label: 'Developer Experience', count: 1 },
          ],
        } as Response;
      }
      return {
        ok: true,
        json: async () => ({ count: 0, next: null, previous: null, results: [] }),
      } as Response;
    });

    renderWithProviders();

    const categorySelect = screen.getByLabelText(/filter by issue category/i) as HTMLSelectElement;
    expect(categorySelect).toBeInTheDocument();

    const options = Array.from(categorySelect.options).map((opt) => opt.text);
    expect(options[0]).toBe('Category: All Categories');
    expect(options).toContain('Features');
    expect(options).toContain('Testing & QA');
    expect(options).toContain('Bug Fixes');
    expect(options).toContain('Security');
    expect(options).toContain('Performance');
    expect(options).toContain('Documentation');
    expect(options).toContain('Refactoring');
    expect(options).toContain('Validation');
    expect(options).toContain('UI');
    expect(options).toContain('Database & Storage');
    expect(options).toContain('Networking');
    expect(options).toContain('Frontend');
    expect(options).toContain('Backend');
    expect(options).toContain('DevOps / Infrastructure');
    expect(options).toContain('Fullstack');
    expect(options).toContain('Developer Experience');
    expect(categorySelect.options.length).toBe(17);
  });

  it('changing category filter updates fetch query with category parameter', async () => {
    const fetchMock = vi.fn().mockImplementation(async (url: string) => {
      if (url.includes('/issues/categories/')) {
        return {
          ok: true,
          json: async () => [
            { value: 'feature', label: 'Features', count: 844 },
            { value: 'security', label: 'Security', count: 112 },
          ],
        } as Response;
      }
      return {
        ok: true,
        json: async () => ({ count: 0, next: null, previous: null, results: [] }),
      } as Response;
    });

    globalThis.fetch = fetchMock;

    renderWithProviders();

    const categorySelect = screen.getByLabelText(/filter by issue category/i);
    fireEvent.change(categorySelect, { target: { value: 'security' } });

    await waitFor(() => {
      const calls = fetchMock.mock.calls;
      const matchingCall = calls.find((c) => (c[0] as string).includes('category=security'));
      expect(matchingCall).toBeTruthy();
    });
  });

  it('displays category badge on issue card with human-readable label', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        count: 1,
        next: null,
        previous: null,
        results: [
          {
            id: 99,
            title: 'Fix CSRF token validation',
            project: 'hackit/security-core',
            github_number: 202,
            points: 150,
            difficulty: 'advanced',
            category: 'security',
            status: 'open',
            is_featured: false,
            labels: ['security', 'auth'],
            github_url: 'https://github.com/hackit/security-core/issues/202',
          },
        ],
      }),
    } as Response);

    renderWithProviders('/issues?category=security');

    await waitFor(() => {
      expect(screen.getByText('Security')).toBeInTheDocument();
      expect(screen.getByText('Category: Security')).toBeInTheDocument();
    });
  });
});
