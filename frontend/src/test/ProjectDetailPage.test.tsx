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
    renderWithProviders('AI_Data_Analyst_Agent');
    expect(screen.getByTestId('project-detail-skeleton')).toBeInTheDocument();
  });

  it('renders project files from GitHub monorepo', async () => {
    // The detail page makes two fetch calls:
    // 1. Directory contents
    // 2. README.md raw content
    globalThis.fetch = vi.fn().mockImplementation((url: string) => {
      if (typeof url === 'string' && url.includes('raw.githubusercontent.com')) {
        return Promise.resolve({
          ok: true,
          text: async () => '# AI Data Analyst Agent\n\nA data analysis tool.',
        });
      }
      // Directory contents
      return Promise.resolve({
        ok: true,
        json: async () => [
          {
            name: 'app.py',
            path: 'AI_Data_Analyst_Agent/app.py',
            sha: 'sha-app',
            size: 2048,
            url: 'https://api.github.com/repos/Hackit-DROID/Open-Source-Contribution-Drive/contents/AI_Data_Analyst_Agent/app.py',
            html_url: 'https://github.com/Hackit-DROID/Open-Source-Contribution-Drive/blob/main/AI_Data_Analyst_Agent/app.py',
            git_url: '',
            type: 'file',
          },
          {
            name: 'requirements.txt',
            path: 'AI_Data_Analyst_Agent/requirements.txt',
            sha: 'sha-req',
            size: 256,
            url: '',
            html_url: '',
            git_url: '',
            type: 'file',
          },
          {
            name: 'README.md',
            path: 'AI_Data_Analyst_Agent/README.md',
            sha: 'sha-readme',
            size: 512,
            url: '',
            html_url: '',
            git_url: '',
            type: 'file',
          },
        ],
      });
    });

    renderWithProviders('AI_Data_Analyst_Agent');

    await waitFor(() => {
      expect(screen.getByTestId('project-detail-view')).toBeInTheDocument();
      expect(screen.getByText('AI Data Analyst Agent')).toBeInTheDocument();
      expect(screen.getByText('app.py')).toBeInTheDocument();
      expect(screen.getByText('requirements.txt')).toBeInTheDocument();
      expect(screen.getByText('README.md')).toBeInTheDocument();
    });
  });

  it('renders error state when project directory does not exist', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 404,
      statusText: 'Not Found',
      json: async () => ({ message: 'Not Found' }),
    } as Response);

    renderWithProviders('nonexistent');

    await waitFor(() => {
      expect(screen.getByTestId('error-state')).toBeInTheDocument();
    });
  });
});
