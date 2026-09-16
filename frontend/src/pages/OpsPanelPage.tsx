import { useState } from 'react';
import { useOpsMetrics } from '../api/ops';
import { ApiError } from '../types/api';

export default function OpsPanelPage() {
  const [autoRefresh, setAutoRefresh] = useState(true);
  const { data, isLoading, error, refetch, isFetching } = useOpsMetrics(
    autoRefresh ? 15_000 : false
  );

  if (isLoading) {
    return (
      <div className="space-y-6 animate-pulse">
        <div className="h-8 w-64 bg-slate-800 rounded"></div>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="h-28 bg-slate-800/60 rounded-xl"></div>
          ))}
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="h-64 bg-slate-800/60 rounded-xl"></div>
          <div className="h-64 bg-slate-800/60 rounded-xl"></div>
        </div>
      </div>
    );
  }

  if (error) {
    const isForbidden = error instanceof ApiError && error.status === 403;
    return (
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-8 text-center max-w-lg mx-auto my-12">
        <div className="inline-flex p-3 rounded-full bg-red-500/10 text-red-400 mb-4">
          <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m0 0v.01M12 9v4m-8.485 8.485h16.97a2 2 0 001.789-2.894L13.79 3.106a2 2 0 00-3.578 0L3.696 17.591a2 2 0 001.789 2.894z" />
          </svg>
        </div>
        <h2 className="text-xl font-bold text-slate-100 mb-2">
          {isForbidden ? 'Staff Authorization Required' : 'Failed to Load Ops Metrics'}
        </h2>
        <p className="text-slate-400 text-sm mb-6">
          {isForbidden
            ? 'Access to the Operations Control Panel is restricted to event administrators and staff accounts.'
            : 'Unable to connect to the operational telemetry backend.'}
        </p>
        <div className="flex justify-center gap-3">
          {isForbidden ? (
            <a
              href="/admin/"
              className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-medium rounded-lg transition-colors"
            >
              Log in to Django Admin
            </a>
          ) : (
            <button
              onClick={() => refetch()}
              className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 text-sm font-medium rounded-lg transition-colors"
            >
              Retry Connection
            </button>
          )}
        </div>
      </div>
    );
  }

  if (!data) return null;

  const { system_status, queues, semaphore, oldest_queued_item_age_seconds, last_webhook_received_at } = data;

  return (
    <div className="space-y-8">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-slate-800 pb-5">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold text-slate-100">Operations Control Panel</h1>
            <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
              Internal Ops
            </span>
          </div>
          <p className="text-sm text-slate-400 mt-1">
            Real-time pipeline health, queue depth telemetry, and emergency controls.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <label className="flex items-center gap-2 text-xs text-slate-400 cursor-pointer">
            <input
              type="checkbox"
              checked={autoRefresh}
              onChange={(e) => setAutoRefresh(e.target.checked)}
              className="rounded border-slate-700 bg-slate-800 text-indigo-600 focus:ring-indigo-500"
            />
            Auto-refresh (15s)
          </label>
          <button
            onClick={() => refetch()}
            disabled={isFetching}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium rounded-lg border border-slate-700 transition-colors disabled:opacity-50"
          >
            <svg
              className={`w-3.5 h-3.5 ${isFetching ? 'animate-spin' : ''}`}
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
            Refresh Now
          </button>
        </div>
      </div>

      {/* Emergency Status Grid */}
      <div>
        <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-400 mb-3">
          Runtime Emergency Switches
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <div className={`p-4 rounded-xl border ${system_status.submissions_paused ? 'bg-red-950/30 border-red-800/60' : 'bg-slate-900 border-slate-800'}`}>
            <div className="text-xs text-slate-400 font-medium">Submissions</div>
            <div className="mt-2 flex items-center justify-between">
              <span className={`text-lg font-bold ${system_status.submissions_paused ? 'text-red-400' : 'text-emerald-400'}`}>
                {system_status.submissions_paused ? 'PAUSED' : 'ACTIVE'}
              </span>
              <span className={`w-2.5 h-2.5 rounded-full ${system_status.submissions_paused ? 'bg-red-500 animate-pulse' : 'bg-emerald-500'}`} />
            </div>
          </div>

          <div className={`p-4 rounded-xl border ${system_status.validation_paused ? 'bg-red-950/30 border-red-800/60' : 'bg-slate-900 border-slate-800'}`}>
            <div className="text-xs text-slate-400 font-medium">Validation Pipeline</div>
            <div className="mt-2 flex items-center justify-between">
              <span className={`text-lg font-bold ${system_status.validation_paused ? 'text-red-400' : 'text-emerald-400'}`}>
                {system_status.validation_paused ? 'PAUSED' : 'ACTIVE'}
              </span>
              <span className={`w-2.5 h-2.5 rounded-full ${system_status.validation_paused ? 'bg-red-500 animate-pulse' : 'bg-emerald-500'}`} />
            </div>
          </div>

          <div className={`p-4 rounded-xl border ${system_status.merge_paused ? 'bg-red-950/30 border-red-800/60' : 'bg-slate-900 border-slate-800'}`}>
            <div className="text-xs text-slate-400 font-medium">Merge Queue</div>
            <div className="mt-2 flex items-center justify-between">
              <span className={`text-lg font-bold ${system_status.merge_paused ? 'text-red-400' : 'text-emerald-400'}`}>
                {system_status.merge_paused ? 'PAUSED' : 'ACTIVE'}
              </span>
              <span className={`w-2.5 h-2.5 rounded-full ${system_status.merge_paused ? 'bg-red-500 animate-pulse' : 'bg-emerald-500'}`} />
            </div>
          </div>

          <div className={`p-4 rounded-xl border ${system_status.leaderboard_frozen ? 'bg-blue-950/30 border-blue-800/60' : 'bg-slate-900 border-slate-800'}`}>
            <div className="text-xs text-slate-400 font-medium">Leaderboard</div>
            <div className="mt-2 flex items-center justify-between">
              <span className={`text-lg font-bold ${system_status.leaderboard_frozen ? 'text-blue-400' : 'text-emerald-400'}`}>
                {system_status.leaderboard_frozen ? 'FROZEN' : 'LIVE'}
              </span>
              <span className={`w-2.5 h-2.5 rounded-full ${system_status.leaderboard_frozen ? 'bg-blue-500' : 'bg-emerald-500'}`} />
            </div>
          </div>
        </div>
      </div>

      {/* Telemetry & Queues Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Queue Depths Card */}
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-6">
          <h2 className="text-base font-semibold text-slate-100 mb-4 flex items-center justify-between">
            <span>Queue Depth & Workload</span>
            <span className="text-xs text-slate-400 font-normal">PostgreSQL + Celery</span>
          </h2>
          <div className="space-y-4">
            <div className="flex items-center justify-between p-3 bg-slate-950/60 rounded-lg border border-slate-800/80">
              <div>
                <div className="text-sm font-medium text-slate-200">Validation Queue</div>
                <div className="text-xs text-slate-400">Waiting in queue / Under review</div>
              </div>
              <div className="text-right">
                <div className="text-lg font-bold text-slate-100">
                  {queues.validation_queued + queues.validation_under_review}
                </div>
                <div className="text-xs text-slate-400">
                  {queues.validation_queued} queued, {queues.validation_under_review} review
                </div>
              </div>
            </div>

            <div className="flex items-center justify-between p-3 bg-slate-950/60 rounded-lg border border-slate-800/80">
              <div>
                <div className="text-sm font-medium text-slate-200">Merge Queue</div>
                <div className="text-xs text-slate-400">Approved waiting / Actively merging</div>
              </div>
              <div className="text-right">
                <div className="text-lg font-bold text-slate-100">
                  {queues.merge_approved + queues.merge_active}
                </div>
                <div className="text-xs text-slate-400">
                  {queues.merge_approved} queued, {queues.merge_active} active
                </div>
              </div>
            </div>

            <div className="flex items-center justify-between p-3 bg-slate-950/60 rounded-lg border border-slate-800/80">
              <div>
                <div className="text-sm font-medium text-slate-200">Held for Admin / Retries</div>
                <div className="text-xs text-slate-400">Flagged suspicious or retry backoff</div>
              </div>
              <div className="text-right">
                <div className={`text-lg font-bold ${queues.flagged_or_retry > 0 ? 'text-amber-400' : 'text-slate-100'}`}>
                  {queues.flagged_or_retry}
                </div>
              </div>
            </div>

            <div className="flex items-center justify-between p-3 bg-slate-950/60 rounded-lg border border-slate-800/80">
              <div>
                <div className="text-sm font-medium text-slate-200">Inbound Webhooks</div>
                <div className="text-xs text-slate-400">Total persisted / Pending async worker</div>
              </div>
              <div className="text-right">
                <div className="text-lg font-bold text-slate-100">{queues.webhooks_total}</div>
                <div className="text-xs text-slate-400">{queues.webhooks_unprocessed} unprocessed</div>
              </div>
            </div>
          </div>
        </div>

        {/* Merge Concurrency & Health Card */}
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 flex flex-col justify-between">
          <div>
            <h2 className="text-base font-semibold text-slate-100 mb-4 flex items-center justify-between">
              <span>Merge Semaphore & Health</span>
              <span className="text-xs text-slate-400 font-normal">Redis Distributed Gate</span>
            </h2>

            <div className="space-y-5">
              {/* Semaphore Bar */}
              <div>
                <div className="flex justify-between text-xs mb-1.5">
                  <span className="text-slate-400">Active Merge Bot Slots</span>
                  <span className="font-semibold text-slate-200">
                    {semaphore.active_semaphore_slots} / {semaphore.configured_concurrency} max
                  </span>
                </div>
                <div className="w-full h-3 bg-slate-950 rounded-full overflow-hidden border border-slate-800">
                  <div
                    className="h-full bg-indigo-500 rounded-full transition-all duration-500"
                    style={{
                      width: `${Math.min(
                        100,
                        (semaphore.active_semaphore_slots / (semaphore.configured_concurrency || 1)) * 100
                      )}%`,
                    }}
                  />
                </div>
                <div className="flex justify-between text-xs text-slate-400 mt-1">
                  <span>Available slots: {semaphore.available_slots}</span>
                  <span>Cap: {semaphore.configured_concurrency} concurrent</span>
                </div>
              </div>

              {/* Latency / Oldest Item */}
              <div className="p-4 bg-slate-950/60 rounded-lg border border-slate-800/80">
                <div className="text-xs text-slate-400">Oldest Queued Contribution Latency</div>
                <div className="text-xl font-bold text-slate-100 mt-1">
                  {oldest_queued_item_age_seconds !== null
                    ? `${oldest_queued_item_age_seconds}s in queue`
                    : 'Queue is clear (0s)'}
                </div>
              </div>

              {/* Last Webhook Timestamp */}
              <div className="p-4 bg-slate-950/60 rounded-lg border border-slate-800/80">
                <div className="text-xs text-slate-400">Last Inbound Webhook Activity</div>
                <div className="text-sm font-semibold text-slate-200 mt-1">
                  {last_webhook_received_at
                    ? new Date(last_webhook_received_at).toLocaleString()
                    : 'No webhooks received yet'}
                </div>
              </div>
            </div>
          </div>

          <div className="mt-6 pt-4 border-t border-slate-800/80 flex items-center justify-between text-xs text-slate-400">
            <span>Event Status: <strong className="text-slate-200 uppercase">{data.event_status}</strong></span>
            <a
              href="/admin/"
              className="text-indigo-400 hover:text-indigo-300 font-medium inline-flex items-center gap-1"
            >
              Open Django Admin &rarr;
            </a>
          </div>
        </div>
      </div>
    </div>
  );
}
