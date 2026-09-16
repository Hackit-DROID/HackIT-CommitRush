interface EmptyStateProps {
  title?: string;
  message?: string;
  actionLabel?: string;
  onAction?: () => void;
}

export function EmptyState({
  title = 'No items found',
  message = 'Try adjusting your search or filters to find what you are looking for.',
  actionLabel,
  onAction,
}: EmptyStateProps) {
  return (
    <div
      className="bg-slate-900/40 border border-slate-800/80 rounded-2xl p-10 text-center max-w-lg mx-auto my-8"
      data-testid="empty-state"
    >
      <div className="w-12 h-12 rounded-full bg-slate-800/80 border border-slate-700/60 flex items-center justify-center mx-auto mb-4 text-slate-400">
        <svg
          className="w-6 h-6"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={1.5}
            d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
          />
        </svg>
      </div>
      <h3 className="text-lg font-semibold text-white mb-1.5">{title}</h3>
      <p className="text-sm text-slate-400 mb-6">{message}</p>
      {actionLabel && onAction && (
        <button
          onClick={onAction}
          type="button"
          className="inline-flex items-center px-4 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-sm font-medium text-cyan-400 border border-slate-700 transition-colors shadow-sm focus:outline-none focus:ring-2 focus:ring-cyan-500"
        >
          {actionLabel}
        </button>
      )}
    </div>
  );
}
