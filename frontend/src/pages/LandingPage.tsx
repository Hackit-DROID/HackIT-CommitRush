import { Link, useSearchParams } from 'react-router-dom';
import { useStats } from '../api/stats';
import { useIssues } from '../api/issues';
import { useDocumentTitle } from '../hooks/useDocumentTitle';

export function LandingPage() {
  useDocumentTitle(
    'CommitRush — Open-Source Contribution Drive',
    'CommitRush connects developers with real-world open-source issues and tracks contributions through a live contribution drive.'
  );

  const [searchParams] = useSearchParams();
  const loginRequired = searchParams.get('login_required') === '1';
  const { data: stats } = useStats();
  const { data: featuredIssuesData } = useIssues({ is_featured: true, page_size: 4 });

  const featuredIssues = featuredIssuesData?.results || [];

  return (
    <div className="space-y-16 pb-12" data-testid="landing-page">
      {/* Optional Alert when redirected from a protected route */}
      {loginRequired && (
        <div
          className="bg-amber-950/60 border border-amber-500/40 rounded-2xl p-4 sm:p-5 flex items-center justify-between gap-4 text-amber-200 text-sm shadow-lg shadow-amber-950/20"
          data-testid="login-required-banner"
        >
          <div className="flex items-center gap-3">
            <span className="text-xl">🔒</span>
            <div>
              <p className="font-semibold text-white">Authentication Required</p>
              <p className="text-amber-300/80 text-xs sm:text-sm">
                Please sign in with GitHub to access your dashboard, track contributions, or manage activity.
              </p>
            </div>
          </div>
          <a
            href="/api/v1/auth/github/login/?next=/profile"
            className="shrink-0 px-4 py-2 rounded-xl bg-amber-500 hover:bg-amber-400 text-slate-950 font-bold text-xs transition-colors shadow-md"
          >
            Sign In Now
          </a>
        </div>
      )}

      {/* Hero Section */}
      <section className="relative overflow-hidden rounded-3xl bg-gradient-to-b from-slate-900 via-slate-900/90 to-slate-950 border border-slate-800 p-5 sm:p-10 lg:p-16 shadow-2xl shadow-slate-950/80">
        <div className="absolute -top-24 -right-24 w-96 h-96 bg-cyan-500/10 rounded-full blur-3xl pointer-events-none" />
        <div className="absolute -bottom-24 -left-24 w-96 h-96 bg-indigo-500/10 rounded-full blur-3xl pointer-events-none" />

        <div className="relative max-w-4xl mx-auto text-center space-y-6">
          {/* Live Badge */}
          <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-slate-800/90 border border-slate-700/80 text-xs font-mono text-cyan-300 shadow-inner">
            <span className="w-2 h-2 rounded-full bg-cyan-400 animate-pulse" />
            <span>HackIT Contribution Sprint • Monorepo Live</span>
          </div>

          {/* Main Title */}
          <h1 className="text-4xl sm:text-5xl lg:text-6xl font-black text-white tracking-tight leading-[1.1]">
            The Open-Source <br className="hidden sm:inline" />
            <span className="bg-gradient-to-r from-cyan-400 via-indigo-300 to-indigo-500 bg-clip-text text-transparent">
              Contribution Drive
            </span>{' '}
            for Developers
          </h1>

          {/* Subtitle */}
          <p className="text-base sm:text-lg text-slate-300 max-w-2xl mx-auto leading-relaxed">
            CommitRush connects college developers directly with real-world open-source repositories.
            Solve verified issues, open pull requests on GitHub, pass automated validation pipelines, and compete in real-time.
          </p>

          {/* Action CTAs */}
          <div className="pt-4 flex flex-col sm:flex-row items-center justify-center gap-4">
            {/* Primary GitHub Login CTA */}
            <a
              href="/api/v1/auth/github/login/?next=/profile"
              className="w-full sm:w-auto inline-flex items-center justify-center gap-3 px-8 py-4 rounded-2xl bg-white hover:bg-slate-100 text-slate-950 font-bold text-base shadow-xl shadow-white/10 hover:shadow-cyan-500/20 transition-all hover:scale-[1.02] active:scale-[0.98] group"
              data-testid="github-login-cta"
            >
              <svg
                className="w-5 h-5 fill-current text-slate-950 group-hover:scale-110 transition-transform"
                viewBox="0 0 24 24"
              >
                <path fillRule="evenodd" clipRule="evenodd" d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.53 1.032 1.53 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z" />
              </svg>
              <span>Continue with GitHub</span>
            </a>

            {/* Secondary Explorer CTAs */}
            <Link
              to="/issues"
              className="w-full sm:w-auto inline-flex items-center justify-center gap-2 px-6 py-4 rounded-2xl bg-slate-800 hover:bg-slate-700 text-slate-200 hover:text-white font-semibold text-base border border-slate-700/80 transition-all shadow-sm"
            >
              <span>Explore 1,500+ Issues</span>
              <span className="text-cyan-400 font-mono">→</span>
            </Link>

            <Link
              to="/leaderboard"
              className="w-full sm:w-auto inline-flex items-center justify-center gap-2 px-6 py-4 rounded-2xl bg-slate-900/80 hover:bg-slate-800 text-slate-300 hover:text-white font-medium text-base border border-slate-800 transition-all shadow-sm"
            >
              <span>View Leaderboard</span>
            </Link>
          </div>

          {/* Dev Quick-Login Bar (Convenience for testing) */}
          <div className="pt-3 text-xs text-slate-400 flex flex-wrap items-center justify-center gap-2">
            <span className="text-slate-500">Quick Test Sign-in:</span>
            <a
              href="/api/v1/auth/dev-login/?username=sarah_dev&next=/profile"
              className="px-2.5 py-1 rounded-md bg-slate-800 hover:bg-slate-700 text-cyan-400 font-mono transition-colors"
            >
              sarah_dev (Rank #1)
            </a>
            <a
              href="/api/v1/auth/dev-login/?username=alex_builder&next=/profile"
              className="px-2.5 py-1 rounded-md bg-slate-800 hover:bg-slate-700 text-cyan-400 font-mono transition-colors"
            >
              alex_builder (Rank #2)
            </a>
            <a
              href="/api/v1/auth/dev-login/?username=admin&next=/profile"
              className="px-2.5 py-1 rounded-md bg-slate-800 hover:bg-slate-700 text-amber-400 font-mono transition-colors"
            >
              admin (Staff)
            </a>
          </div>
        </div>

        {/* Live Metrics Grid */}
        <div className="mt-12 pt-8 border-t border-slate-800/80 grid grid-cols-2 md:grid-cols-4 gap-4 sm:gap-6">
          <div className="bg-slate-950/60 border border-slate-800/60 rounded-2xl p-4 text-center">
            <span className="text-2xl sm:text-3xl font-black text-cyan-400 font-mono block">
              1,500+
            </span>
            <span className="text-xs text-slate-400 font-medium uppercase tracking-wider mt-1 block">
              Curated Issues
            </span>
          </div>

          <div className="bg-slate-950/60 border border-slate-800/60 rounded-2xl p-4 text-center">
            <span className="text-2xl sm:text-3xl font-black text-indigo-400 font-mono block">
              {stats?.participants?.total ? stats.participants.total : '100+'}
            </span>
            <span className="text-xs text-slate-400 font-medium uppercase tracking-wider mt-1 block">
              Active Participants
            </span>
          </div>

          <div className="bg-slate-950/60 border border-slate-800/60 rounded-2xl p-4 text-center">
            <span className="text-2xl sm:text-3xl font-black text-emerald-400 font-mono block">
              {stats?.pull_requests?.merged !== undefined ? stats.pull_requests.merged : '120+'}
            </span>
            <span className="text-xs text-slate-400 font-medium uppercase tracking-wider mt-1 block">
              Merged PRs
            </span>
          </div>

          <div className="bg-slate-950/60 border border-slate-800/60 rounded-2xl p-4 text-center">
            <span className="text-2xl sm:text-3xl font-black text-amber-400 font-mono block">
              {stats?.points?.total_awarded !== undefined ? `${stats.points.total_awarded.toLocaleString()} pts` : '15,000+ pts'}
            </span>
            <span className="text-xs text-slate-400 font-medium uppercase tracking-wider mt-1 block">
              Points Awarded
            </span>
          </div>
        </div>
      </section>

      {/* How It Works Section */}
      <section className="space-y-8">
        <div className="text-center space-y-2 max-w-2xl mx-auto">
          <h2 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight">
            How CommitRush Works
          </h2>
          <p className="text-sm text-slate-400">
            A seamless 4-step contribution lifecycle designed for real open-source impact.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          {/* Step 1 */}
          <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-6 space-y-4 hover:border-slate-700 transition-colors relative overflow-hidden group">
            <div className="w-10 h-10 rounded-xl bg-cyan-950/80 border border-cyan-500/30 flex items-center justify-center font-mono font-bold text-cyan-400 text-sm">
              01
            </div>
            <h3 className="text-lg font-bold text-white tracking-tight">
              1. Browse & Pick Issues
            </h3>
            <p className="text-xs sm:text-sm text-slate-400 leading-relaxed">
              Explore 1,500+ issues across frontend, backend, algorithms, and tooling. Filter by difficulty (<span className="text-emerald-400 font-mono">starter</span>, <span className="text-cyan-400 font-mono">intermediate</span>, <span className="text-indigo-400 font-mono">advanced</span>) and point bounties.
            </p>
          </div>

          {/* Step 2 */}
          <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-6 space-y-4 hover:border-slate-700 transition-colors relative overflow-hidden group">
            <div className="w-10 h-10 rounded-xl bg-indigo-950/80 border border-indigo-500/30 flex items-center justify-center font-mono font-bold text-indigo-400 text-sm">
              02
            </div>
            <h3 className="text-lg font-bold text-white tracking-tight">
              2. Fork, Code & Solve
            </h3>
            <p className="text-xs sm:text-sm text-slate-400 leading-relaxed">
              Fork the official repository, clone it locally, write clean code with proper tests, and commit your changes following clean repository guidelines.
            </p>
          </div>

          {/* Step 3 */}
          <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-6 space-y-4 hover:border-slate-700 transition-colors relative overflow-hidden group">
            <div className="w-10 h-10 rounded-xl bg-purple-950/80 border border-purple-500/30 flex items-center justify-center font-mono font-bold text-purple-400 text-sm">
              03
            </div>
            <h3 className="text-lg font-bold text-white tracking-tight">
              3. Open PR with Link
            </h3>
            <p className="text-xs sm:text-sm text-slate-400 leading-relaxed">
              Open a Pull Request on GitHub referencing your issue in the body (<code className="text-purple-300 font-mono text-[11px] bg-purple-950/50 px-1 py-0.5 rounded">Fixes #123</code>). Our webhook pipeline picks it up automatically in seconds.
            </p>
          </div>

          {/* Step 4 */}
          <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-6 space-y-4 hover:border-slate-700 transition-colors relative overflow-hidden group">
            <div className="w-10 h-10 rounded-xl bg-emerald-950/80 border border-emerald-500/30 flex items-center justify-center font-mono font-bold text-emerald-400 text-sm">
              04
            </div>
            <h3 className="text-lg font-bold text-white tracking-tight">
              4. Validation & Points
            </h3>
            <p className="text-xs sm:text-sm text-slate-400 leading-relaxed">
              Our automated worker checks PR diffs, validates rules, and enters the bounded merge queue. Once merged, points credit to your profile and the leaderboard updates instantly.
            </p>
          </div>
        </div>
      </section>

      {/* Real-World Monorepo & System Features */}
      <section className="bg-slate-900/40 border border-slate-800/80 rounded-3xl p-5 sm:p-10 space-y-8">
        <div className="flex flex-col md:flex-row md:items-end justify-between gap-4">
          <div className="space-y-2">
            <span className="text-xs font-mono uppercase tracking-wider text-cyan-400">
              Source of Truth Integration
            </span>
            <h2 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight">
              Powered by Real Open-Source Projects
            </h2>
            <p className="text-sm text-slate-400 max-w-2xl">
              All issues and projects are synchronized directly from the official HackIT Open-Source Contribution Drive.
            </p>
          </div>
          <a
            href="https://github.com/Hackit-DROID/Open-Source-Contribution-Drive"
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold border border-slate-700 transition-colors"
          >
            <span>View Source Repository</span>
            <span className="text-slate-400">↗</span>
          </a>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="bg-slate-950/70 border border-slate-800/80 rounded-2xl p-6 space-y-3">
            <div className="text-2xl">⚡</div>
            <h3 className="text-base font-bold text-white">Automated Validation</h3>
            <p className="text-xs sm:text-sm text-slate-400 leading-relaxed">
              Real-time validation checks PR branch names, diff size, commit structure, and issue associations without manual bottlenecks.
            </p>
          </div>

          <div className="bg-slate-950/70 border border-slate-800/80 rounded-2xl p-6 space-y-3">
            <div className="text-2xl">🚦</div>
            <h3 className="text-base font-bold text-white">Bounded Merge Queue</h3>
            <p className="text-xs sm:text-sm text-slate-400 leading-relaxed">
              Concurrency-controlled merge semaphore prevents race conditions, git lock contention, and duplicate point crediting.
            </p>
          </div>

          <div className="bg-slate-950/70 border border-slate-800/80 rounded-2xl p-6 space-y-3">
            <div className="text-2xl">⚖️</div>
            <h3 className="text-base font-bold text-white">Fair-Play Daily Caps</h3>
            <p className="text-xs sm:text-sm text-slate-400 leading-relaxed">
              Configurable daily quotas (5 PRs / 500 points per day) prevent script spam and ensure a level playing field for all developers.
            </p>
          </div>
        </div>
      </section>

      {/* Featured Issues Preview */}
      {featuredIssues.length > 0 && (
        <section className="space-y-6">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-2xl font-bold text-white tracking-tight">
                Featured Contribution Issues
              </h2>
              <p className="text-xs sm:text-sm text-slate-400">
                Jump into high-impact issues ready for pull requests.
              </p>
            </div>
            <Link
              to="/issues"
              className="text-xs sm:text-sm text-cyan-400 hover:text-cyan-300 font-semibold flex items-center gap-1 transition-colors"
            >
              <span>View all issues</span>
              <span>→</span>
            </Link>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {featuredIssues.map((issue) => (
              <Link
                key={issue.id}
                to={`/issues/${issue.id}`}
                className="group bg-slate-900/60 hover:bg-slate-900 border border-slate-800 hover:border-slate-700 rounded-2xl p-5 transition-all shadow-sm flex flex-col justify-between gap-4"
              >
                <div className="space-y-2">
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-xs font-mono text-cyan-400">
                      {issue.project} #{issue.github_number}
                    </span>
                    <div className="flex items-center gap-1.5">
                      <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold uppercase font-mono bg-cyan-950/60 border border-cyan-800/50 text-cyan-300">
                        {issue.difficulty}
                      </span>
                      <span className="px-2 py-0.5 rounded-full text-[10px] font-bold font-mono bg-amber-950/60 border border-amber-800/50 text-amber-300">
                        {issue.points} pts
                      </span>
                    </div>
                  </div>
                  <h3 className="text-base font-bold text-white group-hover:text-cyan-300 transition-colors line-clamp-1">
                    {issue.title}
                  </h3>
                </div>

                <div className="flex items-center justify-between text-xs text-slate-400 pt-2 border-t border-slate-800/60">
                  <span className="capitalize">{issue.category || 'General'}</span>
                  <span className="text-indigo-400 group-hover:translate-x-0.5 transition-transform">
                    View Issue Details →
                  </span>
                </div>
              </Link>
            ))}
          </div>
        </section>
      )}

      {/* Bottom CTA Section */}
      <section className="relative overflow-hidden rounded-3xl bg-gradient-to-r from-cyan-950/50 via-slate-900 to-indigo-950/50 border border-slate-800 p-6 sm:p-12 text-center space-y-6">
        <h2 className="text-3xl sm:text-4xl font-black text-white tracking-tight">
          Ready to Make Your Mark?
        </h2>
        <p className="text-sm sm:text-base text-slate-300 max-w-xl mx-auto leading-relaxed">
          Sign in with your GitHub account to start claiming issues, opening pull requests, and climbing the sprint leaderboard.
        </p>
        <div className="pt-2 flex flex-col sm:flex-row items-center justify-center gap-4">
          <a
            href="/api/v1/auth/github/login/?next=/profile"
            className="w-full sm:w-auto inline-flex items-center justify-center gap-2.5 px-8 py-3.5 rounded-2xl bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-bold text-sm shadow-xl shadow-cyan-500/20 transition-all hover:scale-[1.02] active:scale-[0.98]"
          >
            <span>Start with GitHub</span>
            <span>→</span>
          </a>
          <Link
            to="/projects"
            className="w-full sm:w-auto inline-flex items-center justify-center gap-2 px-6 py-3.5 rounded-2xl bg-slate-800 hover:bg-slate-700 text-slate-200 font-semibold text-sm border border-slate-700/80 transition-colors"
          >
            Browse Projects
          </Link>
        </div>
      </section>
    </div>
  );
}
