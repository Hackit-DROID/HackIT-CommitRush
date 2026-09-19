import type { ReactNode } from 'react';
import { Navigate, useLocation, Link } from 'react-router-dom';
import { useCurrentUser } from '../api/auth';
import { DashboardSkeleton } from './Skeletons';

interface ProtectedRouteProps {
  children: ReactNode;
  requireStaff?: boolean;
  redirectTo?: string;
}

export function ProtectedRoute({
  children,
  requireStaff = false,
  redirectTo,
}: ProtectedRouteProps) {
  const location = useLocation();
  const { data: user, isLoading } = useCurrentUser();

  // 1. Loading State - prevent flash of unauthenticated content (FOUC)
  if (isLoading) {
    return (
      <div className="space-y-6" data-testid="auth-loading">
        <div className="flex items-center gap-3 py-4">
          <div className="w-5 h-5 rounded-full border-2 border-cyan-500 border-t-transparent animate-spin" />
          <span className="text-sm text-slate-400 font-mono">Authenticating session...</span>
        </div>
        <DashboardSkeleton />
      </div>
    );
  }

  // 2. Unauthenticated check
  if (!user?.is_authenticated) {
    const destination = redirectTo || `/?login_required=1&next=${encodeURIComponent(location.pathname)}`;
    return <Navigate to={destination} replace />;
  }

  // 3. Staff permission check
  if (requireStaff && !user.is_staff) {
    return (
      <div
        className="max-w-xl mx-auto my-12 bg-slate-900/90 border border-red-500/30 rounded-2xl p-8 text-center space-y-5 shadow-2xl"
        data-testid="unauthorized-state"
      >
        <div className="w-16 h-16 mx-auto rounded-full bg-red-950/60 border border-red-500/40 flex items-center justify-center text-2xl text-red-400">
          🛡️
        </div>
        <div className="space-y-2">
          <h2 className="text-2xl font-bold text-white tracking-tight">Staff Access Required</h2>
          <p className="text-slate-400 text-sm leading-relaxed">
            This page requires administrator privileges. Your current account{' '}
            <span className="text-slate-200 font-mono font-semibold">@{user.github_username}</span> is not registered as staff.
          </p>
        </div>
        <div className="pt-2 flex flex-col sm:flex-row items-center justify-center gap-3">
          <Link
            to="/profile"
            className="w-full sm:w-auto px-5 py-2.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 font-medium text-sm transition-colors"
          >
            ← Return to Profile
          </Link>
          <a
            href={`/api/v1/auth/dev-login/?username=admin&next=${encodeURIComponent(location.pathname)}`}
            className="w-full sm:w-auto px-5 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-medium text-sm transition-colors shadow-lg shadow-indigo-600/20"
          >
            Switch to Admin
          </a>
        </div>
      </div>
    );
  }

  // 4. Authorized
  return <>{children}</>;
}
