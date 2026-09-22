# CommitRush 2026 — UI/UX Redesign Implementation Plan

Based on the design master specification at `/home/charlieputh/Music/design.md`.

## Core Philosophy
- **Identity:** Ink (`#08090B`, `#0D0F12`, `#121419`), Paper (`#FAFAF8`), and Commit Red (`#F12B40`).
- **Anti-AI-Slop:** Zero neon glows, zero terminal greens, zero cyber/matrix aesthetics, zero purple-cyan gradients.
- **Rhythm & Air:** Generous whitespace, 20px rounded surfaces, pill buttons, Space Grotesk display typography + Inter body + JetBrains Mono technical labels.
- **Test Integrity:** Maintain 100% compatibility with Vitest test suite (all 92 tests passing).

# CommitRush 2026 — UI/UX Redesign Implementation Plan

Based on the design master specification at `/home/charlieputh/Music/design.md`.

## Core Philosophy
- **Identity:** Ink (`#08090B`, `#0D0F12`, `#121419`), Paper (`#FAFAF8`), and Commit Red (`#F12B40`).
- **Anti-AI-Slop:** Zero neon glows, zero terminal greens, zero cyber/matrix aesthetics, zero purple-cyan gradients.
- **Rhythm & Air:** Generous whitespace, 20px rounded surfaces (`rounded-[20px]`), pill buttons (`rounded-full`), Space Grotesk display typography + Inter body + JetBrains Mono technical labels.
- **Test Integrity:** 100% test passing rate across all 20 test files (92 tests passed).

## Implementation Status (Completed)

### Phase 1: Foundation & Tokens (Complete)
- Configured Google Fonts in `frontend/index.html` (Space Grotesk, Inter, JetBrains Mono).
- Defined design tokens, CSS variables, and utility classes in `frontend/src/index.css` via Tailwind CSS v4 `@theme`.

### Phase 2: Shell, Navigation & Footer (Complete)
- Redesigned `frontend/src/components/Layout.tsx` with Space Grotesk wordmark, transparent-to-ink sticky navbar, pill CTAs, and accessible mobile drawer with 44px touch targets.
- Redesigned footer to reflect HACKIT SGGSIE&T Nanded editorial format with quick links and copyright.
- Harmonized `ProfileMenu.tsx`, `EmptyState.tsx`, `ErrorState.tsx`, `Skeletons.tsx`, and `ContributionStatusBadge.tsx`.

### Phase 3: Master Homepage / LandingPage (Complete)
- Implemented editorial hero with wolf silhouette illustration + Git contribution thread.
- Kickoff announcement & live countdown (22 Sep 2026 · A4 Hall · SGGSIE&T, Nanded).
- Event snapshot & "Why CommitRush?" 3 editorial pillars.
- 4-step "How CommitRush Works" lifecycle.
- 8-step Contribution Journey pipeline ("From issue to impact").
- Beginner-friendly path ("Never opened a PR before?").
- Live metrics & featured issues connected to Django backend API.
- Anti-spam quote moment ("PR count is not the whole story").
- Reward tiers & FAQ accordion sections.
- Final CTA banner ("Your next commit could count.").

### Phase 4: Sub-pages and Shared Components Theme Harmonization (Complete)
- Redesigned `IssuesExplorerPage.tsx` and `ProjectsExplorerPage.tsx`.
- Redesigned `LeaderboardPage.tsx`, `ProjectDetailPage.tsx`, `IssueDetailPage.tsx`, and `StatsPage.tsx`.
- Redesigned `DashboardPage.tsx`, `MyProfilePage.tsx`, and `PublicProfilePage.tsx`.
- Redesigned `MyContributionsPage.tsx`, `ContributionDetailPage.tsx`, and `NotFoundPage.tsx`.

### Phase 5: Verification & Testing (Complete)
- **Vitest Suite:** 20 test files passed (92/92 tests passed).
- **TypeScript & Vite Build:** `npm run build` (`tsc -b && vite build`) built cleanly in 1.02s with zero errors.
- **Backend & Frontend Servers:** Running locally at `http://localhost:5173` (Vite) and `http://127.0.0.1:8000` (Django).

