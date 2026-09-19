import { ApiError } from '../types/api';

interface ErrorStateProps {
  error: unknown;
  onRetry?: () => void;
  title?: string;
}

export function ErrorState({ error, onRetry, title }: ErrorStateProps) {
  const isApiError = error instanceof ApiError;
  const isRateLimited = isApiError && error.isRateLimited;
  const isNotFound = isApiError && error.isNotFound;
  const isServerError = isApiError && error.status >= 500;

  const defaultTitle = isRateLimited
    ? 'Rate Limit Exceeded'
    : isNotFound
    ? 'Resource Not Found'
    : isServerError
    ? 'Server Temporarily Unavailable'
    : 'Unable to Load Data';

  let defaultMessage = 'An unexpected error occurred while communicating with the server.';

  if (isRateLimited) {
    defaultMessage = 'You have reached the API rate limit budget (~100 requests/min). Please wait a moment before trying again.';
  } else if (isNotFound) {
    defaultMessage = 'The requested resource could not be found or has been relocated.';
  } else if (isServerError) {
    defaultMessage = 'The CommitRush server encountered a temporary issue. Please try again in a few moments.';
  } else if (error instanceof Error) {
    const msg = error.message.trim();
    // Sanitize technical messages, stack traces, or raw JSON
    if (
      msg.includes('Failed to fetch') ||
      msg.includes('NetworkError') ||
      msg.includes('Load failed')
    ) {
      defaultMessage = 'Unable to connect to the server. Please check your internet connection and try again.';
    } else if (
      msg.startsWith('{') ||
      msg.includes('OperationalError') ||
      msg.includes('Traceback') ||
      msg.includes('Internal Server Error')
    ) {
      defaultMessage = 'The server encountered an error processing your request. Please try again.';
    } else if (msg.length > 0 && msg.length < 200) {
      defaultMessage = msg;
    }
  }

  return (
    <div
      className="bg-slate-900/60 border border-red-900/40 rounded-2xl p-8 text-center max-w-md mx-auto my-8 shadow-lg shadow-red-950/20"
      data-testid="error-state"
    >
      <div
        className={`w-12 h-12 rounded-full flex items-center justify-center mx-auto mb-4 ${
          isRateLimited
            ? 'bg-amber-950/60 border border-amber-800/60 text-amber-400'
            : 'bg-red-950/60 border border-red-800/60 text-red-400'
        }`}
      >
        {isRateLimited ? (
          <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
        ) : (
          <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
          </svg>
        )}
      </div>

      <h3 className="text-lg font-semibold text-white mb-2">{title || defaultTitle}</h3>
      <p className="text-sm text-slate-400 mb-6 leading-relaxed">{defaultMessage}</p>

      {onRetry && (
        <button
          onClick={onRetry}
          type="button"
          className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-sm font-medium text-white border border-slate-700 transition-colors shadow-sm focus:outline-none focus:ring-2 focus:ring-cyan-500"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
          </svg>
          Retry
        </button>
      )}
    </div>
  );
}
