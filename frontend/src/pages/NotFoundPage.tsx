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
        {/* Glow ambient background effects */}
        <div className="absolute -top-16 left-1/2 -translate-x-1/2 w-96 h-96 bg-cyan-500/10 rounded-full blur-3xl pointer-events-none" />
        <div className="absolute -bottom-16 left-1/2 -translate-x-1/2 w-80 h-80 bg-indigo-500/10 rounded-full blur-3xl pointer-events-none" />

        {/* 404 Glitch Badge */}
        <div className="relative inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-slate-900 border border-slate-700/80 text-xs font-mono text-cyan-400 shadow-xl">
          <span className="w-2 h-2 rounded-full bg-rose-500 animate-ping" />
          <span>ERR_COMMIT_NOT_FOUND • 404</span>
        </div>

        {/* Massive 404 Title */}
        <div className="space-y-2">
          <h1 className="text-7xl sm:text-8xl lg:text-9xl font-black text-transparent bg-clip-text bg-gradient-to-b from-white via-slate-200 to-slate-500 tracking-tight font-mono select-none">
            404
          </h1>
          <h2 className="text-2xl sm:text-3xl font-bold text-white tracking-tight">
            Lost in the Commit Tree
          </h2>
          <p className="text-slate-400 text-sm sm:text-base max-w-md mx-auto leading-relaxed">
            The branch, pull request, or page you were navigating to does not exist,
            has been merged, or was relocated.
          </p>
        </div>

        {/* Terminal Box */}
        <div className="bg-slate-950/80 border border-slate-800 rounded-2xl p-4 max-w-md mx-auto text-left font-mono text-xs shadow-2xl overflow-x-auto">
          <div className="flex items-center gap-1.5 pb-2.5 mb-2.5 border-b border-slate-800/80 text-slate-500">
            <div className="w-2.5 h-2.5 rounded-full bg-rose-500/60" />
            <div className="w-2.5 h-2.5 rounded-full bg-amber-500/60" />
            <div className="w-2.5 h-2.5 rounded-full bg-emerald-500/60" />
            <span className="ml-2 text-[10px] text-slate-500">bash — commitrush-cli</span>
          </div>
          <p className="text-slate-400">
            <span className="text-cyan-400">$</span> git checkout HEAD~1 --path &quot;{location.pathname}&quot;
          </p>
          <p className="text-rose-400/90 pt-1">
            fatal: pathspec &apos;{location.pathname}&apos; did not match any file(s) known to git
          </p>
        </div>

        {/* Action Buttons */}
        <div className="flex flex-wrap items-center justify-center gap-3 pt-2">
          {user?.is_authenticated ? (
            <Link
              to="/profile"
              className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-bold text-xs transition-all shadow-lg shadow-cyan-500/20 hover:scale-105 active:scale-95"
              data-testid="not-found-home-btn"
            >
              <span>👤</span>
              <span>Back to My Profile</span>
            </Link>
          ) : (
            <Link
              to="/"
              className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-bold text-xs transition-all shadow-lg shadow-cyan-500/20 hover:scale-105 active:scale-95"
              data-testid="not-found-home-btn"
            >
              <span>🏠</span>
              <span>Back to Landing Page</span>
            </Link>
          )}

          <Link
            to="/issues"
            className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-slate-900 hover:bg-slate-800 text-slate-200 hover:text-white font-semibold text-xs border border-slate-700/80 transition-colors shadow-sm"
            data-testid="not-found-issues-btn"
          >
            <span>🎯</span>
            <span>Explore Issues</span>
          </Link>

          <Link
            to="/projects"
            className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-slate-900 hover:bg-slate-800 text-slate-200 hover:text-white font-semibold text-xs border border-slate-700/80 transition-colors shadow-sm"
            data-testid="not-found-projects-btn"
          >
            <span>📁</span>
            <span>Browse Projects</span>
          </Link>

          <Link
            to="/leaderboard"
            className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-slate-900 hover:bg-slate-800 text-slate-200 hover:text-white font-semibold text-xs border border-slate-700/80 transition-colors shadow-sm"
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
