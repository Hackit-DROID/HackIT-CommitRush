import { useState, useEffect } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { useStats } from '../api/stats';
import { useIssues } from '../api/issues';
import { getGitHubLoginUrl } from '../api/auth';
import { useDocumentTitle } from '../hooks/useDocumentTitle';

// Target kickoff date: September 22, 2026 10:00 AM IST
const KICKOFF_DATE = new Date('2026-09-22T10:00:00+05:30');

export function LandingPage() {
  useDocumentTitle(
    'CommitRush 2026 — Open-Source Contribution Challenge',
    'CommitRush is a 21-day open-source contribution sprint by HACKIT at SGGSIE&T, Nanded. Find real issues, make meaningful contributions, and learn through open source.'
  );

  const [searchParams] = useSearchParams();
  const loginRequired = searchParams.get('login_required') === '1';
  const { data: stats } = useStats();
  const { data: featuredIssuesData } = useIssues({ is_featured: true, page_size: 4 });
  const featuredIssues = featuredIssuesData?.results || [];

  // Countdown timer calculation
  const [timeLeft, setTimeLeft] = useState(() => calculateTimeLeft());

  function calculateTimeLeft() {
    const diff = KICKOFF_DATE.getTime() - Date.now();
    if (diff <= 0) {
      return { days: 0, hours: 0, minutes: 0, seconds: 0, isLive: true };
    }
    return {
      days: Math.floor(diff / (1000 * 60 * 60 * 24)),
      hours: Math.floor((diff / (1000 * 60 * 60)) % 24),
      minutes: Math.floor((diff / 1000 / 60) % 60),
      seconds: Math.floor((diff / 1000) % 60),
      isLive: false,
    };
  }

  useEffect(() => {
    const timer = setInterval(() => {
      setTimeLeft(calculateTimeLeft());
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  return (
    <div className="space-y-20 pb-20" data-testid="landing-page">
      {/* Optional Alert when redirected from a protected route */}
      {loginRequired && (
        <div
          className="bg-white border border-amber-300 rounded-md p-5 flex items-center justify-between gap-4 text-amber-900 text-sm shadow-sm"
          data-testid="login-required-banner"
        >
          <div className="flex items-center gap-3">
            <span className="text-xl">🔒</span>
            <div>
              <p className="font-bold text-[#111111]">Authentication Required</p>
              <p className="text-[#555555] text-xs sm:text-sm">
                Please sign in with GitHub to access your profile, submit contributions, or track your points.
              </p>
            </div>
          </div>
          <a
            href={getGitHubLoginUrl('/profile')}
            className="shrink-0 px-5 py-2.5 rounded-[4px] bg-[#050505] hover:bg-[#1a1a1a] text-white font-medium text-xs transition-colors shadow-sm"
          >
            Sign In with GitHub
          </a>
        </div>
      )}

      {/* SECTION 1: EDITORIAL HERO */}
      <section className="relative overflow-hidden rounded-lg bg-white border border-[#d8d8d3] p-6 sm:p-12 lg:p-16 shadow-sm">
        {/* Subtle warm wash */}
        <div className="absolute top-0 right-0 w-[500px] h-[500px] bg-[radial-gradient(circle_at_70%_25%,rgba(255,90,31,0.06),transparent_65%)] pointer-events-none" />
        <div className="absolute bottom-0 left-0 w-[400px] h-[400px] bg-[radial-gradient(circle_at_20%_80%,rgba(61,95,88,0.06),transparent_60%)] pointer-events-none" />

        <div className="relative grid grid-cols-1 lg:grid-cols-12 gap-10 lg:gap-12 items-center">
          {/* Left Column: Typography & CTAs */}
          <div className="lg:col-span-7 space-y-6 text-left">
            {/* Eyebrow */}
            <div className="inline-flex items-center gap-2.5 px-3 py-1 rounded-full bg-[#f4f4f1] border border-[#d8d8d3] text-xs font-mono font-medium text-[#111111]">
              <span className="w-1.5 h-1.5 rounded-full bg-[#ff5a1f]" />
              <span>HACKIT PRESENTS • COMMITRUSH 2026</span>
            </div>

            {/* Headline */}
            <div className="space-y-1">
              <h1 className="text-5xl sm:text-6xl lg:text-7xl font-display font-extrabold tracking-tight text-[#111111] leading-[1.05]">
                COMMIT<br />
                <span className="text-[#ff5a1f]">RUSH</span>
              </h1>
              <p className="text-xl sm:text-2xl font-display font-semibold text-[#111111] pt-2">
                The Open-Source <span className="text-[#ff5a1f]">Contribution Drive</span> for Developers
              </p>
            </div>

            {/* Supporting Lines */}
            <p className="text-sm sm:text-base text-[#555555] max-w-xl leading-relaxed">
              A 21-day open-source contribution challenge. Find a real issue, understand the project, make a meaningful change, open a pull request, and learn by contributing.
            </p>

            {/* Action Buttons */}
            <div className="pt-2 flex flex-col sm:flex-row items-stretch sm:items-center gap-3.5">
              {/* Primary GitHub Login CTA */}
              <a
                href={getGitHubLoginUrl('/profile')}
                className="inline-flex items-center justify-center gap-2.5 px-7 py-3.5 rounded-[4px] bg-[#050505] hover:bg-[#1a1a1a] text-white font-semibold text-sm shadow-sm hover:scale-[1.01] active:scale-[0.99] transition-all group"
                data-testid="github-login-cta"
              >
                <svg className="w-4 h-4 fill-current shrink-0 group-hover:scale-110 transition-transform" viewBox="0 0 24 24">
                  <path fillRule="evenodd" clipRule="evenodd" d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.53 1.032 1.53 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z" />
                </svg>
                <span>Register for CommitRush →</span>
              </a>

              {/* Secondary CTAs */}
              <Link
                to="/issues"
                className="inline-flex items-center justify-center gap-2 px-6 py-3.5 rounded-[4px] bg-transparent hover:bg-black/5 text-[#050505] font-medium text-sm border border-[#050505] transition-all"
              >
                <span>Explore 1,500+ Issues</span>
                <span className="text-[#ff5a1f] font-mono text-xs">→</span>
              </Link>

              <Link
                to="/leaderboard"
                className="inline-flex items-center justify-center gap-2 px-5 py-3.5 rounded-[4px] text-[#555555] hover:text-[#111111] font-medium text-sm transition-colors"
              >
                <span>View Leaderboard</span>
              </Link>
            </div>

            {/* Metadata Footer */}
            <div className="pt-3 flex flex-wrap items-center gap-x-6 gap-y-2 text-xs font-mono text-[#777777]">
              <span className="text-[#111111]">22 SEP — 12 OCT 2026</span>
              <span>•</span>
              <span className="text-[#111111]">INDIVIDUAL PARTICIPATION</span>
              <span>•</span>
              <span className="text-[#111111]">21 DAYS</span>
            </div>

          </div>

          {/* Right Column: Signature Editorial Visual */}
          <div className="lg:col-span-5 relative flex items-center justify-center">
            <div className="w-full max-w-[380px] sm:max-w-[420px] aspect-square rounded-md bg-[#f4f4f1] border border-[#d8d8d3] p-6 flex flex-col justify-between relative overflow-hidden shadow-sm">
              {/* Subtle background curved branch lines */}
              <svg className="absolute inset-0 w-full h-full stroke-black/5 fill-none" viewBox="0 0 400 400">
                <path d="M 50 350 C 120 300, 160 220, 220 200 C 280 180, 320 100, 350 50" strokeWidth="2" />
                <path d="M 120 300 C 180 320, 240 330, 320 280" strokeWidth="2" strokeDasharray="4 6" />
                <path d="M 220 200 C 250 160, 280 160, 350 170" strokeWidth="2" stroke="rgba(255,90,31,0.2)" />
              </svg>

              {/* Top Badge */}
              <div className="flex items-center justify-between relative z-10">
                <span className="px-3 py-1 rounded-full text-[11px] font-mono font-medium bg-white border border-[#d8d8d3] text-[#555555]">
                  EDITION 2026
                </span>
                <span className="w-2 h-2 rounded-full bg-[#ff5a1f]" />
              </div>

              {/* Center Artwork */}
              <div className="relative z-10 my-auto flex flex-col items-center justify-center py-2">
                <div className="relative w-56 h-56 sm:w-60 sm:h-60 flex items-center justify-center">
                  {/* Soft vermilion radial wash behind mascot */}
                  <div className="absolute inset-0 rounded-full bg-[#ff5a1f]/10 blur-xl pointer-events-none" />
                  
                  <img
                    src="/hero-mascot.png"
                    alt="CommitRush Hero Character"
                    className="w-full h-full object-contain mix-blend-multiply drop-shadow-sm relative z-10"
                  />
                </div>

                <span className="text-[11px] font-mono tracking-widest text-[#777777] uppercase mt-2">
                  CODE • COMMIT • CONTRIBUTE
                </span>
              </div>

              {/* Bottom Quote Capsule */}
              <div className="relative z-10 pt-3 border-t border-[#d8d8d3] flex items-center justify-between text-[11px] text-[#555555]">
                <span className="font-mono">SGGSIE&T • NANDED</span>
                <span className="font-mono text-[#ff5a1f]">DAY 00 / 21</span>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* SECTION 2: EVENT KICKOFF & COUNTDOWN BANNER */}
      <section className="rounded-md bg-white border border-[#d8d8d3] p-6 sm:p-8 flex flex-col md:flex-row items-center justify-between gap-6 shadow-sm">
        <div className="space-y-1.5 text-center md:text-left">
          <div className="flex items-center justify-center md:justify-start gap-2 text-xs font-mono text-[#ff5a1f]">
            <span className="w-2 h-2 rounded-full bg-[#ff5a1f] animate-pulse" />
            <span>KICKOFF CEREMONY</span>
          </div>
          <h2 className="text-xl sm:text-2xl font-display font-bold text-[#111111] tracking-tight">
            22 September 2026 · A4 Hall · SGGSIE&T
          </h2>
          <p className="text-xs sm:text-sm text-[#555555]">
            Registration is currently open. Remote participation permitted across all 21 days.
          </p>
        </div>

        {/* Countdown display */}
        <div className="flex items-center gap-3 sm:gap-4 font-mono text-center shrink-0">
          <div className="bg-[#f4f4f1] border border-[#d8d8d3] rounded-md px-3.5 py-2.5 min-w-[64px]">
            <span className="text-2xl font-display font-bold text-[#111111] block">{timeLeft.days}</span>
            <span className="text-[10px] text-[#777777] uppercase">Days</span>
          </div>
          <span className="text-[#777777] font-bold">:</span>
          <div className="bg-[#f4f4f1] border border-[#d8d8d3] rounded-md px-3.5 py-2.5 min-w-[64px]">
            <span className="text-2xl font-display font-bold text-[#111111] block">
              {String(timeLeft.hours).padStart(2, '0')}
            </span>
            <span className="text-[10px] text-[#777777] uppercase">Hours</span>
          </div>
          <span className="text-[#777777] font-bold">:</span>
          <div className="bg-[#f4f4f1] border border-[#d8d8d3] rounded-md px-3.5 py-2.5 min-w-[64px]">
            <span className="text-2xl font-display font-bold text-[#111111] block">
              {String(timeLeft.minutes).padStart(2, '0')}
            </span>
            <span className="text-[10px] text-[#777777] uppercase">Mins</span>
          </div>
          <span className="text-[#777777] font-bold">:</span>
          <div className="bg-[#f4f4f1] border border-[#d8d8d3] rounded-md px-3.5 py-2.5 min-w-[64px]">
            <span className="text-2xl font-display font-bold text-[#ff5a1f] block">
              {String(timeLeft.seconds).padStart(2, '0')}
            </span>
            <span className="text-[10px] text-[#777777] uppercase">Secs</span>
          </div>
        </div>
      </section>

      {/* SECTION 3: EVENT SNAPSHOT */}
      <section className="grid grid-cols-2 md:grid-cols-4 gap-4 sm:gap-6">
        <div className="bg-white border border-[#d8d8d3] rounded-md p-5 sm:p-6 space-y-1 shadow-sm">
          <span className="text-2xl sm:text-3xl font-display font-bold text-[#111111] block">21 DAYS</span>
          <span className="text-xs sm:text-sm text-[#555555] block">22 Sep → 12 Oct 2026</span>
          <span className="text-[11px] text-[#777777] block pt-1">Sprint challenge window</span>
        </div>

        <div className="bg-white border border-[#d8d8d3] rounded-md p-5 sm:p-6 space-y-1 shadow-sm">
          <span className="text-2xl sm:text-3xl font-display font-bold text-[#111111] block">INDIVIDUAL</span>
          <span className="text-xs sm:text-sm text-[#555555] block">Contribute from anywhere</span>
          <span className="text-[11px] text-[#777777] block pt-1">Open to all students</span>
        </div>

        <div className="bg-white border border-[#d8d8d3] rounded-md p-5 sm:p-6 space-y-1 shadow-sm">
          <span className="text-2xl sm:text-3xl font-display font-bold text-[#111111] block">1,500+</span>
          <span className="text-xs sm:text-sm text-[#555555] block">Real Issues & Projects</span>
          <span className="text-[11px] text-[#777777] block pt-1">Vetted repositories</span>
        </div>

        <div className="bg-white border border-[#d8d8d3] rounded-md p-5 sm:p-6 space-y-1 shadow-sm">
          <span className="text-2xl sm:text-3xl font-display font-bold text-[#ff5a1f] block">REWARDS</span>
          <span className="text-xs sm:text-sm text-[#555555] block">Special prizes + certificates</span>
          <span className="text-[11px] text-[#777777] block pt-1">Certificates for everyone</span>
        </div>
      </section>

      {/* SECTION 4: WHY COMMITRUSH? */}
      <section className="space-y-8">
        <div className="max-w-3xl space-y-3">
          <span className="text-xs font-mono text-[#ff5a1f] uppercase tracking-widest block">
            THE PHILOSOPHY
          </span>
          <h2 className="text-3xl sm:text-4xl font-display font-extrabold text-[#111111] tracking-tight">
            Open source gets better when more people learn to contribute.
          </h2>
          <p className="text-base text-[#555555] leading-relaxed">
            CommitRush is built to make the first step into open source less intimidating. Instead of watching tutorials forever, participants learn by reading real repositories, understanding real issues, writing real code, opening real pull requests, and participating in code review.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="bg-white border border-[#d8d8d3] rounded-md p-6 space-y-3 shadow-sm">
            <span className="w-8 h-8 rounded-full bg-[#f4f4f1] border border-[#d8d8d3] flex items-center justify-center text-sm font-mono text-[#ff5a1f]">
              01
            </span>
            <h3 className="text-lg font-display font-bold text-[#111111]">Learn by doing</h3>
            <p className="text-xs sm:text-sm text-[#555555] leading-relaxed">
              Real repositories teach different lessons than isolated tutorials. You learn branching, unit testing conventions, commit hygiene, and maintainer collaboration.
            </p>
          </div>

          <div className="bg-white border border-[#d8d8d3] rounded-md p-6 space-y-3 shadow-sm">
            <span className="w-8 h-8 rounded-full bg-[#f4f4f1] border border-[#d8d8d3] flex items-center justify-center text-sm font-mono text-[#ff5a1f]">
              02
            </span>
            <h3 className="text-lg font-display font-bold text-[#111111]">Contribute with context</h3>
            <p className="text-xs sm:text-sm text-[#555555] leading-relaxed">
              A good contribution starts with understanding the project, reading its contribution guidelines, and respecting the maintainers' architecture.
            </p>
          </div>

          <div className="bg-white border border-[#d8d8d3] rounded-md p-6 space-y-3 shadow-sm">
            <span className="w-8 h-8 rounded-full bg-[#f4f4f1] border border-[#d8d8d3] flex items-center justify-center text-sm font-mono text-[#ff5a1f]">
              03
            </span>
            <h3 className="text-lg font-display font-bold text-[#111111]">Leave something better</h3>
            <p className="text-xs sm:text-sm text-[#555555] leading-relaxed">
              The goal is not simply to collect points or spam PR counts. It is to make an actual open-source repository better than you found it.
            </p>
          </div>
        </div>
      </section>

      {/* SECTION 5: HOW IT WORKS (Preserving test-required strings) */}
      <section className="space-y-8">
        <div className="space-y-2 max-w-2xl">
          <span className="text-xs font-mono text-[#ff5a1f] uppercase tracking-widest block">
            THE WORKFLOW
          </span>
          <h2 className="text-3xl sm:text-4xl font-display font-extrabold text-[#111111] tracking-tight">
            How CommitRush Works
          </h2>
          <p className="text-sm text-[#555555]">
            A clean 4-step contribution lifecycle designed for real open-source impact.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          {/* Step 1 */}
          <div className="bg-white border border-[#d8d8d3] rounded-md p-6 space-y-4 hover:border-[#111111] transition-colors relative shadow-sm">
            <div className="w-9 h-9 rounded-full bg-[#f4f4f1] border border-[#d8d8d3] flex items-center justify-center font-mono font-bold text-[#ff5a1f] text-xs">
              01
            </div>
            <h3 className="text-lg font-display font-bold text-[#111111] tracking-tight">
              1. Browse & Pick Issues
            </h3>
            <p className="text-xs sm:text-sm text-[#555555] leading-relaxed">
              Explore 1,500+ issues across frontend, backend, algorithms, and tooling. Filter by difficulty (<span className="text-[#111111] font-mono">starter</span>, <span className="text-[#111111] font-mono">intermediate</span>, <span className="text-[#111111] font-mono">advanced</span>) and point bounties.
            </p>
          </div>

          {/* Step 2 */}
          <div className="bg-white border border-[#d8d8d3] rounded-md p-6 space-y-4 hover:border-[#111111] transition-colors relative shadow-sm">
            <div className="w-9 h-9 rounded-full bg-[#f4f4f1] border border-[#d8d8d3] flex items-center justify-center font-mono font-bold text-[#ff5a1f] text-xs">
              02
            </div>
            <h3 className="text-lg font-display font-bold text-[#111111] tracking-tight">
              2. Fork, Code & Solve
            </h3>
            <p className="text-xs sm:text-sm text-[#555555] leading-relaxed">
              Fork the official repository, clone it locally, write clean code with proper tests, and commit your changes following clean repository guidelines.
            </p>
          </div>

          {/* Step 3 */}
          <div className="bg-white border border-[#d8d8d3] rounded-md p-6 space-y-4 hover:border-[#111111] transition-colors relative shadow-sm">
            <div className="w-9 h-9 rounded-full bg-[#f4f4f1] border border-[#d8d8d3] flex items-center justify-center font-mono font-bold text-[#ff5a1f] text-xs">
              03
            </div>
            <h3 className="text-lg font-display font-bold text-[#111111] tracking-tight">
              3. Open PR with Link
            </h3>
            <p className="text-xs sm:text-sm text-[#555555] leading-relaxed">
              Open a Pull Request on GitHub referencing your issue in the body (<code className="text-[#ff5a1f] font-mono text-[11px] bg-[#f4f4f1] px-1.5 py-0.5 rounded border border-[#d8d8d3]">Fixes #123</code>). Our webhook pipeline picks it up automatically in seconds.
            </p>
          </div>

          {/* Step 4 */}
          <div className="bg-white border border-[#d8d8d3] rounded-md p-6 space-y-4 hover:border-[#111111] transition-colors relative shadow-sm">
            <div className="w-9 h-9 rounded-full bg-[#f4f4f1] border border-[#d8d8d3] flex items-center justify-center font-mono font-bold text-[#ff5a1f] text-xs">
              04
            </div>
            <h3 className="text-lg font-display font-bold text-[#111111] tracking-tight">
              4. Validation & Points
            </h3>
            <p className="text-xs sm:text-sm text-[#555555] leading-relaxed">
              Our automated worker checks PR diffs, validates rules, and enters the bounded merge queue. Once merged, points credit to your profile and the leaderboard updates instantly.
            </p>
          </div>
        </div>
      </section>

      {/* SECTION 6: THE CONTRIBUTION JOURNEY (From Issue to Impact) */}
      <section className="rounded-md bg-white border border-[#d8d8d3] p-6 sm:p-10 space-y-6 shadow-sm">
        <div className="space-y-1">
          <span className="text-xs font-mono text-[#ff5a1f] uppercase tracking-widest block">
            THE JOURNEY
          </span>
          <h2 className="text-2xl sm:text-3xl font-display font-bold text-[#111111] tracking-tight">
            From issue to impact.
          </h2>
          <p className="text-xs sm:text-sm text-[#555555]">
            Everything that happens between finding an open issue and getting your contribution accepted.
          </p>
        </div>

        {/* Curved Journey Pathway */}
        <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-8 gap-3 pt-4">
          {[
            { step: '01', title: 'Find Issue' },
            { step: '02', title: 'Read Docs' },
            { step: '03', title: 'Fork & Clone' },
            { step: '04', title: 'Create Branch' },
            { step: '05', title: 'Write & Test' },
            { step: '06', title: 'Open PR' },
            { step: '07', title: 'Pass Review' },
            { step: '08', title: 'Merged & Ranked' },
          ].map((item, idx) => (
            <div
              key={item.step}
              className="bg-[#f4f4f1] border border-[#d8d8d3] rounded-md p-3 text-center space-y-1.5 relative group hover:border-[#111111] transition-colors"
            >
              <span className="text-[10px] font-mono text-[#777777] block">{item.step}</span>
              <span className="text-xs font-semibold text-[#111111] block">{item.title}</span>
              {idx < 7 && (
                <span className="hidden lg:block absolute -right-2 top-1/2 -translate-y-1/2 text-[#777777] text-xs pointer-events-none z-10">
                  →
                </span>
              )}
            </div>
          ))}
        </div>
      </section>

      {/* SECTION 7: BEGINNER PATHWAY */}
      <section className="rounded-md bg-white border border-[#d8d8d3] p-6 sm:p-10 flex flex-col md:flex-row items-center justify-between gap-8 shadow-sm">
        <div className="space-y-3 max-w-xl">
          <span className="text-xs font-mono text-[#ff5a1f] uppercase tracking-widest block">
            FIRST TIME CONTRIBUTOR?
          </span>
          <h2 className="text-2xl sm:text-3xl font-display font-bold text-[#111111] tracking-tight">
            Never opened a PR before? That's exactly what this challenge is for.
          </h2>
          <p className="text-sm text-[#555555] leading-relaxed">
            You don't need to be an open-source expert or a veteran engineer. You just need curiosity, basic git knowledge, and the willingness to learn by reading existing code.
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs text-[#555555] pt-2">
            <div className="flex items-center gap-2">
              <span className="text-[#3d5f58] font-bold">✓</span>
              <span>A GitHub account</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-[#3d5f58] font-bold">✓</span>
              <span>Willingness to read `CONTRIBUTING.md`</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-[#3d5f58] font-bold">✓</span>
              <span>Basic coding familiarity</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-[#3d5f58] font-bold">✓</span>
              <span>Patience with code reviews</span>
            </div>
          </div>
        </div>

        <div className="shrink-0 flex flex-col items-center gap-3">
          <Link
            to="/issues"
            className="px-6 py-3 rounded-[4px] bg-[#050505] hover:bg-[#1a1a1a] text-white font-semibold text-sm transition-all shadow-sm"
          >
            Show me beginner issues →
          </Link>
          <span className="text-[11px] font-mono text-[#777777]">Filtered by: good first issue</span>
        </div>
      </section>

      {/* SECTION 8: LIVE METRICS & FEATURED ISSUES */}
      <section className="space-y-8">
        {/* Live Metrics Grid */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 sm:gap-6">
          <div className="bg-white border border-[#d8d8d3] rounded-md p-5 text-center space-y-1 shadow-sm">
            <span className="text-2xl sm:text-3xl font-display font-extrabold text-[#111111] font-mono block">
              1,500+
            </span>
            <span className="text-xs text-[#777777] font-mono uppercase tracking-wider block">
              Curated Issues
            </span>
          </div>

          <div className="bg-white border border-[#d8d8d3] rounded-md p-5 text-center space-y-1 shadow-sm">
            <span className="text-2xl sm:text-3xl font-display font-extrabold text-[#111111] font-mono block">
              {stats?.participants?.total ? stats.participants.total : '100+'}
            </span>
            <span className="text-xs text-[#777777] font-mono uppercase tracking-wider block">
              Active Participants
            </span>
          </div>

          <div className="bg-white border border-[#d8d8d3] rounded-md p-5 text-center space-y-1 shadow-sm">
            <span className="text-2xl sm:text-3xl font-display font-extrabold text-[#111111] font-mono block">
              {stats?.pull_requests?.merged !== undefined ? stats.pull_requests.merged : '120+'}
            </span>
            <span className="text-xs text-[#777777] font-mono uppercase tracking-wider block">
              Merged PRs
            </span>
          </div>

          <div className="bg-white border border-[#d8d8d3] rounded-md p-5 text-center space-y-1 shadow-sm">
            <span className="text-2xl sm:text-3xl font-display font-extrabold text-[#ff5a1f] font-mono block">
              {stats?.points?.total_awarded !== undefined
                ? `${stats.points.total_awarded.toLocaleString()} pts`
                : '18,500 pts'}
            </span>
            <span className="text-xs text-[#777777] font-mono uppercase tracking-wider block">
              Points Awarded
            </span>
          </div>
        </div>

        {/* Curated Featured Issues */}
        {featuredIssues.length > 0 && (
          <div className="space-y-6 pt-4">
            <div className="flex items-center justify-between">
              <div>
                <span className="text-xs font-mono text-[#ff5a1f] uppercase tracking-widest block">
                  PROJECT DIRECTORY
                </span>
                <h2 className="text-2xl font-display font-bold text-[#111111] tracking-tight">
                  Featured Contribution Issues
                </h2>
              </div>
              <Link
                to="/issues"
                className="text-xs sm:text-sm text-[#ff5a1f] hover:text-[#ff8a3d] font-semibold flex items-center gap-1 transition-colors"
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
                  className="group bg-white hover:bg-[#fafaf8] border border-[#d8d8d3] hover:border-[#111111] rounded-md p-5 transition-all shadow-sm flex flex-col justify-between gap-4"
                >
                  <div className="space-y-2">
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-xs font-mono text-[#555555]">
                        {issue.project} #{issue.github_number}
                      </span>
                      <div className="flex items-center gap-1.5">
                        <span className="px-2.5 py-0.5 rounded-full text-[10px] font-mono uppercase bg-[#f4f4f1] border border-[#d8d8d3] text-[#555555]">
                          {issue.difficulty}
                        </span>
                        <span className="px-2.5 py-0.5 rounded-full text-[10px] font-mono font-bold bg-orange-50 border border-orange-200 text-[#ff5a1f]">
                          {issue.points} pts
                        </span>
                      </div>
                    </div>
                    <h3 className="text-base font-bold text-[#111111] group-hover:text-[#ff5a1f] transition-colors line-clamp-1">
                      {issue.title}
                    </h3>
                  </div>

                  <div className="flex items-center justify-between text-xs text-[#777777] pt-2 border-t border-[#d8d8d3]">
                    <span className="capitalize">{issue.category || 'General'}</span>
                    <span className="text-[#555555] group-hover:text-[#111111] group-hover:translate-x-0.5 transition-all">
                      View Issue Details →
                    </span>
                  </div>
                </Link>
              ))}
            </div>
          </div>
        )}
      </section>

      {/* SECTION: FINAL CALL TO ACTION */}
      <section className="rounded-lg bg-white border border-[#d8d8d3] p-8 sm:p-14 text-center space-y-6 shadow-sm relative overflow-hidden">
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_50%_0%,rgba(255,90,31,0.06),transparent_70%)] pointer-events-none" />

        <div className="relative space-y-3 max-w-xl mx-auto">
          <span className="text-xs font-mono text-[#ff5a1f] uppercase tracking-widest">
            GET READY
          </span>
          <h2 className="text-3xl sm:text-4xl font-display font-extrabold text-[#111111] tracking-tight">
            Your next commit could count.
          </h2>
          <p className="text-sm text-[#555555] leading-relaxed">
            Find a project. Make something better. Leave your mark on open source.
          </p>
        </div>

        <div className="relative pt-2 flex flex-col sm:flex-row items-center justify-center gap-3.5">
          <a
            href={getGitHubLoginUrl('/profile')}
            className="w-full sm:w-auto inline-flex items-center justify-center gap-2 px-8 py-3.5 rounded-[4px] bg-[#050505] hover:bg-[#1a1a1a] text-white font-semibold text-sm shadow-sm hover:scale-[1.01] active:scale-[0.99] transition-all"
          >
            <span>Register for CommitRush →</span>
          </a>
          <Link
            to="/projects"
            className="w-full sm:w-auto inline-flex items-center justify-center gap-2 px-7 py-3.5 rounded-[4px] bg-transparent hover:bg-black/5 text-[#050505] font-medium text-sm border border-[#050505] transition-colors"
          >
            Explore Projects
          </Link>
        </div>
      </section>
    </div>
  );
}
