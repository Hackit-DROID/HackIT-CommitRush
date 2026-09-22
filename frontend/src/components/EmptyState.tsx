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
      className="bg-[#ffffff] border border-[#d8d8d3] rounded-[6px] p-10 text-center max-w-lg mx-auto my-8 shadow-sm"
      data-testid="empty-state"
    >
      <div className="w-12 h-12 rounded-full bg-[#f4f4f1] border border-[#d8d8d3] flex items-center justify-center mx-auto mb-4 text-[#555555]">
        <svg
          className="w-5 h-5"
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
      <h3 className="text-lg font-bold text-[#111111] mb-1.5">{title}</h3>
      <p className="text-sm text-[#555555] mb-6 leading-relaxed">{message}</p>
      {actionLabel && onAction && (
        <button
          onClick={onAction}
          type="button"
          className="inline-flex items-center px-5 py-2.5 rounded-[4px] bg-[#050505] hover:bg-[#222222] text-sm font-medium text-white transition-colors shadow-none focus:outline-none focus-visible:ring-2 focus-visible:ring-[#ff5a1f]"
        >
          {actionLabel}
        </button>
      )}
    </div>
  );
}
