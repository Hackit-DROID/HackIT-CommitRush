import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { BrowserRouter } from 'react-router-dom';
import OpsPanelPage from '../pages/OpsPanelPage';
import * as opsApi from '../api/ops';
import { ApiError } from '../types/api';

vi.mock('../api/ops', () => ({
  useOpsMetrics: vi.fn(),
}));

const mockOpsData = {
  event_status: 'active',
  system_status: {
    submissions_paused: false,
    validation_paused: true,
    merge_paused: false,
    leaderboard_frozen: true,
  },
  queues: {
    validation_queued: 4,
    validation_under_review: 2,
    merge_approved: 3,
    merge_active: 1,
    flagged_or_retry: 2,
    webhooks_total: 120,
    webhooks_unprocessed: 5,
  },
  semaphore: {
    configured_concurrency: 8,
    active_semaphore_slots: 3,
    available_slots: 5,
  },
  oldest_queued_item_age_seconds: 45,
  last_webhook_received_at: '2026-09-16T18:00:00Z',
  generated_at: '2026-09-16T18:05:00Z',
};

describe('OpsPanelPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders loading state correctly', () => {
    vi.mocked(opsApi.useOpsMetrics).mockReturnValue({
      data: undefined,
      isLoading: true,
      error: null,
      refetch: vi.fn(),
      isFetching: false,
    } as any);

    const { container } = render(
      <BrowserRouter>
        <OpsPanelPage />
      </BrowserRouter>
    );

    expect(container.querySelector('.animate-pulse')).toBeInTheDocument();
  });

  it('renders 403 authorization required error for non-staff users', () => {
    vi.mocked(opsApi.useOpsMetrics).mockReturnValue({
      data: undefined,
      isLoading: false,
      error: new ApiError(403, 'Forbidden'),
      refetch: vi.fn(),
      isFetching: false,
    } as any);

    render(
      <BrowserRouter>
        <OpsPanelPage />
      </BrowserRouter>
    );

    expect(screen.getByText('Staff Authorization Required')).toBeInTheDocument();
    expect(screen.getByText('Log in to Django Admin')).toBeInTheDocument();
  });

  it('renders operational metrics, switches, and queues when authorized', () => {
    vi.mocked(opsApi.useOpsMetrics).mockReturnValue({
      data: mockOpsData,
      isLoading: false,
      error: null,
      refetch: vi.fn(),
      isFetching: false,
    } as any);

    render(
      <BrowserRouter>
        <OpsPanelPage />
      </BrowserRouter>
    );

    // Title
    expect(screen.getByText('Operations Control Panel')).toBeInTheDocument();

    // Emergency switches status
    expect(screen.getByText('Submissions')).toBeInTheDocument();
    expect(screen.getByText('Validation Pipeline')).toBeInTheDocument();
    expect(screen.getAllByText('Merge Queue').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('Leaderboard')).toBeInTheDocument();

    // Specific states
    expect(screen.getByText('PAUSED')).toBeInTheDocument(); // validation_paused is true
    expect(screen.getByText('FROZEN')).toBeInTheDocument(); // leaderboard_frozen is true

    // Queues
    expect(screen.getByText('Validation Queue')).toBeInTheDocument();
    expect(screen.getByText('4 queued, 2 review')).toBeInTheDocument();
    expect(screen.getByText('3 queued, 1 active')).toBeInTheDocument();

    // Semaphore
    expect(screen.getByText('3 / 8 max')).toBeInTheDocument();
    expect(screen.getByText('Available slots: 5')).toBeInTheDocument();

    // Latency
    expect(screen.getByText('45s in queue')).toBeInTheDocument();
  });
});
