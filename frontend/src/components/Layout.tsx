import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import { ServiceStatusBanner } from './ServiceStatusBanner';

interface LayoutProps {
  children: React.ReactNode;
}

export function Layout({ children }: LayoutProps) {
  const location = useLocation();

  const isIssuesActive =
    location.pathname === '/' ||
    location.pathname.startsWith('/issues');

  const isProjectsActive = location.pathname.startsWith('/projects');
  const isLeaderboardActive = location.pathname.startsWith('/leaderboard');
  const isDashboardActive = location.pathname.startsWith('/dashboard');
  const isContributionsActive = location.pathname.startsWith('/contributions');
  const isStatsActive = location.pathname.startsWith('/stats');

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans selection:bg-cyan-500 selection:text-white">
      {/* Top Navigation Bar */}
      <header className="border-b border-slate-800 bg-slate-900/80 backdrop-blur sticky top-0 z-30">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <div className="flex items-center space-x-6 sm:space-x-8">
            <Link
              to="/issues"
              className="flex items-center space-x-2.5 group focus:outline-none focus:ring-2 focus:ring-cyan-500 rounded-md px-1 py-0.5"
            >
              <div className="w-8 h-8 rounded-lg bg-gradient-to-tr from-cyan-600 to-indigo-600 flex items-center justify-center font-black text-white shadow-md shadow-cyan-500/20 group-hover:scale-105 transition-transform">
                CR
              </div>
              <span className="font-bold text-lg tracking-tight text-white group-hover:text-cyan-400 transition-colors">
                CommitRush
              </span>
            </Link>

            <nav className="flex space-x-1 sm:space-x-1.5 flex-wrap">
              <Link
                to="/issues"
                className={`px-2.5 py-1.5 rounded-lg text-xs sm:text-sm font-medium transition-colors ${
                  isIssuesActive
                    ? 'bg-slate-800 text-cyan-400 border border-slate-700/60 shadow-sm'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
                }`}
              >
                Issues
              </Link>
              <Link
                to="/projects"
                className={`px-2.5 py-1.5 rounded-lg text-xs sm:text-sm font-medium transition-colors ${
                  isProjectsActive
                    ? 'bg-slate-800 text-cyan-400 border border-slate-700/60 shadow-sm'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
                }`}
              >
                Projects
              </Link>
              <Link
                to="/leaderboard"
                className={`px-2.5 py-1.5 rounded-lg text-xs sm:text-sm font-medium transition-colors ${
                  isLeaderboardActive
                    ? 'bg-slate-800 text-cyan-400 border border-slate-700/60 shadow-sm'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
                }`}
              >
                Leaderboard
              </Link>
              <Link
                to="/dashboard"
                className={`px-2.5 py-1.5 rounded-lg text-xs sm:text-sm font-medium transition-colors ${
                  isDashboardActive
                    ? 'bg-slate-800 text-cyan-400 border border-slate-700/60 shadow-sm'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
                }`}
              >
                Dashboard
              </Link>
              <Link
                to="/contributions"
                className={`px-2.5 py-1.5 rounded-lg text-xs sm:text-sm font-medium transition-colors ${
                  isContributionsActive
                    ? 'bg-slate-800 text-cyan-400 border border-slate-700/60 shadow-sm'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
                }`}
              >
                My Activity
              </Link>
              <Link
                to="/stats"
                className={`px-2.5 py-1.5 rounded-lg text-xs sm:text-sm font-medium transition-colors ${
                  isStatsActive
                    ? 'bg-slate-800 text-cyan-400 border border-slate-700/60 shadow-sm'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
                }`}
              >
                Stats
              </Link>
            </nav>
          </div>

          <div className="flex items-center space-x-3 text-xs text-slate-400">
            <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-emerald-950/60 border border-emerald-800/50 text-emerald-400 font-mono">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
              Live Sync
            </span>
          </div>
        </div>
      </header>

      {/* Global Degraded-Mode Service Status Banner (PRD §17, Plan M7-T7) */}
      <ServiceStatusBanner />

      {/* Main Content Area */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {children}
      </main>

      {/* Footer */}
      <footer className="border-t border-slate-800/60 bg-slate-900/40 py-6 text-center text-xs text-slate-500">
        <div className="max-w-7xl mx-auto px-4">
          CommitRush — High Speed Open Source Contribution Sprint. All data synced locally from PostgreSQL.
        </div>
      </footer>
    </div>
  );
}
