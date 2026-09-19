import { useState, useRef, useEffect, type ReactNode } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { ServiceStatusBanner } from './ServiceStatusBanner';
import { useCurrentUser, useLogout } from '../api/auth';
import { ProfileMenu } from './ProfileMenu';

interface LayoutProps {
  children: ReactNode;
}

export function Layout({ children }: LayoutProps) {
  const location = useLocation();
  const { data: user, isLoading } = useCurrentUser();
  const { mutate: logout, isPending: isLoggingOut } = useLogout();
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const mobileMenuRef = useRef<HTMLDivElement>(null);
  const menuTriggerRef = useRef<HTMLButtonElement>(null);

  const isIssuesActive = location.pathname.startsWith('/issues');
  const isProjectsActive = location.pathname.startsWith('/projects');
  const isLeaderboardActive = location.pathname.startsWith('/leaderboard');
  const isProfileActive = location.pathname === '/profile' || location.pathname.startsWith('/profile');

  // Close mobile menu on route change
  useEffect(() => {
    setIsMobileMenuOpen(false);
  }, [location.pathname, location.search]);

  // Handle outside click to close mobile navigation
  useEffect(() => {
    if (!isMobileMenuOpen) return;

    function handleClickOutside(event: MouseEvent | TouchEvent) {
      const target = event.target as Node;
      if (
        mobileMenuRef.current &&
        !mobileMenuRef.current.contains(target) &&
        menuTriggerRef.current &&
        !menuTriggerRef.current.contains(target)
      ) {
        setIsMobileMenuOpen(false);
      }
    }

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') {
        setIsMobileMenuOpen(false);
        menuTriggerRef.current?.focus();
      }
    }

    document.addEventListener('mousedown', handleClickOutside);
    document.addEventListener('touchstart', handleClickOutside);
    document.addEventListener('keydown', handleKeyDown);

    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
      document.removeEventListener('touchstart', handleClickOutside);
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [isMobileMenuOpen]);

  const currentYear = new Date().getFullYear();

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans selection:bg-cyan-500 selection:text-white">
      {/* Top Navigation Bar */}
      <header className="border-b border-slate-800 bg-slate-900/90 backdrop-blur sticky top-0 z-30">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <div className="flex items-center space-x-4 sm:space-x-8">
            {/* Mobile Hamburger Menu Trigger */}
            <button
              ref={menuTriggerRef}
              type="button"
              onClick={() => setIsMobileMenuOpen((prev) => !prev)}
              aria-label={isMobileMenuOpen ? 'Close navigation menu' : 'Open navigation menu'}
              aria-expanded={isMobileMenuOpen}
              aria-controls="mobile-navigation"
              data-testid="mobile-menu-trigger"
              className="md:hidden min-w-[44px] min-h-[44px] flex items-center justify-center rounded-xl text-slate-400 hover:text-white hover:bg-slate-800 focus:outline-none focus:ring-2 focus:ring-cyan-500 transition-colors cursor-pointer -ml-2"
            >
              {isMobileMenuOpen ? (
                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              ) : (
                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
                </svg>
              )}
            </button>

            {/* Clickable Brand Logo */}
            <Link
              to={user?.is_authenticated ? '/profile' : '/'}
              aria-label="CommitRush home"
              className="flex items-center space-x-2.5 group focus:outline-none focus:ring-2 focus:ring-cyan-500 rounded-md px-1 py-0.5"
            >
              <div className="w-8 h-8 rounded-lg bg-gradient-to-tr from-cyan-600 to-indigo-600 flex items-center justify-center font-black text-white shadow-md shadow-cyan-500/20 group-hover:scale-105 transition-transform shrink-0">
                CR
              </div>
              <span className="font-bold text-lg tracking-tight text-white group-hover:text-cyan-400 transition-colors">
                CommitRush
              </span>
            </Link>

            {/* Desktop Navigation Links */}
            <nav className="hidden md:flex space-x-1.5" aria-label="Desktop Navigation">
              <Link
                to="/issues"
                className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                  isIssuesActive
                    ? 'bg-slate-800 text-cyan-400 border border-slate-700/60 shadow-sm'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
                }`}
              >
                Issues
              </Link>
              <Link
                to="/projects"
                className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                  isProjectsActive
                    ? 'bg-slate-800 text-cyan-400 border border-slate-700/60 shadow-sm'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
                }`}
              >
                Projects
              </Link>
              <Link
                to="/leaderboard"
                className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                  isLeaderboardActive
                    ? 'bg-slate-800 text-cyan-400 border border-slate-700/60 shadow-sm'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
                }`}
              >
                Leaderboard
              </Link>

              {user?.is_authenticated && (
                <Link
                  to="/profile"
                  className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                    isProfileActive
                      ? 'bg-slate-800 text-cyan-400 border border-slate-700/60 shadow-sm'
                      : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
                  }`}
                  data-testid="nav-my-profile"
                >
                  My Profile
                </Link>
              )}
            </nav>
          </div>

          {/* Right Header Controls */}
          <div className="flex items-center space-x-2 sm:space-x-3 text-xs">
            {isLoading ? (
              <div
                className="w-8 h-8 sm:w-9 sm:h-9 rounded-full bg-slate-800 animate-pulse border border-slate-700/60"
                data-testid="avatar-loading-skeleton"
              />
            ) : user?.is_authenticated ? (
              <ProfileMenu user={user} />
            ) : (
              <div className="flex items-center space-x-2">
                <a
                  href={`/api/v1/auth/github/login/?next=${encodeURIComponent(location.pathname === '/' ? '/profile' : location.pathname)}`}
                  className="inline-flex items-center gap-1.5 px-3 py-2 rounded-xl bg-white hover:bg-slate-100 text-slate-950 font-bold shadow-sm transition-all text-xs"
                >
                  <svg className="w-3.5 h-3.5 fill-current shrink-0" viewBox="0 0 24 24">
                    <path fillRule="evenodd" clipRule="evenodd" d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.53 1.032 1.53 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z" />
                  </svg>
                  <span className="hidden xs:inline sm:inline">Sign in with GitHub</span>
                  <span className="xs:hidden sm:hidden">Sign in</span>
                </a>
              </div>
            )}

            <span className="hidden lg:inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-emerald-950/60 border border-emerald-800/50 text-emerald-400 font-mono">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
              Live Sync
            </span>
          </div>
        </div>

        {/* Mobile Navigation Drawer */}
        {isMobileMenuOpen && (
          <div
            id="mobile-navigation"
            ref={mobileMenuRef}
            data-testid="mobile-navigation-menu"
            className="md:hidden border-b border-slate-800 bg-slate-900/98 backdrop-blur-xl px-4 pt-3 pb-5 space-y-3 shadow-2xl animate-in fade-in slide-in-from-top-2 duration-150"
          >
            <nav className="flex flex-col space-y-1" aria-label="Mobile Navigation Links">
              <Link
                to="/issues"
                onClick={() => setIsMobileMenuOpen(false)}
                className={`flex items-center justify-between px-4 py-3 rounded-xl text-sm font-semibold transition-colors min-h-[44px] ${
                  isIssuesActive
                    ? 'bg-slate-800 text-cyan-400 border border-slate-700/80'
                    : 'text-slate-300 hover:text-white hover:bg-slate-800/60'
                }`}
                data-testid="mobile-nav-issues"
              >
                <span>Issues</span>
                <span className="text-slate-500 font-mono text-xs">→</span>
              </Link>

              <Link
                to="/projects"
                onClick={() => setIsMobileMenuOpen(false)}
                className={`flex items-center justify-between px-4 py-3 rounded-xl text-sm font-semibold transition-colors min-h-[44px] ${
                  isProjectsActive
                    ? 'bg-slate-800 text-cyan-400 border border-slate-700/80'
                    : 'text-slate-300 hover:text-white hover:bg-slate-800/60'
                }`}
                data-testid="mobile-nav-projects"
              >
                <span>Projects</span>
                <span className="text-slate-500 font-mono text-xs">→</span>
              </Link>

              <Link
                to="/leaderboard"
                onClick={() => setIsMobileMenuOpen(false)}
                className={`flex items-center justify-between px-4 py-3 rounded-xl text-sm font-semibold transition-colors min-h-[44px] ${
                  isLeaderboardActive
                    ? 'bg-slate-800 text-cyan-400 border border-slate-700/80'
                    : 'text-slate-300 hover:text-white hover:bg-slate-800/60'
                }`}
                data-testid="mobile-nav-leaderboard"
              >
                <span>Leaderboard</span>
                <span className="text-slate-500 font-mono text-xs">→</span>
              </Link>

              {user?.is_authenticated && (
                <Link
                  to="/profile"
                  onClick={() => setIsMobileMenuOpen(false)}
                  className={`flex items-center justify-between px-4 py-3 rounded-xl text-sm font-semibold transition-colors min-h-[44px] ${
                    isProfileActive
                      ? 'bg-slate-800 text-cyan-400 border border-slate-700/80'
                      : 'text-slate-300 hover:text-white hover:bg-slate-800/60'
                  }`}
                  data-testid="mobile-nav-profile"
                >
                  <span className="flex items-center gap-2">
                    <span>👤</span>
                    <span>My Profile</span>
                  </span>
                  <span className="text-cyan-400 font-mono text-xs font-bold">{user.total_points} pts</span>
                </Link>
              )}
            </nav>

            {/* Mobile Auth Actions */}
            <div className="pt-2 border-t border-slate-800/80">
              {user?.is_authenticated ? (
                <div className="flex items-center justify-between px-2 py-1">
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-slate-400">Signed in as</span>
                    <span className="text-xs font-bold text-white font-mono">@{user.github_username}</span>
                  </div>
                  <button
                    type="button"
                    disabled={isLoggingOut}
                    onClick={() => {
                      setIsMobileMenuOpen(false);
                      logout();
                    }}
                    className="px-3 py-2 rounded-lg text-xs font-semibold text-rose-400 hover:bg-rose-950/40 transition-colors min-h-[44px] flex items-center"
                    data-testid="mobile-nav-logout"
                  >
                    {isLoggingOut ? 'Signing out...' : 'Sign Out'}
                  </button>
                </div>
              ) : (
                <a
                  href={`/api/v1/auth/github/login/?next=${encodeURIComponent(location.pathname === '/' ? '/profile' : location.pathname)}`}
                  className="w-full flex items-center justify-center gap-2 px-4 py-3 rounded-xl bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-bold text-sm shadow-md transition-colors min-h-[44px]"
                  data-testid="mobile-nav-login"
                >
                  <svg className="w-4 h-4 fill-current shrink-0" viewBox="0 0 24 24">
                    <path fillRule="evenodd" clipRule="evenodd" d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.53 1.032 1.53 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z" />
                  </svg>
                  <span>Sign in with GitHub</span>
                </a>
              )}
            </div>
          </div>
        )}
      </header>

      {/* Global Degraded-Mode Service Status Banner (PRD §17, Plan M7-T7) */}
      <ServiceStatusBanner />

      {/* Main Content Area */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {children}
      </main>

      {/* Footer */}
      <footer className="border-t border-slate-800/80 bg-slate-900/60 py-8 text-xs text-slate-400">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 space-y-6">
          <div className="flex flex-col md:flex-row items-center justify-between gap-4">
            <div className="flex items-center space-x-2.5">
              <div className="w-6 h-6 rounded-md bg-gradient-to-tr from-cyan-600 to-indigo-600 flex items-center justify-center font-bold text-white text-[11px] shrink-0">
                CR
              </div>
              <span className="font-bold text-slate-200">CommitRush</span>
              <span className="text-slate-600">•</span>
              <span className="text-slate-500">Open-Source Contribution Drive</span>
            </div>

            <nav className="flex flex-wrap items-center justify-center gap-x-6 gap-y-2 text-slate-400" aria-label="Footer Navigation">
              <Link to="/issues" className="hover:text-cyan-400 transition-colors">
                Issues
              </Link>
              <Link to="/projects" className="hover:text-cyan-400 transition-colors">
                Projects
              </Link>
              <Link to="/leaderboard" className="hover:text-cyan-400 transition-colors">
                Leaderboard
              </Link>
              {user?.is_authenticated ? (
                <Link to="/profile" className="hover:text-cyan-400 transition-colors">
                  My Profile
                </Link>
              ) : (
                <a
                  href={`/api/v1/auth/github/login/?next=${encodeURIComponent(location.pathname === '/' ? '/profile' : location.pathname)}`}
                  className="hover:text-cyan-400 transition-colors"
                >
                  Sign In
                </a>
              )}
              <a
                href="https://github.com/Hackit-DROID/Open-Source-Contribution-Drive"
                target="_blank"
                rel="noopener noreferrer"
                className="hover:text-cyan-400 transition-colors inline-flex items-center gap-1"
                aria-label="Official HackIT repository on GitHub (opens in a new tab)"
              >
                <span>Source Repo</span>
                <span className="text-slate-500">↗</span>
              </a>
              <a
                href="/health/"
                className="hover:text-cyan-400 transition-colors inline-flex items-center gap-1 font-mono text-[11px]"
              >
                <span>Health</span>
              </a>
            </nav>
          </div>

          <div className="pt-4 border-t border-slate-800/60 flex flex-col sm:flex-row items-center justify-between gap-2 text-slate-500 text-[11px]">
            <p>© {currentYear} CommitRush. Open-source contribution sprint platform.</p>
            <p>Data synchronized directly from official GitHub repositories.</p>
          </div>
        </div>
      </footer>
    </div>
  );
}
