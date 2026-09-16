import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ProjectDetailPage } from '../pages/ProjectDetailPage';

function renderWithProviders(slug: string) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[`/projects/${slug}`]}>
        <Routes>
          <Route path="/projects/*" element={<ProjectDetailPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

describe('ProjectDetailPage', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('renders loading skeleton initially', () => {
    globalThis.fetch = vi.fn().mockImplementation(() => new Promise(() => {}));
    renderWithProviders('hackit/backend-core');
    expect(screen.getByTestId('project-detail-skeleton')).toBeInTheDocument();
  });

  it('renders project metadata, issue counts, and contribution activity', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        id: 1,
        github_repo_id: 101,
        owner: 'hackit',
        name: 'backend-core',
        full_name: 'hackit/backend-core',
        language: 'Python',
        is_enabled: true,
        description: 'Core backend service for CommitRush',
        issue_count: 15,
        open_issue_count: 10,
        contribution_activity: {
          total_contributions: 8,
          merged_contributions: 5,
          in_progress_contributions: 3,
        },
      }),
    } as Response);

    renderWithProviders('hackit/backend-core');

    await waitFor(() => {
      expect(screen.getByText('backend-core')).toBeInTheDocument();
      expect(screen.getByText('hackit')).toBeInTheDocument();
      expect(screen.getByText('Core backend service for CommitRush')).toBeInTheDocument();
      expect(screen.getByText('15')).toBeInTheDocument();
      expect(screen.getByText(/10 open for contributions/i)).toBeInTheDocument();
      expect(screen.getByText('5')).toBeInTheDocument();
      expect(screen.getByText('3')).toBeInTheDocument();
    });
  });

  it('renders 404 not found error state when project does not exist', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 404,
      statusText: 'Not Found',
      json: async () => ({ detail: "Project 'nonexistent' not found." }),
    } as Response);

    renderWithProviders('nonexistent');

    await waitFor(() => {
      expect(screen.getByTestId('error-state')).toBeInTheDocument();
      expect(screen.getByText('Resource Not Found')).toBeInTheDocument();
    });
  });
});
