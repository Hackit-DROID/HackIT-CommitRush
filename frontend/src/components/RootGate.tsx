import { Navigate } from 'react-router-dom';
import { useCurrentUser } from '../api/auth';
import { LandingPage } from '../pages/LandingPage';
import { DashboardSkeleton } from './Skeletons';

export function RootGate() {
  const { data: user, isLoading } = useCurrentUser();

  if (isLoading) {
    return (
      <div className="space-y-6" data-testid="root-loading">
        <div className="flex items-center gap-3 py-4">
          <div className="w-5 h-5 rounded-full border-2 border-cyan-500 border-t-transparent animate-spin" />
          <span className="text-sm text-slate-400 font-mono">Initializing CommitRush...</span>
        </div>
        <DashboardSkeleton />
      </div>
    );
  }

  if (user?.is_authenticated) {
    return <Navigate to="/profile" replace />;
  }

  return <LandingPage />;
}
