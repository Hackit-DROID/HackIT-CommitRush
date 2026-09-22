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

// Helpers to build mock GitHub Contents API responses
function makeGitHubDir(name: string) {
  return {
    name,
    path: name,
    sha: `sha-${name}`,
    size: 0,
    url: `https://api.github.com/repos/Hackit-DROID/Open-Source-Contribution-Drive/contents/${name}`,
    html_url: `https://github.com/Hackit-DROID/Open-Source-Contribution-Drive/tree/main/${name}`,
    git_url: `https://api.github.com/repos/Hackit-DROID/Open-Source-Contribution-Drive/git/trees/sha-${name}`,
    type: 'dir',
  };
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

  it('renders project list from GitHub monorepo', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => [
        makeGitHubDir('AI_Data_Analyst_Agent'),
        makeGitHubDir('AI_Data_Analyst_Agent_2'),
        makeGitHubDir('Blood_Donation_Management_System'),
        { name: 'README.md', path: 'README.md', sha: 'sha-readme', size: 500, type: 'file', url: '', html_url: '', git_url: '' },
      ],
    } as Response);

    renderWithProviders(<ProjectsExplorerPage />);

    await waitFor(() => {
      // Grouped: "AI Data Analyst Agent" (2 variants) + "Blood Donation Management System" (1 variant)
      expect(screen.getByText('AI Data Analyst Agent')).toBeInTheDocument();
      expect(screen.getByText('Blood Donation Management System')).toBeInTheDocument();
      // Variant count "2" appears alongside "variants in the monorepo"
      expect(screen.getByText(/variants? in the monorepo/)).toBeInTheDocument();
    });
  });

  it('renders empty state when no projects match filters', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => [
        { name: 'README.md', path: 'README.md', sha: 'sha-readme', size: 500, type: 'file', url: '', html_url: '', git_url: '' },
      ],
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
        json: async () => [],
      } as Response);

    globalThis.fetch = fetchMock;

    renderWithProviders(<ProjectsExplorerPage />);

    await waitFor(() => {
      expect(screen.getByTestId('error-state')).toBeInTheDocument();
    });

    const retryBtn = screen.getByRole('button', { name: /retry/i });
    fireEvent.click(retryBtn);
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it('client-side search filters projects by name', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => [
        makeGitHubDir('AI_Data_Analyst_Agent'),
        makeGitHubDir('Blood_Donation_Management_System'),
        makeGitHubDir('College_Academic_Portal'),
      ],
    } as Response);

    renderWithProviders(<ProjectsExplorerPage />);

    await waitFor(() => {
      expect(screen.getByText('AI Data Analyst Agent')).toBeInTheDocument();
    });

    const searchInput = screen.getByPlaceholderText(/search project name/i);
    fireEvent.change(searchInput, { target: { value: 'Blood' } });
    fireEvent.submit(searchInput.closest('form')!);

    await waitFor(() => {
      expect(screen.getByText('Blood Donation Management System')).toBeInTheDocument();
      expect(screen.queryByText('AI Data Analyst Agent')).not.toBeInTheDocument();
      expect(screen.queryByText('College Academic Portal')).not.toBeInTheDocument();
    });
  });
});
