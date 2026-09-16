export function ProjectsListSkeleton() {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5" data-testid="projects-skeleton">
      {[1, 2, 3, 4, 5, 6].map((i) => (
        <div
          key={i}
          className="bg-slate-900/60 border border-slate-800 rounded-xl p-5 space-y-4 animate-pulse"
        >
          <div className="flex items-start justify-between">
            <div className="h-5 bg-slate-800 rounded w-2/3" />
            <div className="h-5 bg-slate-800 rounded-full w-16" />
          </div>
          <div className="space-y-2">
            <div className="h-3.5 bg-slate-800/80 rounded w-full" />
            <div className="h-3.5 bg-slate-800/60 rounded w-4/5" />
          </div>
          <div className="pt-2 flex items-center justify-between border-t border-slate-800/60">
            <div className="h-4 bg-slate-800 rounded w-20" />
            <div className="h-4 bg-slate-800 rounded w-24" />
          </div>
        </div>
      ))}
    </div>
  );
}

export function IssuesListSkeleton() {
  return (
    <div className="space-y-3.5" data-testid="issues-skeleton">
      {[1, 2, 3, 4, 5, 6, 7].map((i) => (
        <div
          key={i}
          className="bg-slate-900/60 border border-slate-800 rounded-xl p-5 space-y-3 animate-pulse"
        >
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
            <div className="h-5 bg-slate-800 rounded w-3/4 sm:w-1/2" />
            <div className="flex gap-2">
              <div className="h-6 bg-slate-800 rounded-full w-16" />
              <div className="h-6 bg-slate-800 rounded-full w-20" />
            </div>
          </div>
          <div className="flex items-center gap-3">
            <div className="h-4 bg-slate-800/80 rounded w-32" />
            <div className="h-4 bg-slate-800/80 rounded w-20" />
          </div>
          <div className="flex gap-1.5 pt-1">
            <div className="h-5 bg-slate-800/60 rounded-md w-14" />
            <div className="h-5 bg-slate-800/60 rounded-md w-16" />
          </div>
        </div>
      ))}
    </div>
  );
}

export function ProjectDetailSkeleton() {
  return (
    <div className="space-y-8 animate-pulse" data-testid="project-detail-skeleton">
      <div className="space-y-3">
        <div className="h-4 bg-slate-800 rounded w-24" />
        <div className="h-8 bg-slate-800 rounded w-1/2" />
        <div className="h-4 bg-slate-800/70 rounded w-3/4" />
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        {[1, 2, 3].map((i) => (
          <div key={i} className="bg-slate-900 border border-slate-800 rounded-xl p-5 space-y-2">
            <div className="h-4 bg-slate-800 rounded w-1/2" />
            <div className="h-8 bg-slate-800 rounded w-1/3" />
          </div>
        ))}
      </div>
    </div>
  );
}

export function IssueDetailSkeleton() {
  return (
    <div className="space-y-6 animate-pulse max-w-4xl mx-auto" data-testid="issue-detail-skeleton">
      <div className="h-4 bg-slate-800 rounded w-28" />
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 sm:p-8 space-y-6">
        <div className="space-y-3">
          <div className="flex gap-2">
            <div className="h-6 bg-slate-800 rounded-full w-20" />
            <div className="h-6 bg-slate-800 rounded-full w-16" />
          </div>
          <div className="h-8 bg-slate-800 rounded w-4/5" />
          <div className="h-4 bg-slate-800/80 rounded w-1/3" />
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 py-4 border-y border-slate-800/70">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="space-y-1">
              <div className="h-3 bg-slate-800 rounded w-16" />
              <div className="h-5 bg-slate-800 rounded w-24" />
            </div>
          ))}
        </div>

        <div className="h-10 bg-slate-800 rounded-xl w-48" />
      </div>
    </div>
  );
}

export function ContributionsListSkeleton() {
  return (
    <div className="space-y-4" data-testid="contributions-skeleton">
      {[1, 2, 3, 4, 5].map((i) => (
        <div
          key={i}
          className="bg-slate-900/60 border border-slate-800 rounded-xl p-5 space-y-3.5 animate-pulse"
        >
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div className="space-y-2 flex-1">
              <div className="h-5 bg-slate-800 rounded w-2/3" />
              <div className="h-3.5 bg-slate-800/70 rounded w-1/3" />
            </div>
            <div className="h-7 bg-slate-800 rounded-full w-28" />
          </div>
          <div className="h-4 bg-slate-800/50 rounded w-4/5" />
          <div className="pt-2 flex items-center justify-between border-t border-slate-800/50 text-xs text-slate-500">
            <div className="h-3.5 bg-slate-800 rounded w-24" />
            <div className="h-3.5 bg-slate-800 rounded w-32" />
          </div>
        </div>
      ))}
    </div>
  );
}

export function ContributionDetailSkeleton() {
  return (
    <div className="space-y-6 animate-pulse max-w-4xl mx-auto" data-testid="contribution-detail-skeleton">
      <div className="h-4 bg-slate-800 rounded w-32" />
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 sm:p-8 space-y-6">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="space-y-2 flex-1">
            <div className="h-7 bg-slate-800 rounded w-3/4" />
            <div className="h-4 bg-slate-800/80 rounded w-1/2" />
          </div>
          <div className="h-8 bg-slate-800 rounded-full w-32" />
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 py-4 border-y border-slate-800/70">
          {[1, 2, 3].map((i) => (
            <div key={i} className="space-y-1">
              <div className="h-3 bg-slate-800 rounded w-20" />
              <div className="h-5 bg-slate-800 rounded w-28" />
            </div>
          ))}
        </div>

        <div className="space-y-3">
          <div className="h-4 bg-slate-800 rounded w-24" />
          <div className="h-16 bg-slate-800/60 rounded-xl w-full" />
        </div>
      </div>
    </div>
  );
}

export function LeaderboardSkeleton() {
  return (
    <div className="space-y-4" data-testid="leaderboard-skeleton">
      <div className="h-16 bg-slate-900/60 border border-slate-800 rounded-xl p-4 animate-pulse" />
      <div className="space-y-2">
        {[1, 2, 3, 4, 5, 6, 7, 8].map((i) => (
          <div
            key={i}
            className="bg-slate-900/60 border border-slate-800 rounded-xl p-4 flex items-center justify-between gap-4 animate-pulse"
          >
            <div className="flex items-center gap-4">
              <div className="w-8 h-8 rounded-full bg-slate-800" />
              <div className="w-10 h-10 rounded-full bg-slate-800" />
              <div className="space-y-1">
                <div className="h-4 bg-slate-800 rounded w-32" />
                <div className="h-3 bg-slate-800/60 rounded w-20" />
              </div>
            </div>
            <div className="flex items-center gap-6">
              <div className="h-5 bg-slate-800 rounded w-16" />
              <div className="h-6 bg-slate-800 rounded w-20" />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export function DashboardSkeleton() {
  return (
    <div className="space-y-8 animate-pulse" data-testid="dashboard-skeleton">
      <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-6 flex flex-col sm:flex-row items-center justify-between gap-6">
        <div className="flex items-center gap-4">
          <div className="w-16 h-16 rounded-2xl bg-slate-800" />
          <div className="space-y-2">
            <div className="h-6 bg-slate-800 rounded w-40" />
            <div className="h-4 bg-slate-800/70 rounded w-24" />
          </div>
        </div>
        <div className="grid grid-cols-3 gap-4 w-full sm:w-auto">
          <div className="h-14 bg-slate-800 rounded-xl w-24" />
          <div className="h-14 bg-slate-800 rounded-xl w-24" />
          <div className="h-14 bg-slate-800 rounded-xl w-24" />
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="h-48 bg-slate-900/60 border border-slate-800 rounded-2xl p-6" />
        <div className="h-48 bg-slate-900/60 border border-slate-800 rounded-2xl p-6" />
      </div>

      <div className="space-y-4">
        <div className="h-6 bg-slate-800 rounded w-48" />
        <div className="space-y-3">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-16 bg-slate-900/60 border border-slate-800 rounded-xl" />
          ))}
        </div>
      </div>
    </div>
  );
}

export function ProfileSkeleton() {
  return (
    <div className="space-y-8 animate-pulse max-w-4xl mx-auto" data-testid="profile-skeleton">
      <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-6 sm:p-8 flex flex-col sm:flex-row items-center gap-6">
        <div className="w-20 h-20 rounded-full bg-slate-800" />
        <div className="space-y-2 text-center sm:text-left flex-1">
          <div className="h-7 bg-slate-800 rounded w-48 mx-auto sm:mx-0" />
          <div className="h-4 bg-slate-800/70 rounded w-32 mx-auto sm:mx-0" />
        </div>
        <div className="flex gap-4">
          <div className="h-16 bg-slate-800 rounded-xl w-24" />
          <div className="h-16 bg-slate-800 rounded-xl w-24" />
        </div>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="bg-slate-900/60 border border-slate-800 rounded-xl p-5 space-y-2">
            <div className="h-3.5 bg-slate-800 rounded w-20" />
            <div className="h-7 bg-slate-800 rounded w-12" />
          </div>
        ))}
      </div>

      <div className="space-y-4">
        <div className="h-6 bg-slate-800 rounded w-48" />
        <div className="space-y-3">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-16 bg-slate-900/60 border border-slate-800 rounded-xl" />
          ))}
        </div>
      </div>
    </div>
  );
}

export function StatsSkeleton() {
  return (
    <div className="space-y-8 animate-pulse" data-testid="stats-skeleton">
      <div className="space-y-2">
        <div className="h-8 bg-slate-800 rounded w-48" />
        <div className="h-4 bg-slate-800/70 rounded w-80" />
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="bg-slate-900/60 border border-slate-800 rounded-2xl p-6 space-y-3">
            <div className="h-4 bg-slate-800 rounded w-24" />
            <div className="h-9 bg-slate-800 rounded w-20" />
            <div className="h-3 bg-slate-800/60 rounded w-32" />
          </div>
        ))}
      </div>

      <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-6 space-y-4">
        <div className="h-6 bg-slate-800 rounded w-56" />
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-4">
          {[1, 2, 3, 4, 5, 6, 7, 8, 9].map((i) => (
            <div key={i} className="bg-slate-950/60 border border-slate-800/80 rounded-xl p-4 space-y-2">
              <div className="h-3.5 bg-slate-800 rounded w-16" />
              <div className="h-6 bg-slate-800 rounded w-12" />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

