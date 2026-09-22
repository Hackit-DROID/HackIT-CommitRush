import { useStats } from '../api/stats';

export function ServiceStatusBanner() {
  const { data } = useStats();

  if (!data?.system_status) {
    return null;
  }

  const { merge_paused, validation_paused, submissions_paused, leaderboard_frozen } = data.system_status;

  const notices: { id: string; message: string; type: 'warning' | 'info' }[] = [];

  if (merge_paused) {
    notices.push({
      id: 'merge-paused',
      message: 'Merge processing temporarily paused by admins. Approved contributions remain safely queued.',
      type: 'warning',
    });
  }

  if (submissions_paused) {
    notices.push({
      id: 'submissions-paused',
      message: 'New webhook submissions temporarily paused. Raw deliveries are safely recorded for processing upon resume.',
      type: 'warning',
    });
  }

  if (validation_paused) {
    notices.push({
      id: 'validation-paused',
      message: 'Contribution automated validation is temporarily paused.',
      type: 'warning',
    });
  }

  if (leaderboard_frozen) {
    notices.push({
      id: 'leaderboard-frozen',
      message: 'Public leaderboard rankings are frozen. Standings are currently locked.',
      type: 'info',
    });
  }

  if (notices.length === 0) {
    return null;
  }

  return (
    <div
      role="status"
      aria-live="polite"
      data-testid="service-status-banner"
      className="border-b border-amber-300 bg-amber-50 text-amber-900 text-xs sm:text-sm font-medium py-2.5 px-4 sticky top-16 z-20 backdrop-blur"
    >
      <div className="max-w-7xl mx-auto flex flex-col gap-1.5">
        {notices.map((notice) => (
          <div
            key={notice.id}
            data-testid={`banner-notice-${notice.id}`}
            className="flex items-center gap-2"
          >
            <span className="shrink-0 font-bold">
              {notice.type === 'warning' ? '⚠️' : '❄️'}
            </span>
            <span>{notice.message}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
