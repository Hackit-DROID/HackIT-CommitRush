# HackIT: CommitRush — Product Requirements Document

**Status:** Draft for 10-day build
**Audience:** Engineering team (backend, frontend, infra), event admins
**Scale target:** 500 participants, 300 concurrent requests, 67 repos, ~1,500 issues

---

## 1. Executive Summary

CommitRush is an event orchestration layer sitting on top of GitHub for a college open-source contribution event. GitHub remains the system of record for code, issues, PRs, reviews, and merges. CommitRush owns everything GitHub doesn't: participant identity, issue/project discovery, contribution tracking, validation, daily limits, points, leaderboard, and administration.

The single hardest constraint is time: 10 days to a production-ready launch, serving up to 300 concurrent users with bursts of simultaneous PR/merge activity. The architecture is therefore built around one rule — **no user-facing request synchronously touches GitHub or the merge bot.** Everything the user sees comes from PostgreSQL (optionally via Redis cache); everything that talks to GitHub happens in Celery workers, decoupled from the request/response cycle.

This document specifies one production release — no MVP1/2/3 — with P0/P1/P2 priority tags so the team can cut scope under time pressure without breaking correctness.

---

## 2. Problem Statement

Running an open-source contribution event at this scale on manual tracking (spreadsheets, Discord, honor system) doesn't work: it can't validate that a PR is real, can't rate-limit farming, can't produce a trustworthy leaderboard, and collapses under bursty traffic (everyone submits near the deadline). GitHub itself has no event/points concept and no admin console suited to running a competition. CommitRush needs to close that gap without trying to re-implement GitHub, and without introducing infrastructure the team can't stand up and stabilize in 10 days.

---

## 3. Product Vision

"Find an issue. Make a contribution. Get it merged. Climb the board."

CommitRush is a thin, reliable, correctness-first coordination layer. It wins not by having the most features but by never losing a contribution, never double-awarding points, and staying browsable even when GitHub, the merge bot, or the queue is having a bad day.

---

## 4. Goals

| # | Goal | Priority |
|---|---|---|
| G1 | Participants can discover projects/issues without hitting GitHub directly | P0 |
| G2 | PR/merge activity on GitHub is reliably captured via webhooks | P0 |
| G3 | Contributions move through a durable, idempotent state machine | P0 |
| G4 | Points are awarded exactly once per credited contribution | P0 |
| G5 | Merge processing is concurrency-capped and queued, not fire-and-forget | P0 |
| G6 | Daily contribution/point limits are race-condition safe | P0 |
| G7 | Leaderboard is fast, cached, and consistent | P0 |
| G8 | Admins have emergency controls (pause/resume/freeze) | P0 |
| G9 | System degrades gracefully when GitHub/Redis/DB/workers fail | P0 |
| G10 | Site stays usable (read paths) even when background processing lags | P0 |
| G11 | Full audit trail for points and admin actions | P1 |
| G12 | Event statistics dashboard | P1 |
| G13 | Daily/weekly leaderboard views | P2 |

---

## 5. Non-Goals

CommitRush will **not** build, for launch:

- Custom Git hosting or an in-browser code editor
- Internal chat/messaging platform
- A social network (feeds, follows, comments)
- A full replacement for GitHub's PR/review UI
- Complex ML-based fraud/AI-detection
- A native mobile application
- Kubernetes, microservices, GraphQL, or Kafka
- Elaborate badge/achievement/gamification systems
- Multi-tenant support for future events (design should not *preclude* it, but won't be built now)

These exist to protect the 10-day window. Anything not listed as P0/P1 below defaults to out-of-scope for launch.

---

## 6. Users & Personas

| Persona | Description | Primary needs |
|---|---|---|
| Participant | Student, GitHub account, competing for points | Discover issues, track own progress, trust the leaderboard |
| Project Maintainer (internal) | HackIT member who curated a repo | Not a distinct system role for launch — admins manage this via Django Admin |
| Event Admin | HackIT organizers | Configure event, monitor pipeline, resolve disputes, emergency controls |
| Spectator (unauthenticated) | Anyone viewing the event | See landing page, public leaderboard, stats |

---

## 7. User Journeys

**Primary journey (participant):**
1. Lands on homepage → understands concept → logs in with GitHub OAuth.
2. Browses Projects Explorer or Issue Explorer, filters by language/difficulty/points.
3. Opens an issue on CommitRush → clicks through to GitHub → comments/gets assigned → works on it.
4. Opens a PR on GitHub referencing the issue.
5. GitHub webhook fires → CommitRush creates/updates a `Contribution` record in `PENDING`.
6. Celery validates the PR (references a tracked issue, correct repo, not self-merge fraud, etc.) → `VALIDATING` → `APPROVED`/`REJECTED`.
7. Approved contributions enter the merge queue → bounded worker pool processes them → `MERGING` → on GitHub-confirmed merge, `MERGED`.
8. Points awarded transactionally, subject to daily limits. Leaderboard updates (cached, near-real-time).
9. Participant checks Dashboard: rank, points, in-progress contributions, daily usage.

**Admin journey:** monitor queue depth/health on an admin dashboard, intervene on flagged contributions, adjust event config (limits, concurrency), pause pipeline stages during incidents, resume, review audit log.

**Degraded-mode journey:** GitHub is down → participant can still browse projects/issues/leaderboard/dashboard (all DB-backed) but sees a banner: "GitHub sync is delayed — recent PR activity may take longer to appear."

---

## 8. Functional Requirements

Grouped by area, each with priority.

### 8.1 Identity & Auth
| Req | Priority |
|---|---|
| GitHub OAuth login (no manual username entry) | P0 |
| Store GitHub user id, username, avatar, email (if granted) | P0 |
| Session-based auth for the SPA (DRF session or token, see §19) | P0 |
| Logout | P0 |
| Handle revoked OAuth grant (re-auth prompt, don't hard-fail) | P0 |
| Account merge/duplicate GitHub id prevention | P0 |

### 8.2 Discovery
| Req | Priority |
|---|---|
| Project list with search/filter (language, status) | P0 |
| Project detail (metadata, issue count, contribution activity) | P0 |
| Issue list with search/filter (repo, difficulty, category, points, status, language) + sort (points, newest) | P0 |
| Server-side pagination (never load all 1,500 issues client-side) | P0 |
| Issue detail page, links out to canonical GitHub issue | P0 |
| Relevance/activity sort | P2 |

### 8.3 Contribution Tracking
| Req | Priority |
|---|---|
| Webhook ingestion for `pull_request` and `issues` events | P0 |
| Idempotent contribution creation/update from webhook | P0 |
| Contribution state machine (§11) | P0 |
| Participant-visible contribution status | P0 |
| Periodic reconciliation sync (catch missed webhooks) | P0 |

### 8.4 Merge Queue
| Req | Priority |
|---|---|
| Bounded-concurrency merge processing (configurable 5–10) | P0 |
| Durable, recoverable queue | P0 |
| Retry with backoff on transient failure | P0 |
| Admin pause/resume | P0 |
| Priority: merge queue processed ahead of analytics/notifications | P0 |

### 8.5 Points & Limits
| Req | Priority |
|---|---|
| Per-issue configurable point value | P0 |
| Transactional, race-safe point award | P0 |
| Configurable daily contribution limit & daily point cap | P0 |
| Over-limit contributions still recorded/validated, points deferred | P0 |
| Admin manual point adjustment with audit trail | P1 |

### 8.6 Leaderboard & Stats
| Req | Priority |
|---|---|
| Global leaderboard (points, merged count, tie-break rule) | P0 |
| Cached leaderboard, short TTL refresh | P0 |
| Participant's own rank visible even off top page | P0 |
| Leaderboard freeze (event end) | P0 |
| Aggregate event stats (participants, PRs, merges, points) | P1 |
| Top projects / top languages stats | P2 |
| Daily/weekly leaderboard views | P2 |

### 8.7 Admin
| Req | Priority |
|---|---|
| Django Admin for Participants/Projects/Issues/Contributions | P0 |
| Event config panel (limits, concurrency, pause switches) | P0 |
| Emergency controls (§10.6) | P0 |
| GitHub repo sync trigger (manual) | P0 |
| Suspicious activity view / suspend participant | P1 |

---

## 9. Information Architecture

**Public / unauthenticated:**
- `/` — Landing page
- `/leaderboard` — Public leaderboard
- `/projects` — Projects Explorer
- `/projects/:slug` — Project detail
- `/issues` — Issue Explorer
- `/issues/:id` — Issue detail
- `/profile/:username` — Public contributor profile
- `/stats` — Event statistics

**Authenticated:**
- `/dashboard` — Participant dashboard
- `/login`, `/auth/callback` — OAuth flow

**Admin:** Django Admin at `/admin/` (not the React app) + a small custom "Ops" panel for emergency controls if time allows (P1), otherwise emergency controls live in Django Admin actions (P0 fallback).

---

## 10. System Architecture

### 10.1 Core principle

> **No user-facing request should synchronously depend on a slow or failure-prone external operation.**

Concretely:

```
BAD:   User → Django → GitHub API → Merge bot → wait → DB → Response
GOOD:  User → DRF → PostgreSQL → Response                     (fast path)
       Celery → GitHub API → validation/merge bot → DB → status update   (async path)
```

**Why this matters for CommitRush specifically:**
- GitHub API latency/rate limits are out of our control; a spike of 300 concurrent participants cannot be allowed to turn into 300 concurrent GitHub API calls blocking Gunicorn workers.
- The merge bot is the single most failure-prone component (third-party API, bot account, branch protections, conflicts). If any request path calls it synchronously, one bot hiccup takes down page loads.
- Webhooks are inherently async and can arrive in bursts (GitHub redelivers, participants push multiple commits) — they must be absorbed by a queue, not processed inline in the webhook view.
- Decoupling means the frontend is always backed by Postgres reads, so the site "feels up" even mid-incident.

### 10.2 High-level component diagram (textual)

```
[React SPA] --HTTPS--> [Cloudflare] --> [Gunicorn/Django+DRF] --> [PostgreSQL]
                                              |                        ^
                                              v                        |
                                         [Redis: cache + broker]       |
                                              |                        |
                                        [Celery workers, multiple queues]
                                              |                        |
                                              v                        |
                                    [GitHub REST API] [Merge bot] -----+
                                              ^
                                              |
              [GitHub] --webhook--> [Django webhook endpoint] --enqueue--> [Redis]
```

### 10.3 Why this stack is sufficient (no infra escalation)

500 users / 300 concurrent requests / 1,500 issues is a small-to-medium Django workload. A single well-tuned Postgres instance, Redis instance, and a handful of Gunicorn + Celery processes comfortably handle this. Kubernetes/microservices/Kafka would add deployment risk and learning-curve cost with zero benefit at this scale — explicitly rejected per constraints.

### 10.4 Synchronous vs asynchronous operation classification

| Operation | Sync/Async | Rationale |
|---|---|---|
| Fetch issue list/detail | Sync (DB read) | Data lives in Postgres |
| Fetch project list/detail | Sync (DB read) | Data lives in Postgres |
| Fetch leaderboard | Sync (Redis cache → DB fallback) | Must be fast under load |
| Fetch dashboard | Sync (DB read) | Data lives in Postgres |
| Login/OAuth callback | Sync (one GitHub call, unavoidable, low volume) | Only happens once per session, not per page load |
| Webhook receipt | Sync ack + async processing | Must return 200 fast so GitHub doesn't retry-storm |
| Contribution validation | Async (Celery) | May call GitHub API |
| Merge processing | Async (Celery, bounded concurrency) | Calls merge bot/GitHub |
| GitHub repo/issue sync | Async (Celery, scheduled + manual trigger) | Bulk GitHub API usage |
| Notifications | Async (Celery, low priority) | Non-critical |
| Analytics/stat rollups | Async (Celery, low priority, scheduled) | Non-critical, can lag |

---

## 11. Contribution State Machine

### 11.1 States

| State | Meaning | Credited? |
|---|---|---|
| `PENDING` | Webhook received, PR seen, not yet validated | No |
| `QUEUED` | Passed initial checks, waiting for validation worker | No |
| `UNDER_REVIEW` | Being validated (rule checks) | No |
| `VALIDATING` | Alias/sub-state of under_review used during automated checks — kept for clarity in status UI | No |
| `APPROVED` | Passed validation, eligible for merge queue | No |
| `MERGING` | In merge queue / actively being processed by merge worker | No |
| `MERGED` | GitHub confirms PR merged | **Yes** |
| `REJECTED` | Failed validation or disqualified | No |
| `FLAGGED` | Held for admin review (suspicious pattern) | No (until admin resolves) |
| `RETRY` | Transient failure, will be reprocessed | No |

> Note: To keep the implementation simple, `VALIDATING` is implemented as the same DB state as `UNDER_REVIEW` with a `sub_status` field, rather than a fully separate state, to avoid combinatorial transition bugs. This is an explicit simplification — flag if product wants them visually distinct (they can share one backend state and just differ in a UI label driven by a `checks_completed` counter).

### 11.2 Transition table

| From | To | Trigger | Automatic? |
|---|---|---|---|
| — | `PENDING` | Webhook: PR opened/synchronized referencing tracked issue | Auto |
| `PENDING` | `QUEUED` | Passed cheap pre-checks (repo tracked, issue tracked, not duplicate) | Auto |
| `PENDING` | `REJECTED` | Failed pre-checks (untracked repo/issue) | Auto |
| `QUEUED` | `UNDER_REVIEW` | Validation worker picks it up | Auto |
| `UNDER_REVIEW` | `APPROVED` | Rule checks pass (see §21) | Auto |
| `UNDER_REVIEW` | `REJECTED` | Rule checks fail (e.g., self-issue, trivial diff below threshold if enabled) | Auto |
| `UNDER_REVIEW` | `FLAGGED` | Suspicious pattern detected (e.g., near-identical PRs across issues) | Auto (flag), manual (resolve) |
| `UNDER_REVIEW` | `RETRY` | GitHub API error / timeout during validation | Auto |
| `RETRY` | `UNDER_REVIEW` | Retry succeeds (bounded retry count) | Auto |
| `RETRY` | `FLAGGED` | Retry count exceeded | Auto |
| `APPROVED` | `MERGING` | Merge worker capacity available | Auto |
| `MERGING` | `MERGED` | GitHub confirms merged=true (webhook or reconciliation) | Auto |
| `MERGING` | `RETRY` | Merge bot/GitHub transient failure | Auto |
| `MERGING` | `REJECTED` | GitHub reports PR closed without merge | Auto |
| `FLAGGED` | `APPROVED` / `REJECTED` | Admin decision | Manual |
| `REJECTED` | `UNDER_REVIEW` | Admin override (rare) | Manual |
| Any | `REJECTED` | Admin manual reject | Manual |

**Worker crash mid-processing:** contributions in `UNDER_REVIEW`/`MERGING` carry a `locked_at`/`worker_heartbeat` timestamp; a periodic sweep task requeues anything stuck past a timeout (e.g., 10 minutes) back to its prior queued state. This is the recovery mechanism — no contribution is silently lost because state lives in Postgres, not in worker memory.

**Reversibility:** `MERGED` is terminal for points purposes but not immutable — an admin can revoke points via a `PointTransaction` reversal (audit-logged) if a merge is later found fraudulent (e.g., reverted on GitHub). The `Contribution` row itself is never deleted.

**Credited state:** only `MERGED` awards points, and only up to the daily cap (see §14).

---

## 12. Queue & Background Processing Architecture

### 12.1 Queues (Celery, Redis broker)

| Queue | Purpose | Priority | Concurrency |
|---|---|---|---|
| `webhooks` | Parse/normalize incoming webhook payloads into Contribution rows | High | Moderate (e.g., 4–8 workers) |
| `validation` | Run rule checks on `QUEUED` contributions | High | Moderate |
| `merge` | Drive merge bot / merge-confirmation calls | **Highest** | **Capped 5–10, admin-configurable** |
| `sync` | GitHub repo/issue reconciliation | Low | Low (1–2) |
| `notifications` | Non-critical user-facing notices (if any) | Lowest | Low |
| `analytics` | Stat rollups, leaderboard cache warm | Low | Low |

Separate queues isolate failure domains: a merge-bot outage floods retries only in `merge`, never starving `webhooks` intake, so incoming PR events keep being captured even if merging is paused.

### 12.2 Merge concurrency control

Implemented via a Celery queue consumed by a **fixed-size worker pool bound to the `merge` queue only** (e.g., `celery -A commitrush worker -Q merge -c 8 --max-tasks-per-child=50`), with the concurrency number (`MERGE_CONCURRENCY`) stored in `EventConfig` and used to size the pool at deploy/restart time. For true dynamic (no-restart) adjustment, gate actual merge-bot invocation behind a **Redis semaphore** (`INCR`/`DECR` with TTL) sized from `EventConfig.merge_concurrency`, so admins can change the number live without redeploying workers.

Example: 300 `APPROVED` contributions exist. The semaphore admits at most N (5–10) into active merge-bot calls; the rest sit in `APPROVED` state, visibly "Queued" to the user, and are pulled in FIFO (with priority override, see below) as slots free up.

### 12.3 Priority within the merge queue

FIFO by default (`approved_at` ascending), with an optional priority boost field (`is_priority`) admins can set per-contribution for edge cases (e.g., re-processing after a false rejection). No complex scoring — deterministic and explainable.

### 12.4 Retry policy

| Failure type | Retry strategy |
|---|---|
| GitHub API 5xx / timeout | Exponential backoff, max 5 attempts, then → `RETRY` state visible to admin |
| GitHub API rate-limited (403/429) | Backoff respecting `Retry-After`/reset header, requeue, not counted against attempt budget |
| Merge bot failure (conflict, branch protection) | 1 retry after delay, then → `FLAGGED` for admin (likely needs human: real merge conflict) |
| Worker crash | Heartbeat sweep requeues after timeout (§11) |
| Duplicate task (same contribution enqueued twice) | Idempotency key = `contribution_id`; Celery task acquires a Redis lock per contribution before processing |

### 12.5 User-facing statuses

Directly map DB `status` to UI copy: Pending, Queued, Under Review, Validating, Approved, Merging, Merged, Rejected, Flagged, Retry — each with a one-line explanation (see §22).

### 12.6 Admin monitoring & emergency pause/resume

Admin panel (Django Admin custom view or lightweight React "Ops" page, P1) shows: queue depth per queue, oldest queued item age, failed job count, merge semaphore current usage/limit, last webhook received timestamp. Pause toggles (`EventConfig.merge_paused`, `.validation_paused`, `.submissions_paused`) are checked at the top of each Celery task — when true, tasks re-queue themselves (with delay) instead of processing, and the webhook endpoint still accepts and stores events but does not enqueue validation when `submissions_paused` is set (still returns 200 to GitHub, stores raw payload for later replay).

---

## 13. GitHub Integration

### 13.1 OAuth
Standard GitHub OAuth App flow. Scopes: minimum needed to read user profile (`read:user`) — no `repo` write scope needed from participants since CommitRush never pushes on their behalf. Store `github_id` (immutable, primary identity key), `username` (mutable, refreshed on login), `avatar_url`, `email` (optional).

### 13.2 Webhooks
CommitRush registers webhooks on each tracked repo (or a single GitHub App/org-level webhook if repos are under one org — **assumption, confirm with team**, see §29) for: `pull_request` (opened, synchronize, closed, edited), `issues` (opened, closed, labeled, edited) . Endpoint verifies `X-Hub-Signature-256` HMAC against a stored webhook secret before processing (see §18). Handler does minimal work synchronously: verify signature → store raw payload with GitHub delivery ID → enqueue `webhooks` task → return 200 immediately (<200ms). All parsing/business logic happens in the async task.

### 13.3 Events consumed

| GitHub event | Action | 
|---|---|
| `pull_request.opened` | Create/update `Contribution` (PENDING) if references tracked issue |
| `pull_request.synchronize` | Update contribution's commit SHA / re-trigger validation if already validated |
| `pull_request.closed` (merged=true) | Transition → MERGED, trigger point award |
| `pull_request.closed` (merged=false) | Transition → REJECTED (closed without merge) |
| `issues.closed` | Mark local `Issue.status` closed, disable further submissions against it |
| `issues.labeled`/`edited` | Update local `Issue` metadata cache |

### 13.4 Reconciliation (fallback for missed/lost webhooks)
Scheduled Celery beat task every N minutes (configurable, e.g., 15) pulls recent PR/issue activity per tracked repo via REST API for repos with no webhook activity in the window, and a slower full-repo reconciliation nightly. This is the safety net for "Webhook delayed/lost" (§20).

### 13.5 What's stored locally vs canonical on GitHub

| Data | Canonical source | Cached locally? |
|---|---|---|
| Issue title/body/labels | GitHub | Yes, synced |
| PR status, merged flag | GitHub | Yes, synced |
| Repo metadata | GitHub | Yes, synced |
| Contribution lifecycle, points, event rules | **CommitRush (Postgres)** | N/A — this is the source of truth |
| User GitHub identity | GitHub | Yes, cached at login |

### 13.6 Rate limiting
Track remaining rate limit from response headers; when below a safety threshold (e.g., 10%), Celery tasks that call GitHub back off automatically and non-critical sync tasks (analytics, nightly reconciliation) are deprioritized. Webhook ingestion never calls GitHub synchronously, so rate limits never block the user-facing site.

---

## 14. Points & Daily Limit System

### 14.1 Point assignment
Each `Issue` has an explicit `points` integer field, admin-configurable (example tiers: Beginner 50 / Intermediate 100 / Advanced 200 — defaults only, fully overridable per issue).

### 14.2 When points are awarded
Only on transition into `MERGED`. Never for `REJECTED`, `FLAGGED`, or intermediate states.

### 14.3 Daily limit policy (core requirement)

**Policy:** the daily limit caps **credited throughput**, not participation.

- A merged PR is **always recorded** as a `Contribution` and its state machine completes normally.
- If the participant has **not** hit `max_contributions_per_day` or `max_points_per_day`: points are awarded normally.
- If the participant **has** hit either limit: the `Contribution` still reaches `MERGED`, but its associated `PointTransaction` is created with `status=DEFERRED` and `points_awarded=0`. The UI clearly shows: *"Merged! Points deferred — daily limit reached. Resets at [time]."*
- Deferred points are **not** automatically granted the next day (avoids retroactive leaderboard jumps and keeps the rule simple) — this is a product decision to confirm (§29 open question: alternative is "banked and released next day," which is more generous but adds complexity/exploit surface).

**Why this policy:** rejecting a legitimate merged PR outright is bad UX and discourages real contribution; capping only the *points* (not the record) preserves fairness against farming while keeping the contribution history honest and complete.

### 14.4 Race-condition safety
Point award happens inside a single DB transaction that:
1. `SELECT ... FOR UPDATE` on the participant's `DailyContributionUsage` row for today (or `INSERT ... ON CONFLICT DO NOTHING` to create it first).
2. Checks current count/points against configured caps.
3. If under cap: increments usage, creates `PointTransaction(status=AWARDED)`, updates `Participant.total_points` (or relies on a derived/aggregated value — see §16 tradeoff).
4. If at/over cap: creates `PointTransaction(status=DEFERRED, points=0)`.
5. Commits atomically.

Row-level locking on the per-participant-per-day usage row (not a global lock) means concurrent contributions from *different* participants never block each other; only a single participant's own simultaneous merges serialize against each other, which is correct and cheap at this scale.

### 14.5 Admin overrides
Admins can manually create a `PointTransaction` (positive or negative) with a required `reason` field — always audit-logged (§8, `AuditLog`).

---

## 15. Database Model

All entities live in PostgreSQL, the authoritative application database.

| Entity | Purpose | Key fields | Relationships | Unique constraints / indexes |
|---|---|---|---|---|
| `Participant` | Extends Django `User` w/ event profile | `github_id` (unique), `github_username`, `avatar_url`, `is_suspended`, `total_points` (denormalized, recomputed by trigger/signal) | 1:1 with `User` | unique(`github_id`) |
| `Project` | Tracked repository | `github_repo_id` (unique), `owner`, `name`, `full_name`, `language`, `is_enabled`, `description` | 1:N `Issue` | unique(`github_repo_id`), index(`is_enabled`) |
| `Issue` | Tracked GitHub issue | `github_issue_id` (unique), `project_id`, `number`, `title`, `points`, `difficulty`, `category`, `status` (open/closed/disabled), `is_featured` | FK `Project`; M:N `IssueLabel` | unique(`github_issue_id`), index(`project_id, status`), index(`points`), index(`difficulty`) |
| `IssueLabel` | GitHub label cache | `name`, `color` | M:N `Issue` | unique(`name`) |
| `PullRequest` | GitHub PR cache | `github_pr_id` (unique), `repo_id`, `number`, `author_github_id`, `merged`, `merged_at`, `head_sha` | FK `Project`, FK `Participant` (nullable if author not registered) | unique(`github_pr_id`) |
| `Contribution` | **Core entity** — CommitRush's view of a PR-against-tracked-issue | `participant_id`, `issue_id`, `pull_request_id`, `status`, `sub_status`, `locked_at`, `retry_count`, `flagged_reason`, `approved_at`, `merged_at`, `created_at`, `updated_at` | FK `Participant`, FK `Issue`, FK `PullRequest` | **unique(`participant_id`, `pull_request_id`)** — prevents duplicate contribution rows per PR; index(`status`); index(`issue_id`) |
| `PointTransaction` | Immutable ledger of point events | `contribution_id`, `participant_id`, `points`, `status` (AWARDED/DEFERRED/REVOKED/ADMIN_ADJUST), `reason`, `created_at` | FK `Contribution` (nullable for admin adjustments), FK `Participant` | **unique(`contribution_id`)** where status=AWARDED — enforces one award per contribution; index(`participant_id, created_at`) |
| `DailyContributionUsage` | Per-participant-per-day counters | `participant_id`, `date`, `contributions_count`, `points_count` | FK `Participant` | **unique(`participant_id`, `date`)** |
| `EventConfig` | Singleton runtime config | `merge_concurrency`, `max_contributions_per_day`, `max_points_per_day`, `merge_paused`, `validation_paused`, `submissions_paused`, `leaderboard_frozen`, `event_status` | — | singleton (enforced in app logic or `pk=1`) |
| `WebhookEvent` | Idempotency + audit log for inbound webhooks | `delivery_id` (GitHub's `X-GitHub-Delivery`, unique), `event_type`, `payload` (JSONB), `processed_at`, `processing_error` | — | **unique(`delivery_id`)** — this is the primary dedup key |
| `AuditLog` | Admin/system action trail | `actor` (nullable=system), `action`, `target_type`, `target_id`, `details` (JSONB), `created_at` | — | index(`target_type, target_id`) |

**Leaderboard query note:** `Participant.total_points` is a denormalized counter updated transactionally alongside `PointTransaction` inserts (in the same DB transaction), so leaderboard reads are a simple indexed `ORDER BY total_points DESC` rather than an expensive `SUM()` aggregate join at read time. Index: `(total_points DESC, merged_count DESC)` composite for tie-break ordering.

**Idempotency keys used across the system:** `github_id` (participant), `github_repo_id` (project), `github_issue_id` (issue), `github_pr_id` (PR), `delivery_id` (webhook), `(participant_id, pull_request_id)` (contribution), `contribution_id` (point award).

---

## 16. API Specification

Base: `/api/v1/`. DRF, session auth for the SPA + CSRF for unsafe methods; webhook endpoint uses signature auth (no session).

| Group | Method | Endpoint | Auth | Purpose |
|---|---|---|---|---|
| Auth | GET | `/auth/github/login/` | Public | Redirect to GitHub OAuth |
| Auth | GET | `/auth/github/callback/` | Public | Handle OAuth callback, create session |
| Auth | POST | `/auth/logout/` | Session | Destroy session |
| Auth | GET | `/auth/me/` | Session | Current user identity |
| Projects | GET | `/projects/` | Public | Paginated list, filters: `search`, `language`, `enabled` |
| Projects | GET | `/projects/{slug}/` | Public | Project detail + issue counts |
| Issues | GET | `/issues/` | Public | Paginated list; filters: `project`, `language`, `difficulty`, `category`, `points_min/max`, `status`; sort: `points`, `newest` |
| Issues | GET | `/issues/{id}/` | Public | Issue detail |
| Contributions | GET | `/contributions/mine/` | Session | Participant's own contribution history + statuses |
| Contributions | GET | `/contributions/{id}/` | Session (owner or admin) | Single contribution detail/status |
| Dashboard | GET | `/dashboard/` | Session | Rank, points, daily usage, in-progress, recent activity — single aggregated endpoint to minimize round trips |
| Leaderboard | GET | `/leaderboard/` | Public | Paginated, cached; includes requester's own rank if authenticated (`?include_me=true`) |
| Profile | GET | `/profile/{username}/` | Public | Public contributor profile |
| Stats | GET | `/stats/` | Public | Aggregate event stats (cached, refreshed by Celery beat) |
| Webhooks | POST | `/webhooks/github/` | HMAC signature | GitHub webhook receiver |
| Admin | * | (Django Admin, not DRF) | Staff session | See §18 |

**Example — GET `/issues/`**
Request: `?project=owner-repo&difficulty=beginner&points_min=50&sort=-points&page=2`
Response (200):
```json
{
  "count": 1500,
  "next": ".../issues/?page=3&...",
  "previous": ".../issues/?page=1&...",
  "results": [
    {"id": 1042, "title": "...", "project": "owner/repo", "github_number": 88,
     "points": 100, "difficulty": "intermediate", "category": "backend",
     "status": "open", "github_url": "https://github.com/owner/repo/issues/88"}
  ]
}
```
Errors: `400` invalid filter values, `429` if rate-limited.

**Example — POST `/webhooks/github/`**
Auth: `X-Hub-Signature-256` verified against stored secret. Response: `200` immediately after signature check + enqueue (target <200ms). `401` on bad signature. Duplicate `X-GitHub-Delivery` → `200` (no-op, already recorded) — GitHub must never see an error for a legitimate redelivery.

**Design principle:** favor a few well-shaped, aggregated endpoints (e.g., single `/dashboard/`) over many chatty small ones, given the TanStack Query frontend and the need to keep request volume manageable under burst load.

---

## 17. Frontend Architecture

**Stack:** React + TypeScript + Vite + Tailwind + React Router + TanStack Query.

**Routing:** matches Information Architecture (§9). Auth-gated routes wrapped in a `RequireAuth` guard that redirects to `/login` preserving intended destination.

**API layer:** a single typed `apiClient` (fetch wrapper) with TanStack Query hooks per resource (`useIssues`, `useProjects`, `useLeaderboard`, `useDashboard`, `useContribution`). Query keys include filter/pagination params for correct caching. Stale time tuned per resource: leaderboard/stats can be stale up to their cache TTL (§20); dashboard/contribution status polled on a short interval (e.g., 15–30s) only while a contribution is in a non-terminal state, to reflect queue progress without hammering the API.

**Loading/empty/error states:** every list view has explicit skeleton loading, empty state ("No issues match your filters"), and error state (retry button) — required for all of Issue Explorer, Projects Explorer, Leaderboard, Dashboard.

**Resilience requirement:** the SPA must render fully from cached/DB-backed API responses even when GitHub sync or the merge queue is paused/delayed — no component should block on live GitHub data. A global "Service status" banner (fed by `/stats/` or a lightweight `/status/` endpoint) surfaces degraded-mode notices (e.g., "Merge processing temporarily paused by admins").

**No optimistic updates** for contribution status changes (state is admin/worker-driven, not user-driven) — the one place optimistic UI is safe/useful is trivial local UI state (filter selections, pagination), not anything touching points or contribution status.

---

## 18. Admin System

Django Admin is the primary admin surface — minimizes custom UI work within 10 days.

| Area | Capabilities |
|---|---|
| Participants | Search by username/github_id, view profile/points/contributions, suspend (`is_suspended=True` blocks new point awards, contribution still recorded), view flagged activity |
| Projects | Add/remove repo, enable/disable, manual "Sync now" admin action, edit metadata |
| Issues | Manual "Sync from GitHub" action, edit points/difficulty/category, enable/disable, feature/unfeature, mark invalid (excludes from discovery, existing contributions unaffected) |
| Contributions | Filter by status/participant/issue/project, view full state history (via `AuditLog` + timestamps), admin actions: **Retry**, **Flag**, **Reject**, **Manually Approve**, **Force-transition to Merged** (rare, audited) |
| EventConfig | Single editable row: event status, daily limits, merge concurrency, retry limits, submission availability, leaderboard freeze |
| AuditLog | Read-only, searchable by actor/target |

### Emergency controls (P0) — and why each exists

| Control | Why |
|---|---|
| Pause merge processing | Merge bot misbehaving/GitHub incident — stop making it worse without losing queued work |
| Pause contribution validation | Suspected bad validation logic deployed — freeze before it mass-rejects/mass-flags |
| Pause point awarding | Suspected scoring bug — stop the ledger from getting worse while investigating |
| Disable new submissions | Hard incident / end of event — stop accepting new webhooks-as-contributions (still records raw webhook for later replay) |
| Freeze leaderboard | Event end — lock final standings while post-event point disputes are resolved |
| Resume operations | Return to normal after incident — must be explicit, not automatic, so a human confirms the fix |

All pause flags live on the `EventConfig` singleton and are read at the top of the relevant Celery task/view — no restart required to take effect (Celery tasks re-check on each poll/attempt).

---

## 19. Security Requirements

| Area | Requirement |
|---|---|
| GitHub OAuth | Standard Authorization Code flow, `state` param CSRF protection, secrets in env vars / secret manager, never in repo |
| Session/token | Django session auth, `Secure`, `HttpOnly`, `SameSite=Lax` cookies; session expiry reasonable for event duration |
| API auth | DRF `SessionAuthentication` for SPA; CSRF token required on unsafe methods from browser |
| CORS | Restrict to the deployed frontend origin only |
| Webhook signature | Mandatory `X-Hub-Signature-256` HMAC verification against a per-app secret before any processing; reject with 401 on mismatch |
| Secret management | GitHub OAuth secret, webhook secret, merge bot token stored in environment/secret manager, not DB, not source; DB stores only what's needed (no raw OAuth access tokens persisted beyond session unless required for API calls — if required, encrypt at rest) |
| Rate limiting | DRF throttling on public list endpoints (`issues`, `projects`, `leaderboard`) per-IP and per-user; webhook endpoint excluded from user-based limits but protected by signature check + Cloudflare |
| Input validation | All filter/query params validated via DRF serializers; no raw SQL |
| SQL injection | Django ORM exclusively; no raw string-interpolated queries |
| XSS | React escapes by default; issue titles/descriptions from GitHub rendered as text, not raw HTML, unless explicitly sanitized (if markdown rendering is added, use a sanitizing renderer) |
| Authorization | Object-level checks: a participant can only see their own full contribution detail (public profile shows only aggregate/safe fields); admin actions require `is_staff` |
| Admin authorization | Django Admin behind `is_staff`/`is_superuser`; consider IP allowlist via Cloudflare for `/admin/` if time permits (P1) |
| Audit logs | All admin actions and point adjustments logged to `AuditLog` |
| Abuse prevention | See §21 |

---

## 20. Performance & Scalability

**Design targets** (not guarantees, but engineering budgets):

| Path | Target |
|---|---|
| GET `/issues/`, `/projects/` | p95 < 300ms |
| GET `/leaderboard/` (cached) | p95 < 150ms |
| GET `/dashboard/` | p95 < 400ms |
| Webhook ack | p95 < 200ms |
| Merge queue throughput | 5–10 concurrent, admin-adjustable |

**Key mechanisms:**
- **Database indexing:** all filter/sort columns on `Issue` (project, status, points, difficulty), `Contribution` (status, participant_id, issue_id), `PointTransaction` (participant_id), leaderboard composite index on `Participant(total_points DESC, merged_count DESC)`.
- **Connection pooling:** `pgbouncer` or Django's persistent connections (`CONN_MAX_AGE`) sized for Gunicorn worker count; managed Postgres connection limits sized for expected worker+Celery concurrency.
- **Redis caching:** leaderboard (TTL ~30–60s, invalidated/refreshed on point award via Celery task rather than every read recomputing), stats (`/stats/` TTL ~60s), issue/project list responses can use short cache for identical filter combos if load testing shows need (P1).
- **Static assets / SPA:** served via Cloudflare CDN; Vite production build, hashed assets, long cache headers.
- **Rate limiting:** DRF throttle classes tuned to allow legitimate browsing bursts (e.g., 100 req/min/user) while blocking abuse.
- **Pagination:** default page size ~20–50 for issues/projects; never an unbounded list endpoint.
- **GitHub API usage:** batched where possible (GraphQL-free, REST is fine at this scale), reconciliation sync paginated and rate-aware (§13.6).

**Likely bottlenecks to watch:** (1) leaderboard read amplification right before deadline — mitigated by caching; (2) webhook burst when many PRs merge near deadline — mitigated by queue separation and merge concurrency cap; (3) Postgres write contention on `DailyContributionUsage`/`Participant.total_points` — mitigated by per-row locking scoped to a single participant, not a global lock.

---

## 21. Reliability & Failure Handling

### 21.1 Graceful degradation by dependency

| Dependency down | Behavior |
|---|---|
| **GitHub** | Website (browsing, dashboard, leaderboard) fully functional from Postgres. New webhooks can't arrive (GitHub itself is down) but nothing is lost — GitHub retries deliveries on its side, and reconciliation catches up once it's back. Status banner shown if sync lag exceeds threshold. |
| **Merge bot** | Contributions pile up in `APPROVED` (visibly "Queued for merge") — no data loss, no incorrect points. Once bot recovers, queue drains at configured concurrency. |
| **Redis** | Cache misses fall back to DB reads (slower but correct) for leaderboard/stats. **Celery broker down means async processing halts** — webhook endpoint still accepts and durably stores raw payloads (in Postgres `WebhookEvent`, written directly, not just enqueued) so nothing is lost; processing resumes once Redis recovers via a reconciliation sweep of unprocessed `WebhookEvent` rows. |
| **PostgreSQL (temporary)** | Requests fail fast with 503 rather than hanging; Gunicorn health check reflects DB status; Celery tasks retry with backoff rather than crash-looping. No partial writes — all point-award logic is transactional (§14.4), so a mid-transaction DB failure rolls back cleanly, never a half-applied award. |
| **Celery worker failure** | Heartbeat/lock timeout sweep (§11) requeues stuck contributions; other workers/queues unaffected due to queue isolation (§12.1). |
| **High traffic** | Gunicorn worker count + Cloudflare caching absorb read load; DRF throttling sheds excess; queue-based processing means write-side load turns into queue depth, not request failures. |
| **GitHub API rate limiting** | Async tasks back off per remaining-limit headers (§13.6); user-facing site unaffected since it never calls GitHub synchronously. |

### 21.2 Practical availability targets
No claim of "zero downtime." Target: core read paths (browsing, dashboard, leaderboard) available ≥99% of the event window; background processing (validation/merge) may lag under incident conditions but must fully recover (no data loss) within the retry/reconciliation windows defined above. Admin-declared maintenance windows are acceptable and should be communicated via the status banner.

---

## 22. Abuse & Fairness

Deterministic rules + admin review — no ML fraud detection within 10 days.

| Abuse vector | Mitigation |
|---|---|
| Multiple GitHub accounts | Out of scope to fully prevent (can't verify real-world identity); admins can manually flag/merge cases if reported |
| Duplicate PRs for same issue | `Contribution` unique on `(participant_id, pull_request_id)`; only the first `MERGED` PR against a given issue by a given participant is credited — a second PR to the same issue by the same person is recorded but not separately pointed unless admin overrides |
| Trivial/low-effort changes | Not automatically detected (no LOC-diff scoring for launch — explicit non-goal); rely on project maintainers' own PR review standards on GitHub plus admin spot-review of `FLAGGED` items |
| Repeated contributions to same issue (churn) | Same as duplicate PR handling above |
| Self-created issues (farming) | Validation rule: reject/flag if `Issue.created_by_github_id == Contribution.participant.github_id` (only enforceable for issues CommitRush itself tracks metadata on) |
| Artificial/collusive merges | Admin review of `FLAGGED` items; repo maintainers retain full control on GitHub side (branch protections, required reviews) — CommitRush inherits whatever rigor the repo enforces |
| Race-condition daily-limit bypass | Prevented structurally via row-level DB locking (§14.4) |
| Webhook replay/duplication | Prevented via `WebhookEvent.delivery_id` uniqueness (§13.2, §16) |

---

## 23. Observability

| Domain | Signals |
|---|---|
| Application | Error rate, API p50/p95/p99 latency, 4xx/5xx rate, request volume — via Sentry + Cloudflare/Gunicorn logs |
| Database | Active connections, slow query log, CPU/storage (via managed Postgres dashboard) |
| Queue | Depth per queue, processing time, failed job count, retry count, oldest queued item age (custom Celery/Redis metrics, surfaced in admin ops view) |
| GitHub | API failure count, rate-limit remaining, webhook delivery failures (GitHub's own webhook delivery log + our `WebhookEvent.processing_error`) |
| Merge bot | Success/failure rate, processing latency, active concurrent jobs (semaphore value) |
| Event | Participants count, contributions by status, merges/hour, points awarded/hour — feeds `/stats/` |

**Tooling:** Sentry for error tracking (backend + frontend), an uptime monitor (e.g., simple external pinger) against `/health/` and the SPA root, Cloudflare analytics for traffic. A `/health/` endpoint checks DB and Redis connectivity and returns 200/503 accordingly, used by both uptime monitoring and load balancer health checks.

---

## 24. Testing Strategy

| Category | Coverage |
|---|---|
| **Unit** | Point award transaction logic (incl. concurrent-award simulation), daily limit boundary conditions, state machine transition validity, webhook payload validation, permission checks |
| **Integration** | End-to-end webhook → Contribution → validation → merge → points flow (mocked GitHub/merge bot); Celery task retry behavior; DB transaction rollback on simulated mid-transaction failure |
| **Load** | 100 → 200 → 300 concurrent read-heavy users against issues/leaderboard/dashboard; burst of 300 simultaneous webhook deliveries; burst of 300 contributions reaching `APPROVED` simultaneously — verify merge concurrency stays capped at configured value and no crashes/5xx spikes occur |
| **Failure/chaos** | Kill a Celery worker mid-task → verify requeue via heartbeat sweep; stop Redis → verify webhook payloads still persist and site read paths still work; simulate GitHub 500s/429s → verify backoff and no user-facing impact; send duplicate webhook deliveries (same `delivery_id`) → verify no duplicate points; simulate two simultaneous merge webhooks for the same participant at their daily limit boundary → verify exactly the correct number get credited |
| **Security** | Auth bypass attempts, webhook signature tampering (must reject), rate-limit enforcement, basic injection/XSS payloads through filter params and any user-editable text fields, admin-only endpoint access as non-staff user |

**Acceptance criteria are measurable**, e.g.: "300 concurrent contributions reaching APPROVED simultaneously result in exactly `merge_concurrency` active merge-bot calls at any instant, verified via semaphore metric during load test" and "Sending the same webhook delivery 5 times results in exactly one `PointTransaction(status=AWARDED)` row."

---

## 25. Deployment Architecture

- **Frontend:** static build (Vite) served via Cloudflare (Pages or CDN in front of a static host).
- **Backend:** Gunicorn behind Cloudflare (proxying to origin), sized with enough workers for 300 concurrent short-lived DB-backed requests (e.g., start with `workers = 2*CPU+1`, tune after load test).
- **Celery:** separate worker processes per queue group at minimum: one pool for `merge` (concurrency = `MERGE_CONCURRENCY`), one shared pool for `webhooks`+`validation` (higher concurrency, these are fast), one small pool for `sync`+`notifications`+`analytics`. Celery beat for scheduled reconciliation/stat rollups.
- **Database:** managed PostgreSQL (automated backups, point-in-time recovery if available on the plan — confirm with hosting choice).
- **Redis:** managed Redis, used both as Celery broker and cache (single instance acceptable at this scale; separate broker/cache instances are a P2 nice-to-have, not required).
- **Monitoring:** Sentry (backend + frontend DSNs), uptime monitor hitting `/health/`.
- **Secrets:** environment variables via the hosting platform's secret manager — GitHub OAuth client secret, webhook secret, merge bot token, `SECRET_KEY`, DB/Redis URLs.

---

## 26. 10-Day Implementation Plan

Critical path is: **Auth → Data model → GitHub sync (read side) → Issue/Project APIs+UI → Webhook ingestion → State machine → Points/limits → Merge queue → Leaderboard → Admin/emergency controls → Load & failure testing → Deploy.** Frontend UI for a given resource can't start meaningfully until its API contract is stable, so backend model/API for a resource should land 0.5–1 day ahead of its frontend.

| Day | Focus | Key deliverables | Depends on |
|---|---|---|---|
| 1 | Project setup, data model, auth | Django/DRF/React scaffolding, Postgres schema (§15) migrated, GitHub OAuth login working end-to-end, `EventConfig`/`WebhookEvent`/`AuditLog` tables in place | — |
| 2 | GitHub sync (read side) | Management command + Celery task to bulk-import 67 repos / 1,500 issues into `Project`/`Issue`; rate-limit-aware pagination | Day 1 |
| 3 | Core read APIs + Issue/Project Explorer UI | `/projects/`, `/issues/` (filters, pagination), frontend list/detail pages wired via TanStack Query | Day 2 |
| 4 | Webhook ingestion | `/webhooks/github/` endpoint w/ signature verification, `WebhookEvent` dedup, `webhooks` queue task creating/updating `Contribution` rows in PENDING/QUEUED | Day 1 |
| 5 | Contribution state machine + validation | Validation Celery task (rule checks §21), state transitions PENDING→...→APPROVED/REJECTED/FLAGGED, contribution status API + basic dashboard UI | Day 4 |
| 6 | Merge queue + points | Redis-semaphore-bound merge worker, MERGING→MERGED transition + reconciliation for merge confirmation, transactional point award + daily limit logic (§14) | Day 5 |
| 7 | Leaderboard + dashboard + profile | Leaderboard API+cache, full Dashboard aggregation endpoint+UI, public profile page, event stats endpoint (basic) | Day 6 |
| 8 | Admin system + emergency controls | Django Admin customization for all entities, `EventConfig` panel, pause/resume flags wired into all relevant tasks/views, audit logging on admin actions | Day 6/7 |
| 9 | Load testing, failure testing, hardening | Run load test scenarios (§24), chaos tests (kill worker, stop Redis, duplicate webhooks), fix issues found, security pass (rate limits, auth checks, signature verification) | Days 1–8 complete |
| 10 | Deployment, final reconciliation sync, buffer | Production deploy, DNS/Cloudflare config, Sentry/uptime wired, full 67-repo/1,500-issue production sync, smoke test full user journey end-to-end, buffer for fires | Day 9 |

**Explicit dependency risk:** Days 4–6 (webhook → validation → merge → points) are the true critical path and the hardest to compress — if anything slips, it should slip *into* Day 9's buffer, not into cutting merge-concurrency control or idempotency (those are P0 correctness, not polish). If time runs short, cut P2 items first (daily/weekly leaderboard views, top-projects stats, custom ops React panel — fall back to Django Admin for ops) before touching state machine or idempotency work.

---

## 27. Risks & Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| 10-day timeline slips on core pipeline (Days 4–6) | Launch delayed or ships with correctness bugs | Treat P0 items as non-negotiable; cut P1/P2 first; daily standup checkpoint against this plan |
| GitHub webhook delivery gaps (network blips, GitHub-side issues) | Contributions missed | Reconciliation sync as safety net (§13.4) |
| Merge bot instability (third-party dependency, not fully specified in this PRD) | Contributions stuck in MERGING | Retry + FLAGGED fallback to admin; contributions never lost, only delayed |
| Traffic spike right before deadline | Site slowness/errors | Queue-based write path + Cloudflare caching on read path + load test before launch |
| Daily-limit race condition undetected until live | Leaderboard unfair/inflated | Explicit concurrent-write unit test + load test scenario (§24) |
| Single Postgres instance is a single point of failure | Full outage if DB down | Managed Postgres w/ backups; accept this risk at this scale/budget rather than building HA within 10 days — call out explicitly to stakeholders |
| Ambiguity on webhook registration (per-repo vs org-level/GitHub App) | Could block Day 4 work | Resolve in Day 1 (see Open Questions §29) |
| Scope creep from stakeholders during event | Timeline risk | This PRD's Non-Goals (§5) is the enforcement mechanism — any new ask gets a "post-launch" answer by default |

---

## 28. Launch Acceptance Criteria

- [ ] A participant can authenticate through GitHub OAuth without manually entering a username.
- [ ] A participant can browse all ~67 projects and ~1,500 issues with working search/filter/sort and server-side pagination.
- [ ] Every issue detail links to its canonical GitHub issue.
- [ ] Opening a PR on GitHub against a tracked issue results in a `Contribution` row appearing within the reconciliation/webhook window.
- [ ] Duplicate webhook deliveries (same `delivery_id`) never create duplicate `Contribution` or `PointTransaction` rows.
- [ ] 300 simultaneous contributions reaching `APPROVED` do not trigger more than `MERGE_CONCURRENCY` (5–10) simultaneous merge-bot calls, verified under load test.
- [ ] Two simultaneous merge events for a participant at their daily limit boundary award points to only the correct number.
- [ ] A merged contribution correctly updates participant points and leaderboard rank within the cache refresh window.
- [ ] The leaderboard remains internally consistent (no participant's rank order contradicts their points) under concurrent load.
- [ ] An admin can pause merge processing, validation, and new submissions independently, and resume each independently.
- [ ] Simulated GitHub outage does not prevent browsing, dashboard, or leaderboard access.
- [ ] Simulated Redis outage does not lose webhook payloads (verified they land in `WebhookEvent` and reprocess once Redis returns).
- [ ] Simulated Celery worker crash mid-task results in the affected contribution being requeued, not stuck, within the heartbeat timeout window.
- [ ] Rate limiting is active on public list endpoints and the webhook endpoint rejects unsigned/incorrectly-signed requests with 401.
- [ ] Sentry captures backend and frontend errors; uptime monitor is live against `/health/`.
- [ ] Load test at 300 concurrent users against read paths meets the p95 targets in §20 without 5xx spikes.
- [ ] Full production GitHub sync (67 repos, ~1,500 issues) completes successfully before go-live.

---

## 29. Open Questions / Decisions Required

1. **Webhook registration model:** are all 67 repos under a single GitHub org (allowing one org-level webhook) or scattered across many accounts (requiring per-repo webhook registration, more setup work)? Blocks Day 1/4 planning — resolve immediately.
2. **Merge bot specification:** this PRD assumes an existing/available "merge bot" (per the prompt) but its actual interface (a GitHub Action, a bot account with a PAT, a third-party service?) isn't defined. Backend team needs this contract by Day 5 at the latest.
3. **Deferred points policy:** confirmed as "not banked, points lost if over daily cap" (§14.3) — confirm this is acceptable to event organizers vs. a "banked, released next day" alternative.
4. **OAuth scope for email:** do we need participant email (for notifications) or is GitHub username/avatar sufficient? Affects OAuth scope request and whether `notifications` queue does anything meaningful at launch (currently P2/low-priority regardless).
5. **Trivial-diff / low-effort PR detection:** explicitly out of scope for launch (§21) — confirm organizers are fine relying on repo maintainer review standards alone.
6. **Custom Ops React panel vs. Django Admin only** for emergency controls: this PRD defaults to Django Admin (P0) with a nicer custom panel as P1 — confirm whether Django Admin's UX is acceptable to the admin team during a live incident.
7. **Data retention/post-event:** does CommitRush need to support a "final frozen" export (CSV of final leaderboard/points) for prize distribution? Not currently scoped — likely a quick addition, should be confirmed and slotted into Day 9/10 buffer if needed.

---

## P0 Critical Path (must work for launch)

1. GitHub OAuth login (no manual username entry).
2. Project/Issue discovery with filter/search/pagination, backed entirely by Postgres.
3. Signature-verified, idempotent GitHub webhook ingestion (`WebhookEvent.delivery_id` uniqueness).
4. Contribution state machine (§11) with worker-crash recovery via heartbeat sweep.
5. Bounded-concurrency merge queue (5–10, admin-configurable) via Redis semaphore.
6. Transactional, race-safe point award with per-participant daily contribution/point limits (§14.4).
7. Merged-but-over-limit contributions still recorded; points deferred, not rejected.
8. Cached, consistent leaderboard with participant's own rank always visible.
9. Admin emergency controls: pause/resume merge, validation, submissions; freeze leaderboard.
10. Reconciliation sync as fallback for missed webhooks.
11. Full graceful degradation: site stays browsable if GitHub, merge bot, or Redis is down; no user-facing request ever synchronously calls GitHub or the merge bot.
12. Full audit trail on point transactions and admin actions.
13. Load-tested at 300 concurrent users / 300 simultaneous contribution events before go-live.
