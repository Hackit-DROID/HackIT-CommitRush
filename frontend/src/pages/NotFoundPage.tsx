import { Link, useLocation } from 'react-router-dom';
import { useCurrentUser } from '../api/auth';
import { useDocumentTitle } from '../hooks/useDocumentTitle';

export function NotFoundPage() {
  useDocumentTitle(
    'CommitRush — Page Not Found',
    'The requested branch, pull request, or page does not exist on CommitRush.'
  );

  const location = useLocation();
  const { data: user } = useCurrentUser();

  return (
    <div
      className="min-h-[70vh] flex items-center justify-center py-12 px-4"
      data-testid="not-found-page"
    >
      <div className="relative max-w-2xl w-full text-center space-y-8">
        {/* 404 Status Badge */}
        <div className="relative inline-flex items-center gap-2 px-3.5 py-1 rounded-[4px] bg-[#f4f4f1] border border-[#d8d8d3] text-xs font-mono text-[#ff5a1f]">
          <span className="w-2 h-2 rounded-full bg-[#ff5a1f]" />
          <span>ERR_COMMIT_NOT_FOUND • 404</span>
        </div>

        {/* Massive 404 Title */}
        <div className="space-y-2">
          <h1 className="text-7xl sm:text-8xl lg:text-9xl font-bold text-[#111111] tracking-tight select-none">
            404
          </h1>
          <h2 className="text-2xl sm:text-3xl font-bold text-[#111111] tracking-tight">
            Lost in the Commit Tree
          </h2>
          <p className="text-[#555555] text-sm sm:text-base max-w-md mx-auto leading-relaxed font-sans">
            The branch, pull request, or page you were navigating to does not exist,
            has been merged, or was relocated.
          </p>
        </div>

        {/* Terminal Box */}
        <div className="bg-white border border-[#d8d8d3] rounded-md p-5 max-w-md mx-auto text-left font-mono text-xs shadow-sm overflow-x-auto">
          <div className="flex items-center gap-1.5 pb-3 mb-3 border-b border-[#d8d8d3] text-[#777777]">
            <div className="w-2.5 h-2.5 rounded-full bg-[#d8d8d3]" />
            <div className="w-2.5 h-2.5 rounded-full bg-[#d8d8d3]" />
            <div className="w-2.5 h-2.5 rounded-full bg-[#d8d8d3]" />
            <span className="ml-2 text-[10px] text-[#777777] font-mono">bash — commitrush-cli</span>
          </div>
          <p className="text-[#111111]">
            <span className="text-[#ff5a1f]">$</span> git checkout HEAD~1 --path &quot;{location.pathname}&quot;
          </p>
          <p className="text-[#ff5a1f] pt-1.5">
            fatal: pathspec &apos;{location.pathname}&apos; did not match any file(s) known to git
          </p>
        </div>

        {/* Action Buttons */}
        <div className="flex flex-wrap items-center justify-center gap-3 pt-2">
          {user?.is_authenticated ? (
            <Link
              to="/profile"
              className="inline-flex items-center gap-2 px-6 py-3 rounded-[4px] bg-[#050505] hover:bg-[#222222] text-white font-sans font-semibold text-xs transition-all shadow-sm active:scale-95 cursor-pointer"
              data-testid="not-found-home-btn"
            >
              <span>👤</span>
              <span>Back to My Profile</span>
            </Link>
          ) : (
            <Link
              to="/"
              className="inline-flex items-center gap-2 px-6 py-3 rounded-[4px] bg-[#050505] hover:bg-[#222222] text-white font-sans font-semibold text-xs transition-all shadow-sm active:scale-95 cursor-pointer"
              data-testid="not-found-home-btn"
            >
              <span>🏠</span>
              <span>Back to Landing Page</span>
            </Link>
          )}

          <Link
            to="/issues"
            className="inline-flex items-center gap-2 px-5 py-3 rounded-[4px] bg-white hover:bg-[#f4f4f1] text-[#111111] font-sans font-medium text-xs border border-[#d8d8d3] hover:border-[#111111] transition-colors shadow-sm cursor-pointer"
            data-testid="not-found-issues-btn"
          >
            <span>🎯</span>
            <span>Explore Issues</span>
          </Link>

          <Link
            to="/projects"
            className="inline-flex items-center gap-2 px-5 py-3 rounded-[4px] bg-white hover:bg-[#f4f4f1] text-[#111111] font-sans font-medium text-xs border border-[#d8d8d3] hover:border-[#111111] transition-colors shadow-sm cursor-pointer"
            data-testid="not-found-projects-btn"
          >
            <span>📁</span>
            <span>Browse Projects</span>
          </Link>

          <Link
            to="/leaderboard"
            className="inline-flex items-center gap-2 px-5 py-3 rounded-[4px] bg-white hover:bg-[#f4f4f1] text-[#111111] font-sans font-medium text-xs border border-[#d8d8d3] hover:border-[#111111] transition-colors shadow-sm cursor-pointer"
            data-testid="not-found-leaderboard-btn"
          >
            <span>🏆</span>
            <span>Leaderboard</span>
          </Link>
        </div>
      </div>
    </div>
  );
}
