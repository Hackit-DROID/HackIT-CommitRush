import { useState, useRef, useEffect, type ReactNode } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { ServiceStatusBanner } from './ServiceStatusBanner';
import { useCurrentUser, useLogout, getGitHubLoginUrl } from '../api/auth';
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
    <div className="min-h-screen bg-[#f4f4f1] text-[#111111] flex flex-col font-sans selection:bg-[#ff5a1f] selection:text-white">
      {/* Top Editorial Navigation Bar */}
      <header className="border-b border-[#d8d8d3] bg-[#ffffff]/95 backdrop-blur-md sticky top-0 z-30 transition-all">
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
              className="md:hidden min-w-[44px] min-h-[44px] flex items-center justify-center rounded-[4px] text-[#555555] hover:text-[#111111] hover:bg-[#f4f4f1] focus:outline-none focus-visible:ring-2 focus-visible:ring-[#ff5a1f] transition-colors cursor-pointer -ml-2"
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

            {/* Clickable Editorial Brand Logo */}
            <Link
              to={user?.is_authenticated ? '/profile' : '/'}
              aria-label="CommitRush home"
              className="flex items-center space-x-3 group focus:outline-none focus-visible:ring-2 focus-visible:ring-[#ff5a1f] rounded-[4px] px-1.5 py-1"
            >
              <div className="w-7 h-7 rounded-[4px] bg-[#050505] flex items-center justify-center font-bold text-white text-[11px] tracking-tight group-hover:bg-[#3d5f58] transition-colors shrink-0">
                CR
              </div>
              <div className="flex items-baseline space-x-1.5">
                <span className="font-bold text-lg tracking-tight text-[#111111] group-hover:text-[#3d5f58] transition-colors">
                  COMMIT<span className="text-[#3d5f58]">RUSH</span>
                </span>
                <span className="hidden sm:inline-block text-[10px] font-mono font-medium text-[#777777] uppercase tracking-widest">
                  2026
                </span>
              </div>
            </Link>

            {/* Desktop Navigation Links */}
            <nav className="hidden md:flex space-x-1" aria-label="Desktop Navigation">
              <Link
                to="/issues"
                className={`px-3.5 py-1.5 rounded-[4px] text-sm font-medium transition-colors ${
                  isIssuesActive
                    ? 'bg-[#050505] text-[#ffffff] font-semibold'
                    : 'text-[#555555] hover:text-[#111111] hover:bg-[#f4f4f1]'
                }`}
              >
                Issues
              </Link>
              <Link
                to="/projects"
                className={`px-3.5 py-1.5 rounded-[4px] text-sm font-medium transition-colors ${
                  isProjectsActive
                    ? 'bg-[#050505] text-[#ffffff] font-semibold'
                    : 'text-[#555555] hover:text-[#111111] hover:bg-[#f4f4f1]'
                }`}
              >
                Projects
              </Link>
              <Link
                to="/leaderboard"
                className={`px-3.5 py-1.5 rounded-[4px] text-sm font-medium transition-colors ${
                  isLeaderboardActive
                    ? 'bg-[#050505] text-[#ffffff] font-semibold'
                    : 'text-[#555555] hover:text-[#111111] hover:bg-[#f4f4f1]'
                }`}
              >
                Leaderboard
              </Link>

              {user?.is_authenticated && (
                <Link
                  to="/profile"
                  className={`px-3.5 py-1.5 rounded-[4px] text-sm font-medium transition-colors ${
                    isProfileActive
                      ? 'bg-[#050505] text-[#ffffff] font-semibold'
                      : 'text-[#555555] hover:text-[#111111] hover:bg-[#f4f4f1]'
                  }`}
                  data-testid="nav-my-profile"
                >
                  My Profile
                </Link>
              )}
            </nav>
          </div>

          {/* Right Header Controls */}
          <div className="flex items-center space-x-3 text-xs">
            {isLoading ? (
              <div
                className="w-8 h-8 sm:w-9 sm:h-9 rounded-full bg-[#e8e8e3] animate-pulse border border-[#d8d8d3]"
                data-testid="avatar-loading-skeleton"
              />
            ) : user?.is_authenticated ? (
              <ProfileMenu user={user} />
            ) : (
              <div className="flex items-center space-x-2">
                <a
                  href={getGitHubLoginUrl(location.pathname === '/' ? '/profile' : location.pathname)}
                  className="inline-flex items-center gap-2 px-4 py-2 rounded-[4px] bg-[#050505] hover:bg-[#222222] text-white font-medium shadow-none transition-all text-xs"
                >
                  <svg className="w-3.5 h-3.5 fill-current shrink-0" viewBox="0 0 24 24">
                    <path fillRule="evenodd" clipRule="evenodd" d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.53 1.032 1.53 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z" />
                  </svg>
                  <span className="hidden xs:inline sm:inline">Sign in with GitHub</span>
                  <span className="xs:hidden sm:hidden">Sign in</span>
                </a>
              </div>
            )}

            <span className="hidden lg:inline-flex items-center gap-1.5 px-3 py-1 rounded-[4px] bg-[#f4f4f1] border border-[#d8d8d3] text-[#555555] font-mono text-[11px]">
              <span className="w-1.5 h-1.5 rounded-full bg-[#3d5f58]" />
              22 Sep – 12 Oct
            </span>
          </div>
        </div>

        {/* Mobile Navigation Drawer */}
        {isMobileMenuOpen && (
          <div
            id="mobile-navigation"
            ref={mobileMenuRef}
            data-testid="mobile-navigation-menu"
            className="md:hidden border-b border-[#d8d8d3] bg-[#ffffff] px-4 pt-3 pb-6 space-y-3 shadow-xl animate-in fade-in slide-in-from-top-2 duration-150"
          >
            <nav className="flex flex-col space-y-1.5" aria-label="Mobile Navigation Links">
              <Link
                to="/issues"
                onClick={() => setIsMobileMenuOpen(false)}
                className={`flex items-center justify-between px-4 py-3 rounded-[4px] text-sm font-medium transition-colors min-h-[44px] ${
                  isIssuesActive
                    ? 'bg-[#050505] text-[#ffffff]'
                    : 'text-[#555555] hover:text-[#111111] hover:bg-[#f4f4f1]'
                }`}
                data-testid="mobile-nav-issues"
              >
                <span>Issues</span>
                <span className="font-mono text-xs">→</span>
              </Link>

              <Link
                to="/projects"
                onClick={() => setIsMobileMenuOpen(false)}
                className={`flex items-center justify-between px-4 py-3 rounded-[4px] text-sm font-medium transition-colors min-h-[44px] ${
                  isProjectsActive
                    ? 'bg-[#050505] text-[#ffffff]'
                    : 'text-[#555555] hover:text-[#111111] hover:bg-[#f4f4f1]'
                }`}
                data-testid="mobile-nav-projects"
              >
                <span>Projects</span>
                <span className="font-mono text-xs">→</span>
              </Link>

              <Link
                to="/leaderboard"
                onClick={() => setIsMobileMenuOpen(false)}
                className={`flex items-center justify-between px-4 py-3 rounded-[4px] text-sm font-medium transition-colors min-h-[44px] ${
                  isLeaderboardActive
                    ? 'bg-[#050505] text-[#ffffff]'
                    : 'text-[#555555] hover:text-[#111111] hover:bg-[#f4f4f1]'
                }`}
                data-testid="mobile-nav-leaderboard"
              >
                <span>Leaderboard</span>
                <span className="font-mono text-xs">→</span>
              </Link>

              {user?.is_authenticated && (
                <Link
                  to="/profile"
                  onClick={() => setIsMobileMenuOpen(false)}
                  className={`flex items-center justify-between px-4 py-3 rounded-[4px] text-sm font-medium transition-colors min-h-[44px] ${
                    isProfileActive
                      ? 'bg-[#050505] text-[#ffffff]'
                      : 'text-[#555555] hover:text-[#111111] hover:bg-[#f4f4f1]'
                  }`}
                  data-testid="mobile-nav-profile"
                >
                  <span className="flex items-center gap-2">
                    <span>👤</span>
                    <span>My Profile</span>
                  </span>
                  <span className="text-[#3d5f58] font-mono text-xs font-bold">{user.total_points} pts</span>
                </Link>
              )}
            </nav>

            {/* Mobile Auth Actions */}
            <div className="pt-3 border-t border-[#d8d8d3]">
              {user?.is_authenticated ? (
                <div className="flex items-center justify-between px-2 py-1">
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-[#777777]">Signed in as</span>
                    <span className="text-xs font-bold text-[#111111] font-mono">@{user.github_username}</span>
                  </div>
                  <button
                    type="button"
                    disabled={isLoggingOut}
                    onClick={() => {
                      setIsMobileMenuOpen(false);
                      logout();
                    }}
                    className="px-3 py-2 rounded-[4px] text-xs font-semibold text-[#ff5a1f] hover:bg-[#ff5a1f]/10 transition-colors min-h-[44px] flex items-center"
                    data-testid="mobile-nav-logout"
                  >
                    {isLoggingOut ? 'Signing out...' : 'Sign Out'}
                  </button>
                </div>
              ) : (
                <a
                  href={getGitHubLoginUrl(location.pathname === '/' ? '/profile' : location.pathname)}
                  className="w-full flex items-center justify-center gap-2 px-4 py-3 rounded-[4px] bg-[#050505] hover:bg-[#222222] text-white font-medium text-sm transition-colors min-h-[44px]"
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

      {/* Global Degraded-Mode Service Status Banner */}
      <ServiceStatusBanner />

      {/* Main Content Area */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-10">
        {children}
      </main>

      {/* Editorial Footer */}
      <footer className="border-t border-[#d8d8d3] bg-[#ffffff] py-12 text-sm sm:text-base text-[#555555]">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 space-y-8">
          <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-6">
            <div className="space-y-2">
              <div className="flex items-center space-x-2.5">
                <div className="w-6 h-6 rounded-[3px] bg-[#050505] flex items-center justify-center font-bold text-white text-xs shrink-0">
                  CR
                </div>
                <span className="font-bold text-base sm:text-lg tracking-tight text-[#111111]">
                  COMMIT<span className="text-[#3d5f58]">RUSH</span>
                </span>
                <span className="text-[#d8d8d3]">•</span>
                <span className="text-[#555555] text-sm sm:text-base">21-Day Open-Source Contribution Sprint</span>
              </div>
              <p className="text-[#777777] text-sm">
                Organized by <strong className="text-[#111111] font-semibold">HACKIT</strong> — SGGSIE&T, Nanded. 22 Sep → 12 Oct 2026.
              </p>
            </div>

            <nav className="flex flex-wrap items-center gap-x-6 gap-y-3 text-sm sm:text-base font-medium text-[#555555]" aria-label="Footer Navigation">
              {/* Official HackIT GitHub with Logo */}
              <a
                href="https://github.com/Hackit-DROID"
                target="_blank"
                rel="noopener noreferrer"
                className="hover:text-[#111111] transition-colors inline-flex items-center gap-2"
                aria-label="Official HackIT GitHub organization"
              >
                <img
                  src="/hackit-logo.png"
                  alt="HackIT"
                  className="w-5 h-5 sm:w-6 sm:h-6 rounded-full object-cover shrink-0 border border-[#d8d8d3]"
                />
                <span>HackIT GitHub</span>
              </a>

              {/* Source Repo */}
              <a
                href="https://github.com/Hackit-DROID/Open-Source-Contribution-Drive"
                target="_blank"
                rel="noopener noreferrer"
                className="hover:text-[#111111] transition-colors inline-flex items-center gap-2"
                aria-label="Official HackIT repository on GitHub (opens in a new tab)"
              >
                <svg className="w-5 h-5 shrink-0 fill-current" viewBox="0 0 24 24">
                  <path fillRule="evenodd" clipRule="evenodd" d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.53 1.032 1.53 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z" />
                </svg>
                <span>Source Repo</span>
              </a>

              {/* HackIT Official Website */}
              <a
                href="https://hackit-sggs.vercel.app/"
                target="_blank"
                rel="noopener noreferrer"
                className="hover:text-[#111111] transition-colors inline-flex items-center gap-2"
                aria-label="Official HackIT Community Website"
              >
                <svg className="w-5 h-5 text-[#555555] shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M12 21a9.004 9.004 0 008.716-6.747M12 21a9.004 9.004 0 01-8.716-6.747M12 21c2.485 0 4.5-4.03 4.5-9S14.485 3 12 3m0 18c-2.485 0-4.5-4.03-4.5-9S9.515 3 12 3m0 0a8.997 8.997 0 017.843 4.582M12 3a8.997 8.997 0 00-7.843 4.582m15.686 0A11.953 11.953 0 0112 10.5c-2.998 0-5.74-1.1-7.843-2.918m15.686 0A8.959 8.959 0 0121 12c0 .778-.099 1.533-.284 2.253m0 0A17.919 17.919 0 0112 16.5c-3.162 0-6.133-.815-8.716-2.247m0 0A9.015 9.015 0 013 12c0-1.605.42-3.113 1.157-4.418" />
                </svg>
                <span>HackIT Website</span>
              </a>

              {/* LinkedIn */}
              <a
                href="https://www.linkedin.com/company/hackit-ethical-hacking-cyber-security-club-sggsie-t-nanded/posts/?feedView=all"
                target="_blank"
                rel="noopener noreferrer"
                className="hover:text-[#111111] transition-colors inline-flex items-center gap-2"
                aria-label="HackIT LinkedIn Page"
              >
                <svg className="w-5 h-5 fill-current text-[#0a66c2] shrink-0" viewBox="0 0 24 24">
                  <path d="M19 3a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h14m-.5 15.5v-5.3a3.26 3.26 0 0 0-3.26-3.26c-.85 0-1.84.52-2.28 1.3v-1.11h-2.79v8.37h2.79v-4.93c0-.77.62-1.4 1.39-1.4a1.4 1.4 0 0 1 1.4 1.4v4.93h2.75M6.46 8.76a1.4 1.4 0 1 0-.01-2.8 1.4 1.4 0 0 0 .01 2.8m1.39 9.74v-8.37H5.07v8.37h2.78z" />
                </svg>
                <span>LinkedIn</span>
              </a>

              {user?.is_authenticated ? (
                <Link to="/profile" className="hover:text-[#111111] transition-colors">
                  My Profile
                </Link>
              ) : (
                <a
                  href={getGitHubLoginUrl(location.pathname === '/' ? '/profile' : location.pathname)}
                  className="hover:text-[#111111] transition-colors"
                >
                  Sign In
                </a>
              )}
            </nav>
          </div>

          <div className="pt-6 border-t border-[#e8e8e3] flex flex-col sm:flex-row items-center justify-between gap-3 text-[#777777] text-xs sm:text-sm">
            <p>© {currentYear} CommitRush. Open-source contribution sprint platform.</p>
            <p className="italic text-[#555555]">Build a more open tomorrow.</p>
          </div>
        </div>
      </footer>
    </div>
  );
}
