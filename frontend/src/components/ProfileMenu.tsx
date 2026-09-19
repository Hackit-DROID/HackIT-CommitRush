import { useState, useRef, useEffect } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { CurrentUser } from '../types/api';
import { useLogout } from '../api/auth';

interface ProfileMenuProps {
  user: CurrentUser;
}

export function ProfileMenu({ user }: ProfileMenuProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [imageError, setImageError] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);
  const location = useLocation();
  const { mutate: logout, isPending: isLoggingOut } = useLogout();

  // Close menu on route changes
  useEffect(() => {
    setIsOpen(false);
  }, [location.pathname, location.search]);

  // Handle outside clicks and keyboard escape
  useEffect(() => {
    if (!isOpen) return;

    function handleClickOutside(event: MouseEvent | TouchEvent) {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') {
        setIsOpen(false);
        buttonRef.current?.focus();
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
  }, [isOpen]);

  const fallbackInitial = user.github_username
    ? user.github_username.charAt(0).toUpperCase()
    : 'U';

  return (
    <div className="relative inline-block text-left" ref={menuRef}>
      {/* Profile Avatar Button */}
      <button
        ref={buttonRef}
        type="button"
        onClick={() => setIsOpen((prev) => !prev)}
        aria-expanded={isOpen}
        aria-haspopup="true"
        aria-label={`${user.github_username}'s profile menu`}
        className="flex items-center gap-2 p-0.5 rounded-full border-2 border-slate-700/80 hover:border-cyan-500 focus:outline-none focus:ring-2 focus:ring-cyan-500 focus:ring-offset-2 focus:ring-offset-slate-950 transition-all cursor-pointer group shadow-md"
        data-testid="profile-avatar-button"
      >
        <div className="w-8 h-8 sm:w-9 sm:h-9 rounded-full overflow-hidden bg-slate-800 flex items-center justify-center shrink-0">
          {user.avatar_url && !imageError ? (
            <img
              src={user.avatar_url}
              alt={`${user.github_username}'s profile avatar`}
              width="36"
              height="36"
              decoding="async"
              onError={() => setImageError(true)}
              className="w-full h-full object-cover rounded-full group-hover:scale-105 transition-transform"
              data-testid="profile-avatar-img"
            />
          ) : (
            <div
              className={`w-full h-full rounded-full flex items-center justify-center font-bold text-white text-xs sm:text-sm ${
                user.is_staff ? 'bg-amber-600' : 'bg-gradient-to-tr from-cyan-600 to-indigo-600'
              }`}
              data-testid="profile-avatar-fallback"
            >
              {fallbackInitial}
            </div>
          )}
        </div>
      </button>

      {/* Dropdown Menu */}
      {isOpen && (
        <div
          role="menu"
          aria-orientation="vertical"
          aria-labelledby="user-menu-button"
          tabIndex={-1}
          className="absolute right-0 mt-2 w-64 bg-slate-900 border border-slate-800 rounded-2xl shadow-2xl shadow-slate-950/90 z-50 p-2 divide-y divide-slate-800/80 focus:outline-none animate-in fade-in zoom-in-95 duration-100"
          data-testid="profile-dropdown-menu"
        >
          {/* Menu Header Identity Section */}
          <div className="p-3 space-y-1">
            <div className="flex items-center gap-2.5">
              <div className="w-8 h-8 rounded-full overflow-hidden bg-slate-800 shrink-0 border border-slate-700">
                {user.avatar_url && !imageError ? (
                  <img
                    src={user.avatar_url}
                    alt={user.github_username}
                    width="32"
                    height="32"
                    loading="lazy"
                    decoding="async"
                    className="w-full h-full object-cover"
                  />
                ) : (
                  <div className="w-full h-full flex items-center justify-center font-bold text-xs text-white bg-cyan-600">
                    {fallbackInitial}
                  </div>
                )}
              </div>
              <div className="min-w-0 flex-1">
                <p className="text-sm font-bold text-white truncate" data-testid="menu-username">
                  @{user.github_username}
                </p>
                <p className="text-[11px] text-cyan-400 font-mono font-medium">
                  {user.total_points} pts
                </p>
              </div>
            </div>
          </div>

          {/* Action Links */}
          <div className="py-1.5 space-y-0.5">
            {/* My Profile */}
            <Link
              to="/profile"
              onClick={() => setIsOpen(false)}
              role="menuitem"
              className="flex items-center gap-2.5 w-full px-3 py-2 rounded-xl text-xs font-semibold text-slate-200 hover:text-white hover:bg-slate-800/80 transition-colors group"
              data-testid="menu-item-my-profile"
            >
              <span className="text-sm text-slate-400 group-hover:text-cyan-400">👤</span>
              <span>My Profile</span>
            </Link>

            {/* GitHub Profile External Link */}
            <a
              href={`https://github.com/${user.github_username}`}
              target="_blank"
              rel="noopener noreferrer"
              onClick={() => setIsOpen(false)}
              role="menuitem"
              className="flex items-center justify-between w-full px-3 py-2 rounded-xl text-xs font-semibold text-slate-200 hover:text-white hover:bg-slate-800/80 transition-colors group"
              data-testid="menu-item-github-profile"
            >
              <div className="flex items-center gap-2.5">
                <svg className="w-3.5 h-3.5 fill-current text-slate-400 group-hover:text-white" viewBox="0 0 24 24">
                  <path fillRule="evenodd" clipRule="evenodd" d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.53 1.032 1.53 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z" />
                </svg>
                <span>GitHub Profile</span>
              </div>
              <span className="text-[10px] text-slate-500 group-hover:text-slate-400">↗</span>
            </a>
          </div>

          {/* Account Switcher for Development Testing */}
          <div className="p-2">
            <label htmlFor="dev-account-switch" className="text-[10px] uppercase font-mono text-slate-500 block mb-1">
              Switch Account (Dev)
            </label>
            <select
              id="dev-account-switch"
              value={user.github_username}
              onChange={(e) => {
                window.location.href = `/api/v1/auth/dev-login/?username=${e.target.value}&next=${window.location.pathname}`;
              }}
              className="w-full bg-slate-950 border border-slate-800 text-slate-300 text-[11px] rounded-lg p-1.5 focus:outline-none focus:ring-1 focus:ring-cyan-500 cursor-pointer"
            >
              <option value="sarah_dev">sarah_dev (Rank #1)</option>
              <option value="alex_builder">alex_builder (Rank #2)</option>
              <option value="elena_rust">elena_rust (Rank #3)</option>
              <option value="admin">admin (Staff / Admin)</option>
            </select>
          </div>

          {/* Logout Action */}
          <div className="pt-1.5">
            <button
              type="button"
              role="menuitem"
              disabled={isLoggingOut}
              onClick={() => {
                setIsOpen(false);
                logout();
              }}
              className="flex items-center gap-2.5 w-full px-3 py-2 rounded-xl text-xs font-semibold text-rose-400 hover:text-rose-300 hover:bg-rose-950/40 transition-colors cursor-pointer disabled:opacity-50"
              data-testid="menu-item-logout"
            >
              <span>🚪</span>
              <span>{isLoggingOut ? 'Signing out...' : 'Sign Out'}</span>
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
