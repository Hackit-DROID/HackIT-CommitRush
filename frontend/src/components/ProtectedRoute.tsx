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
          <div className="w-5 h-5 rounded-full border-2 border-[#ff5a1f] border-t-transparent animate-spin" />
          <span className="text-sm text-[#555555] font-mono">Authenticating session...</span>
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
        className="max-w-xl mx-auto my-12 bg-white border border-[#d8d8d3] rounded-md p-8 text-center space-y-5 shadow-sm"
        data-testid="unauthorized-state"
      >
        <div className="w-14 h-14 mx-auto rounded-full bg-[#f4f4f1] border border-[#d8d8d3] flex items-center justify-center text-2xl">
          🛡️
        </div>
        <div className="space-y-2">
          <h2 className="text-2xl font-bold text-[#111111] tracking-tight font-display">Staff Access Required</h2>
          <p className="text-[#555555] text-sm leading-relaxed">
            This page requires administrator privileges. Your current account{' '}
            <span className="text-[#111111] font-mono font-semibold">@{user.github_username}</span> is not registered as staff.
          </p>
        </div>
        <div className="pt-2 flex items-center justify-center">
          <Link
            to="/profile"
            className="px-5 py-2.5 rounded-[4px] bg-[#050505] hover:bg-[#222222] text-white font-sans font-medium text-xs transition-colors shadow-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-[#ff5a1f] focus-visible:ring-offset-2"
          >
            ← Return to Profile
          </Link>
        </div>
      </div>
    );
  }

  // 4. Authorized
  return <>{children}</>;
}
