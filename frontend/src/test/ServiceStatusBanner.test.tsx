import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ServiceStatusBanner } from '../components/ServiceStatusBanner';

function renderWithProviders() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <ServiceStatusBanner />
    </QueryClientProvider>
  );
}

describe('ServiceStatusBanner (M7-T7)', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('renders nothing in normal operating state (all pause/freeze flags false)', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        event_status: 'active',
        system_status: {
          merge_paused: false,
          validation_paused: false,
          submissions_paused: false,
          leaderboard_frozen: false,
        },
      }),
    });

    renderWithProviders();

    await waitFor(() => {
      expect(screen.queryByTestId('service-status-banner')).not.toBeInTheDocument();
    });
  });

  it('renders merge paused banner when merge_paused is true', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        event_status: 'active',
        system_status: {
          merge_paused: true,
          validation_paused: false,
          submissions_paused: false,
          leaderboard_frozen: false,
        },
      }),
    });

    renderWithProviders();

    await waitFor(() => {
      expect(screen.getByTestId('service-status-banner')).toBeInTheDocument();
    });

    expect(screen.getByTestId('banner-notice-merge-paused')).toBeInTheDocument();
    expect(
      screen.getByText(/Merge processing temporarily paused by admins/i)
    ).toBeInTheDocument();
  });

  it('renders submissions paused notice when submissions_paused is true', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        event_status: 'active',
        system_status: {
          merge_paused: false,
          validation_paused: false,
          submissions_paused: true,
          leaderboard_frozen: false,
        },
      }),
    });

    renderWithProviders();

    await waitFor(() => {
      expect(screen.getByTestId('service-status-banner')).toBeInTheDocument();
    });

    expect(screen.getByTestId('banner-notice-submissions-paused')).toBeInTheDocument();
    expect(
      screen.getByText(/New webhook submissions temporarily paused/i)
    ).toBeInTheDocument();
  });

  it('renders leaderboard frozen notice when leaderboard_frozen is true', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        event_status: 'active',
        system_status: {
          merge_paused: false,
          validation_paused: false,
          submissions_paused: false,
          leaderboard_frozen: true,
        },
      }),
    });

    renderWithProviders();

    await waitFor(() => {
      expect(screen.getByTestId('service-status-banner')).toBeInTheDocument();
    });

    expect(screen.getByTestId('banner-notice-leaderboard-frozen')).toBeInTheDocument();
    expect(
      screen.getByText(/Public leaderboard rankings are frozen/i)
    ).toBeInTheDocument();
  });

  it('renders multiple simultaneous degraded conditions cleanly', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        event_status: 'active',
        system_status: {
          merge_paused: true,
          validation_paused: true,
          submissions_paused: true,
          leaderboard_frozen: true,
        },
      }),
    });

    renderWithProviders();

    await waitFor(() => {
      expect(screen.getByTestId('service-status-banner')).toBeInTheDocument();
    });

    expect(screen.getByTestId('banner-notice-merge-paused')).toBeInTheDocument();
    expect(screen.getByTestId('banner-notice-validation-paused')).toBeInTheDocument();
    expect(screen.getByTestId('banner-notice-submissions-paused')).toBeInTheDocument();
    expect(screen.getByTestId('banner-notice-leaderboard-frozen')).toBeInTheDocument();
  });
});
