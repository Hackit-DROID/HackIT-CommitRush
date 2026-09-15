# CommitRush --- Internal Development Plan (`plan.md`)

**Source of truth:** `PRD.md` (all section references `§N` below refer
to it). **Purpose:** Transform the PRD into an ordered, checkpointed,
executable SDLC plan for a 10-day build. This document does not restate
PRD rationale --- it tells an executor *what to build, in what order,
and how to know each stage is done*. **Consumers:** this plan is
designed to be machine-referenced later by `Context.md` (state
tracking), `.dev/awsmap.md` (agent/skill assignment), and `Continue.md`
(execution driver). Module IDs (`M1`--`M10`) and Task IDs (`M#-T#`) are
stable and should not be renumbered.

------------------------------------------------------------------------

## 1. Project-Level Execution Strategy

1.  **Backend-first, strictly.** No module builds substantial frontend
    UI until the API contract it depends on is stable. Per §26, backend
    model/API for a resource should land 0.5--1 day ahead of its
    frontend. Frontend tasks are listed *inside* the module that owns
    their backing API, not as a parallel track.
2.  **No user-facing request synchronously touches GitHub or the merge
    bot** (§10.1). Every module that adds a user-facing endpoint must
    confirm this invariant holds before its checkpoint is considered
    met.
3.  **Follow the PRD's critical path exactly** (§26): Auth → Data model
    → GitHub read-side sync → Project/Issue APIs+UI → Webhook ingestion
    → Contribution state machine + validation → Merge queue + points →
    Leaderboard/dashboard/profile → Admin/emergency controls →
    Load/failure/security testing → Deployment/final reconciliation.
    This plan's 10 modules map 1:1 to this sequence and to the PRD's Day
    1--10 table (§26).
4.  **P0 is non-negotiable.** If the 10-day window is threatened, cut
    P1/P2 items first (see §5 of this plan). Do not compress Days 4--6
    (webhook → validation → merge → points) --- per PRD this is the true
    critical path and schedule slip should land in Day 9's buffer, not
    here.
5.  **Testing is not deferred entirely to the end.** Unit tests for a
    module's core logic (state transitions, race conditions,
    idempotency) should be written as that module is built. Module 9 is
    a *dedicated hardening pass* (load, chaos, security) --- it assumes
    unit/integration coverage already exists from earlier modules, not
    that testing starts there.
6.  **Traceability:** every task cites the PRD section(s) it derives
    from. If a task has no citation, it should not exist.

------------------------------------------------------------------------

## 2. Module Overview

  -------------------------------------------------------------------------------
  ID             Module             PRD Day        Depends On     Priority Tier
  -------------- ------------------ -------------- -------------- ---------------
  M1             Project Setup,     1              ---            P0
                 Data Model & Auth                                

  M2             GitHub Read-Side   2              M1             P0
                 Sync                                             

  M3             Core Read APIs +   3              M1, M2         P0 (P2:
                 Issue/Project                                    relevance sort)
                 Explorer UI                                      

  M4             Webhook Ingestion  4              M1             P0
                                                   (functional:   
                                                   M2)            

  M5             Contribution State 5              M4             P0
                 Machine +                                        
                 Validation                                       

  M6             Merge Queue +      6              M5             P0 (P1: admin
                 Points                                           point
                                                                  adjustment)

  M7             Leaderboard +      7              M6, M3         P0 (P1: stats;
                 Dashboard +                                      P2:
                 Profile                                          top-projects,
                                                                  daily/weekly
                                                                  views)

  M8             Admin System +     8 (buffers     M5, M6, M1     P0 (P1: custom
                 Emergency Controls into 7)                       Ops panel)

  M9             Load, Failure &    9              M1--M8         P0
                 Security Testing                  complete       

  M10            Deployment + Final 10             M9             P0
                 Reconciliation +                                 
                 Buffer                                           
  -------------------------------------------------------------------------------

------------------------------------------------------------------------

## 3. Modules, Tasks, Dependencies, Checkpoints

### M1 --- Project Setup, Data Model & Auth

**Objective:** Stand up the scaffolding, the full schema, and a working
GitHub OAuth login. Nothing later can start without this. **PRD refs:**
§8.1, §10, §13.1, §15, §16 (Auth group), §17, §18 (EventConfig), §23.

  -----------------------------------------------------------------------------------------------------------------------
  Task           Name               What to do                                  Depends on     Outcome
  -------------- ------------------ ------------------------------------------- -------------- --------------------------
  M1-T1          Backend/frontend   Django+DRF backend project;                 ---            Both apps boot locally.
                 scaffolding        React+TypeScript+Vite+Tailwind+React                       
                                    Router+TanStack Query frontend project                     
                                    (§17). No feature code yet --- structure                   
                                    only.                                                      

  M1-T2          Full Postgres      Migrate every entity in §15 exactly as      M1-T1          Schema matches §15
                 schema             specified: `Participant`, `Project`,                       field-for-field;
                                    `Issue`, `IssueLabel`, `PullRequest`,                      migrations run clean.
                                    `Contribution`, `PointTransaction`,                        
                                    `DailyContributionUsage`, `EventConfig`,                   
                                    `WebhookEvent`, `AuditLog` --- including                   
                                    every listed unique constraint and index                   
                                    (esp. `unique(github_id)`,                                 
                                    `unique(participant_id, pull_request_id)`                  
                                    on Contribution, `unique(delivery_id)` on                  
                                    WebhookEvent, `unique(contribution_id)`                    
                                    where status=AWARDED on PointTransaction).                 

  M1-T3          GitHub OAuth login Implement `/auth/github/login/`,            M1-T2          A user can log in via
                                    `/auth/github/callback/`, `/auth/logout/`,                 GitHub and get a session;
                                    `/auth/me/` (§16). Authorization Code flow                 `github_id` uniqueness
                                    with `state` CSRF param (§19). Session auth                enforced
                                    (`Secure`/`HttpOnly`/`SameSite=Lax`), no                   (account-merge/duplicate
                                    manual username entry. Store `github_id`                   prevention, §8.1).
                                    (immutable key), `github_username`,                        
                                    `avatar_url`, `email` (if granted). Scope:                 
                                    `read:user` only (§13.1) --- pending                       
                                    resolution of Open Question #4 on whether                  
                                    email scope is needed.                                     

  M1-T4          EventConfig        Create the singleton `EventConfig` row with M1-T2          Exactly one `EventConfig`
                 singleton          defaults for `merge_concurrency`,                          row exists and is
                 bootstrap          `max_contributions_per_day`,                               readable/writable via
                                    `max_points_per_day`, `merge_paused`,                      Django Admin.
                                    `validation_paused`, `submissions_paused`,                 
                                    `leaderboard_frozen`, `event_status` (§15,                 
                                    §18).                                                      

  M1-T5          `/health/`         Endpoint checks DB + Redis connectivity,    M1-T1          Health check reflects real
                 endpoint           returns 200/503 (§23).                                     dependency status; usable
                                                                                               by uptime monitor and load
                                                                                               balancer later.
  -----------------------------------------------------------------------------------------------------------------------

**Checkpoint (M1 done when):** - A participant can authenticate through
GitHub OAuth without manually entering a username (maps to §28
acceptance criterion 1). - All §15 tables exist with correct
constraints/indexes. - `EventConfig`, `WebhookEvent`, `AuditLog` tables
are in place and empty-but-ready. - `/health/` returns 200 in a healthy
local/staging environment.

**Decision flag:** Open Question #1 (webhook registration model:
org-level vs per-repo) should be resolved during this module per §29
("resolve immediately") even though it isn't formally consumed until M4
--- resolving it late risks blocking Day 4.

------------------------------------------------------------------------

### M2 --- GitHub Read-Side Sync

**Objective:** Populate `Project`/`Issue`/`IssueLabel` from real GitHub
data so later modules have something to serve. **PRD refs:** §13.5,
§13.6, §14.1, §15.

  ---------------------------------------------------------------------------------------
  Task           Name               What to do            Depends on     Outcome
  -------------- ------------------ --------------------- -------------- ----------------
  M2-T1          Project (repo)     Management command /  M1-T2          All tracked
                 bulk import        Celery task importing                repos present as
                                    all tracked repos                    `Project` rows.
                                    into `Project`                       
                                    (`github_repo_id`,                   
                                    `owner`, `name`,                     
                                    `full_name`,                         
                                    `language`,                          
                                    `is_enabled`,                        
                                    `description`).                      

  M2-T2          Issue bulk import  Paginated import of   M2-T1          Issues populated
                                    issues per repo into                 at target scale
                                    `Issue`                              (\~1,500 across
                                    (`github_issue_id`,                  \~67 repos, or
                                    `project_id`,                        representative
                                    `number`, `title`,                   subset in dev).
                                    `points`,                            
                                    `difficulty`,                        
                                    `category`, `status`,                
                                    `is_featured`). Apply                
                                    default point tiers                  
                                    per §14.1 (Beginner                  
                                    50/Intermediate                      
                                    100/Advanced 200)                    
                                    unless overridden.                   

  M2-T3          IssueLabel sync    Import/sync GitHub    M2-T2          Label data
                                    labels into                          available for
                                    `IssueLabel`, linked                 filtering later
                                    M:N to `Issue`.                      (M3).

  M2-T4          Rate-limit-aware   Wire the sync task    M2-T1, M2-T2   A full sync run
                 sync wiring        into the `sync`                      does not exhaust
                                    Celery queue;                        the GitHub rate
                                    implement backoff                    limit or crash
                                    based on remaining                   on pagination.
                                    rate-limit headers                   
                                    (§13.6) --- sync                     
                                    tasks deprioritize                   
                                    themselves under 10%                 
                                    remaining limit.                     
  ---------------------------------------------------------------------------------------

**Checkpoint (M2 done when):** Running the sync task against target
repos populates `Project`, `Issue`, `IssueLabel` correctly, with
pagination and rate-limit backoff verified (no unhandled failures).
Full-scale (67 repos/1,500 issues) production sync is *not* required
here --- that's M10-T6 --- but the mechanism must be proven correct at
whatever scale is available in dev/staging.

------------------------------------------------------------------------

### M3 --- Core Read APIs + Issue/Project Explorer UI

**Objective:** Let participants/spectators browse projects and issues
from Postgres --- no GitHub calls on this path. **PRD refs:** §8.2, §16
(Projects/Issues groups), §17, §19 (rate limiting), §20.

  -------------------------------------------------------------------------------------------------------------
  Task           Name                  What to do                  Depends on     Outcome
  -------------- --------------------- --------------------------- -------------- -----------------------------
  M3-T1          `/projects/` list API Filters: `search`,          M1-T2, M2-T1   Endpoint returns correct
                                       `language`, `enabled`.                     filtered/paginated results.
                                       Paginated.                                 

  M3-T2          `/projects/{slug}/`   Metadata, issue count,      M3-T1          Detail view returns complete
                 detail API            contribution activity.                     project info.

  M3-T3          `/issues/` list API   Filters: `project`,         M1-T2, M2-T2   Matches the example
                                       `language`, `difficulty`,                  request/response shape in
                                       `category`,                                §16.
                                       `points_min/max`, `status`;                
                                       sort: `points`, `newest`.                  
                                       Server-side pagination ---                 
                                       never load all 1,500                       
                                       client-side.                               

  M3-T4          `/issues/{id}/`       Includes canonical GitHub   M3-T3          Detail view links out
                 detail API            issue URL.                                 correctly to GitHub.

  M3-T5          DRF throttling on     Rate limiting               M3-T1, M3-T3   Throttle rejects abusive
                 public endpoints      per-IP/per-user on                         request rates while allowing
                                       `issues`, `projects` list                  normal browsing (\~100
                                       endpoints (§19, §20).                      req/min/user budget).

  M3-T6          Issue/Project         `useIssues`/`useProjects`   M3-T1--M3-T4   Participant can
                 Explorer frontend     TanStack Query hooks;                      browse/filter/sort/paginate
                                       list + detail pages;                       through UI end-to-end.
                                       explicit skeleton loading,                 
                                       empty state,                               
                                       error-with-retry state                     
                                       (§17).                                     
  -------------------------------------------------------------------------------------------------------------

**Checkpoint (M3 done when):** A participant can browse all synced
projects and issues with working search/filter/sort and pagination (§28
criteria 2, 3); every issue detail links to its canonical GitHub issue.

**Deferred if time-constrained:** Relevance/activity sort (P2, §8.2).

------------------------------------------------------------------------

### M4 --- Webhook Ingestion

**Objective:** Reliably and idempotently capture GitHub PR/issue events
without ever blocking on GitHub. **PRD refs:** §10.1, §12.6, §13.2,
§13.3, §13.4, §15 (`WebhookEvent`), §16, §19.

  ----------------------------------------------------------------------------------------------------------------
  Task           Name                   What to do                            Depends on     Outcome
  -------------- ---------------------- ------------------------------------- -------------- ---------------------
  M4-T1          `/webhooks/github/`    Verify `X-Hub-Signature-256` HMAC     M1-T2          Endpoint acks fast;
                 endpoint               against stored secret → store raw                    rejects
                                        payload + `X-GitHub-Delivery` id in                  unsigned/mis-signed
                                        `WebhookEvent` → enqueue `webhooks`                  requests.
                                        task → return 200. Target \<200ms ack                
                                        (§13.2, §20). Reject with 401 on bad                 
                                        signature.                                           

  M4-T2          Delivery dedup         Enforce `WebhookEvent.delivery_id`    M4-T1          Same `delivery_id`
                                        uniqueness; duplicate delivery → 200                 sent N times never
                                        no-op (§13.2, §16).                                  creates duplicate
                                                                                             processing.

  M4-T3          `webhooks` queue       Parse payloads per the §13.3 event    M4-T1, M4-T2   Each event type
                 processing task        table:                                               produces the correct
                                        `pull_request.opened`→create/update                  DB effect.
                                        Contribution (PENDING) if it                         
                                        references a tracked issue;                          
                                        `pull_request.synchronize`→update                    
                                        commit SHA/re-trigger validation;                    
                                        `pull_request.closed`                                
                                        (merged=true)→MERGED path;                           
                                        `pull_request.closed`                                
                                        (merged=false)→REJECTED;                             
                                        `issues.closed`→mark local                           
                                        `Issue.status` closed;                               
                                        `issues.labeled`/`edited`→update                     
                                        local `Issue` cache.                                 

  M4-T4          Respect                When `EventConfig.submissions_paused` M4-T3, M1-T4   Pausing submissions
                 `submissions_paused`   is true, webhook still stores the raw                stops new
                                        payload and returns 200, but does not                Contribution creation
                                        enqueue validation (§12.6).                          without dropping
                                                                                             data.

  M4-T5          Reconciliation         Celery beat task (interval            M2-T1, M2-T2   Scheduled task runs
                 scaffold               configurable, e.g. 15 min) pulling                   and correctly catches
                                        recent PR/issue activity for repos                   a manually-simulated
                                        with no recent webhook activity;                     missed event in dev.
                                        nightly full-repo reconciliation                     
                                        (§13.4). Full verification of this                   
                                        happens in M9; here it just needs to                 
                                        exist and run correctly against the                  
                                        sync data from M2.                                   
  ----------------------------------------------------------------------------------------------------------------

**Checkpoint (M4 done when):** Opening a test PR against a tracked issue
produces a Contribution row within the expected window (§28 criterion
4); duplicate deliveries never duplicate rows (§28 criterion 5);
endpoint acks under 200ms and 401s bad signatures.

**Decision blocker:** Open Question #1 (webhook registration: org-level
single webhook vs per-repo registration) **must be resolved before this
module starts** --- it directly determines how M4-T1 is configured
against GitHub and was flagged in the PRD as blocking Day 4 planning.

**Functional note (not a formal PRD dependency, but required for
meaningful testing):** M4-T3's "references a tracked issue" logic needs
real `Issue` rows to test against --- i.e., M2 should be functionally
complete even though the PRD's Day-table lists M4's formal dependency as
M1 only.

------------------------------------------------------------------------

### M5 --- Contribution State Machine + Validation

**Objective:** Move Contributions automatically and correctly through
validation, with no state ever silently lost. **PRD refs:** §11 (full
state machine), §12.5, §16, §22.

  ---------------------------------------------------------------------------------------------------------------------------------------------
  Task           Name             What to do                                                            Depends on     Outcome
  -------------- ---------------- --------------------------------------------------------------------- -------------- ------------------------
  M5-T1          State transition Implement every transition in §11.2's table: PENDING→QUEUED (cheap    M4-T3          Every listed transition
                 implementation   pre-checks pass) / REJECTED (pre-checks fail); QUEUED→UNDER_REVIEW;                  is reachable and
                                  UNDER_REVIEW→APPROVED/REJECTED/FLAGGED/RETRY; RETRY→UNDER_REVIEW                     correctly gated.
                                  (bounded retries) or FLAGGED (retries exhausted);                                    
                                  FLAGGED→APPROVED/REJECTED (manual, admin); REJECTED→UNDER_REVIEW                     
                                  (manual override, rare). `VALIDATING` is implemented as                              
                                  `UNDER_REVIEW` + `sub_status`, not a separate DB state (§11.1 note).                 

  M5-T2          `validation`     Implement deterministic abuse rules from §22: self-created-issue      M5-T1          Validation task
                 queue rule       farming check                                                                        correctly
                 checks           (`Issue.created_by_github_id == Contribution.participant.github_id` →                approves/rejects/flags
                                  reject/flag); duplicate-PR-per-issue handling relies on the existing                 per these rules.
                                  `(participant_id, pull_request_id)` DB constraint (M1-T2) --- only                   
                                  first MERGED PR per issue per participant is credited. Explicitly                    
                                  **do not** build trivial-diff/LOC-diff detection (non-goal, §5, §22).                

  M5-T3          Worker crash     `locked_at`/`worker_heartbeat` timestamp on Contribution; periodic    M5-T1          A manually-killed
                 recovery sweep   sweep task requeues anything stuck in `UNDER_REVIEW`/`MERGING` past a                worker's stuck
                                  timeout (e.g. 10 min) back to its prior queued state (§11.2).                        contribution is requeued
                                                                                                                       within the timeout
                                                                                                                       window.

  M5-T4          Contribution     `/contributions/mine/` and `/contributions/{id}/` (owner-or-admin     M5-T1          Participant can query
                 status APIs      auth) (§16).                                                                         their own contribution
                                                                                                                       history/status;
                                                                                                                       object-level auth
                                                                                                                       enforced (§19).

  M5-T5          Status UI        Map DB status to the UI copy set (Pending/Queued/Under                M5-T4          Participant sees
                                  Review/Validating/Approved/Merging/Merged/Rejected/Flagged/Retry),                   accurate, current
                                  each with a one-line explanation (§12.5). No optimistic updates for                  contribution status in
                                  status changes (§17).                                                                the
                                                                                                                       dashboard/contribution
                                                                                                                       views.
  ---------------------------------------------------------------------------------------------------------------------------------------------

**Checkpoint (M5 done when):** A test PR against a tracked issue moves
automatically through PENDING→...→APPROVED/REJECTED/FLAGGED with no
manual intervention; a simulated worker crash mid-`UNDER_REVIEW` is
recovered by the heartbeat sweep; status is correctly visible via API
and UI.

------------------------------------------------------------------------

### M6 --- Merge Queue + Points

**Objective:** Process approved contributions through a
concurrency-capped merge pipeline and award points exactly once,
race-free. **PRD refs:** §11.2 (MERGING/MERGED), §12.1--§12.4, §14
(all), §16.

  --------------------------------------------------------------------------------------------------------------------------------
  Task           Name                      What to do                                          Depends on     Outcome
  -------------- ------------------------- --------------------------------------------------- -------------- --------------------
  M6-T1          Merge worker pool +       Fixed-size Celery worker pool bound to the `merge`  M5-T1, M1-T4   Semaphore correctly
                 semaphore                 queue only; concurrency gated by a **Redis                         admits at most N
                                           semaphore** sized from                                             concurrent merge-bot
                                           `EventConfig.merge_concurrency`, so admins can                     calls.
                                           adjust live without redeploy (§12.2).                              

  M6-T2          APPROVED→MERGING→MERGED   Drive transition on GitHub-confirmed merge (webhook M6-T1          Transitions match
                 transitions               or reconciliation); `MERGING`→`RETRY` on transient                 §11.2 exactly.
                                           failure; `MERGING`→`REJECTED` if GitHub reports                    
                                           closed-without-merge (§11.2, §13.3).                               

  M6-T3          FIFO ordering + priority  Process by `approved_at` ascending; optional        M6-T1          Order is
                 override                  `is_priority` field for admin-driven reprocessing                  deterministic and
                                           (§12.3).                                                           admin-explainable.

  M6-T4          Retry policy              GitHub 5xx/timeout: exponential backoff, max 5      M6-T2          Each failure class
                                           attempts → `RETRY` visible to admin. Rate-limited                  behaves per its
                                           (403/429): backoff on `Retry-After`, requeue                       specified strategy;
                                           without counting against attempt budget. Merge bot                 no double-processing
                                           failure (conflict/branch protection): 1 retry then                 of the same
                                           `FLAGGED`. Duplicate task: Redis lock keyed on                     contribution.
                                           `contribution_id` before processing (§12.4).                       

  M6-T5          Transactional point award Implement §14.4 exactly: `SELECT ... FOR UPDATE`    M6-T2          Concurrent merges
                                           (or `INSERT ... ON CONFLICT DO NOTHING`) on the                    for *different*
                                           participant's `DailyContributionUsage` row for                     participants never
                                           today; check against                                               block each other; a
                                           `max_contributions_per_day`/`max_points_per_day`;                  single participant's
                                           under cap → increment usage, create                                simultaneous merges
                                           `PointTransaction(status=AWARDED)`, update                         serialize correctly.
                                           `Participant.total_points`; at/over cap →                          
                                           `PointTransaction(status=DEFERRED, points=0)`;                     
                                           commit atomically. Row-level lock is                               
                                           per-participant-per-day, never global (§14.4).                     
                                           Deferred points are **not** auto-banked to next day                
                                           (§14.3) pending confirmation of Open Question #3.                  

  M6-T6 (P1)     Admin manual point        Admin-created `PointTransaction`                    M6-T5          Admin can adjust
                 adjustment                (positive/negative) with required `reason`,                        points with a
                                           audit-logged (§14.5). Defer if schedule is tight.                  mandatory audit
                                                                                                              trail.
  --------------------------------------------------------------------------------------------------------------------------------

**Checkpoint (M6 done when):** Under a simulated burst of concurrent
`APPROVED` contributions, active merge-bot calls never exceed configured
`MERGE_CONCURRENCY` (§28 criterion 6); two simultaneous merges for a
participant at their daily-limit boundary award points to exactly the
correct number (§28 criterion 7); over-limit merges still complete to
`MERGED` with `DEFERRED` points, never rejected outright (§14.3);
duplicate merge-confirmation webhooks never double-award.

**Decision blocker:** Open Question #2 (merge bot interface --- GitHub
Action / bot PAT / third-party service --- is not defined in the PRD)
must be resolved no later than the start of this module; the PRD states
the backend team needs this contract "by Day 5 at the latest."
**Decision flag (non-blocking):** Open Question #3 (deferred points:
lost vs. banked-next-day) --- build to the PRD's stated default
(lost/not banked) but flag for organizer confirmation before this
behavior is presented as final.

------------------------------------------------------------------------

### M7 --- Leaderboard + Dashboard + Profile

**Objective:** Give participants a fast, cached, trustworthy view of
standings and their own progress. **PRD refs:** §8.6, §12.6 (freeze),
§15 (leaderboard index), §16, §17, §20.

  ----------------------------------------------------------------------------------------------------------------
  Task           Name                     What to do                                 Depends on     Outcome
  -------------- ------------------------ ------------------------------------------ -------------- --------------
  M7-T1          `/leaderboard/` API      Paginated, Redis-cached (TTL \~30--60s,    M6-T5          Correct ranks
                                          refreshed on point award rather than every                and
                                          read), includes requester's own rank via                  tie-breaking
                                          `?include_me=true`. Tie-break via                         under load.
                                          composite index                                           
                                          `(total_points DESC, merged_count DESC)`                  
                                          (§8.6, §15, §16, §20).                                    

  M7-T2          Leaderboard freeze       Wire `EventConfig.leaderboard_frozen` to   M7-T1, M1-T4   Toggling
                                          lock standings on demand (§8.6, §18).                     freeze stops
                                                                                                    rank changes
                                                                                                    from
                                                                                                    propagating to
                                                                                                    the public
                                                                                                    view.

  M7-T3          `/dashboard/` aggregated Single endpoint: rank, points, daily       M6-T5, M5-T4   One round trip
                 API                      usage, in-progress contributions, recent                  serves the
                                          activity (§16).                                           full
                                                                                                    dashboard.

  M7-T4          `/profile/{username}/`   Public contributor profile, safe/aggregate M6-T5          Public profile
                 API                      fields only (§16, §19 object-level auth).                 renders
                                                                                                    without
                                                                                                    exposing
                                                                                                    private
                                                                                                    contribution
                                                                                                    detail.

  M7-T5 (P1)     `/stats/` API            Aggregate event stats (participants, PRs,  M6-T5          Stats endpoint
                                          merges, points), cached, refreshed by                     returns
                                          Celery beat (§8.6, §16, §23).                             current
                                                                                                    aggregates.

  M7-T6          Frontend: Leaderboard,   Wire via TanStack Query;                   M7-T1--M7-T5   Full UI
                 Dashboard, Profile,      dashboard/contribution status polled on a                 matches
                 Stats pages              short interval (15--30s) *only* while                     Information
                                          non-terminal; skeleton/empty/error states                 Architecture
                                          throughout (§17).                                         (§9).

  M7-T7          Service status banner    Global banner fed by `/stats/` or a        M7-T5 or a     Banner appears
                                          lightweight `/status/` endpoint, surfacing minimal status correctly when
                                          degraded-mode notices (e.g. "Merge         source         pause flags
                                          processing temporarily paused") (§17).                    are active or
                                                                                                    sync lag
                                                                                                    exceeds
                                                                                                    threshold.
  ----------------------------------------------------------------------------------------------------------------

**Checkpoint (M7 done when):** A merged contribution visibly updates
points and leaderboard rank within the cache refresh window (§28
criterion 8); leaderboard stays internally consistent under concurrent
load (§28 criterion 9); participant's own rank is visible even off the
top page.

**Deferred if time-constrained (in this order):** daily/weekly
leaderboard views (P2) → top-projects/top-languages stats (P2) →
`/stats/` aggregate dashboard (P1, but keep if feasible).

------------------------------------------------------------------------

### M8 --- Admin System + Emergency Controls

**Objective:** Give event admins full operational control, especially
the ability to pause/resume any pipeline stage instantly. **PRD refs:**
§18 (all), §12.6, §19 (admin auth), §29 Open Question #6.

  -------------------------------------------------------------------------------------------------------------------------------------------
  Task           Name                        What to do                                                        Depends on     Outcome
  -------------- --------------------------- ----------------------------------------------------------------- -------------- ---------------
  M8-T1          Participant/Project/Issue   Django Admin customization per §18's capability table:            M1--M2         All listed
                 admin                       participant search/suspend/flagged-activity view; project                        admin actions
                                             add/remove/enable/disable/manual sync-now; issue manual sync/edit                available and
                                             points-difficulty-category/enable-disable/feature/mark-invalid.                  functioning.

  M8-T2          Contribution admin          Filter by status/participant/issue/project; full state history    M5, M6         Admin can
                                             via `AuditLog`; actions: Retry, Flag, Reject, Manually Approve,                  intervene on
                                             Force-transition to Merged (rare, always audited) (§18).                         any
                                                                                                                              contribution
                                                                                                                              and the action
                                                                                                                              is audited.

  M8-T3          EventConfig admin panel     Single editable row: event status, daily limits, merge            M1-T4          Admin can
                                             concurrency, retry limits, submission availability, leaderboard                  change any
                                             freeze (§18).                                                                    runtime config
                                                                                                                              without a
                                                                                                                              deploy.

  M8-T4          AuditLog admin view         Read-only, searchable by actor/target (§18).                      M1-T2          Every
                                                                                                                              admin/system
                                                                                                                              action is
                                                                                                                              inspectable.

  M8-T5          Emergency pause/resume      Ensure `merge_paused`, `validation_paused`, `submissions_paused`  M5, M6, M4-T4  Each control is
                 wiring                      are checked at the top of *every* relevant Celery task/view, with                independently
                                             tasks re-queuing (delayed) rather than processing when paused;                   toggle-able and
                                             webhook endpoint keeps accepting/storing payloads even when                      takes effect
                                             `submissions_paused` (already built in M4-T4) (§12.6, §18).                      without
                                             Resume must be explicit/manual, never automatic.                                 restart.

  M8-T6 (P1)     Custom Ops React panel      Lightweight panel showing queue depth/health, oldest queued item  M8-T1--M8-T5   If built:
                                             age, failed job count, merge semaphore usage, last webhook                       admins get a
                                             timestamp (§12.6). Explicitly optional --- Django Admin is the P0                faster
                                             fallback.                                                                        operational
                                                                                                                              view than
                                                                                                                              Django Admin
                                                                                                                              alone.
  -------------------------------------------------------------------------------------------------------------------------------------------

**Checkpoint (M8 done when):** An admin can pause merge processing,
validation, and new submissions independently, and resume each
independently, with effects visible without a restart (§28 criterion
10); leaderboard freeze locks standings; every admin action and point
adjustment is in `AuditLog` (§28 audit requirement).

**Decision flag:** Open Question #6 (Django Admin alone vs. custom Ops
panel) --- confirm with the admin team whether Django Admin's UX is
acceptable during a live incident; PRD default is Django Admin as P0,
custom panel as P1.

------------------------------------------------------------------------

### M9 --- Load, Failure & Security Testing / Hardening

**Objective:** Prove the system holds under the PRD's stated scale,
failure modes, and security bar before deploying. This is the schedule's
designated buffer-absorption point. **PRD refs:** §24 (all), §20
(performance targets), §21 (failure handling), §19 (security), §28
(acceptance criteria --- verify what's testable pre-deploy).

  ------------------------------------------------------------------------------------------------------------
  Task           Name            What to do                                     Depends on     Outcome
  -------------- --------------- ---------------------------------------------- -------------- ---------------
  M9-T1          Unit test pass  Point-award transaction logic                  M1--M8         Full unit
                                 incl. concurrent-award simulation; daily-limit                coverage of the
                                 boundary conditions; state-machine transition                 above exists
                                 validity; webhook payload validation;                         and passes.
                                 permission checks (§24).                                      

  M9-T2          Integration     End-to-end                                     M1--M8         Full pipeline
                 test pass       webhook→Contribution→validation→merge→points                  verified
                                 flow with mocked GitHub/merge bot; Celery                     without live
                                 retry behavior; DB transaction rollback on                    GitHub
                                 simulated mid-transaction failure (§24).                      dependency.

  M9-T3          Load testing    100→200→300 concurrent read-heavy users        M1--M8         Measured
                                 against issues/leaderboard/dashboard; burst of                results meet or
                                 300 simultaneous webhook deliveries; burst of                 exceed §20/§24
                                 300 contributions reaching `APPROVED`                         targets.
                                 simultaneously --- verify merge concurrency                   
                                 stays capped and no 5xx spikes (§24). Validate                
                                 against §20 p95 targets (issues/projects                      
                                 \<300ms, leaderboard \<150ms, dashboard                       
                                 \<400ms, webhook ack \<200ms).                                

  M9-T4          Failure/chaos   Kill a Celery worker mid-task → verify         M1--M8         Every listed
                 testing         heartbeat-sweep requeue; stop Redis → verify                  failure
                                 webhook payloads persist and read paths still                 scenario
                                 work; simulate GitHub 500s/429s → verify                      recovers per
                                 backoff, no user-facing impact; send duplicate                §21's
                                 webhook deliveries (same `delivery_id`) →                     degradation
                                 verify no duplicate points; simulate two                      table.
                                 simultaneous merge webhooks for a participant                 
                                 at their daily-limit boundary → verify exact                  
                                 correct crediting (§24, §21).                                 

  M9-T5          Security        Auth bypass attempts; webhook signature        M1--M8         No listed
                 testing         tampering (must reject with 401); rate-limit                  vulnerability
                                 enforcement; injection/XSS payloads through                   class succeeds.
                                 filter params and user-editable text;                         
                                 admin-only endpoint access as non-staff user                  
                                 (§24, §19).                                                   

  M9-T6          Fix & re-verify Resolve issues found in T1--T5; re-run the     M9-T1--T5      All target
                                 affected test category to confirm the fix.                    scenarios pass
                                                                                               cleanly.
  ------------------------------------------------------------------------------------------------------------

**Checkpoint (M9 done when):** Every measurable §24 acceptance example
holds (e.g., "duplicate `delivery_id` sent 5 times → exactly one
`PointTransaction(status=AWARDED)`"; "300 concurrent contributions
reaching APPROVED → exactly `merge_concurrency` active merge-bot calls
at any instant"), and the pre-deploy-testable subset of §28's Launch
Acceptance Criteria passes in a staging-equivalent environment.

**Critical-path note:** Per §26, if the schedule has slipped, it should
slip *into* this module's buffer --- but P0 correctness items
(merge-concurrency control, idempotency) are never cut to save time
here. Cut P1/P2 scope (from earlier modules) instead, per §5 below.

------------------------------------------------------------------------

### M10 --- Deployment, Final Reconciliation Sync & Buffer

**Objective:** Ship to production, prove the full pipeline against real
data at scale, and reserve time for last-minute fixes. This module is
the launch gate. **PRD refs:** §23, §25 (all), §26, §28 (full
checklist).

  -------------------------------------------------------------------------------------------------
  Task           Name            What to do                           Depends on     Outcome
  -------------- --------------- ------------------------------------ -------------- --------------
  M10-T1         Backend deploy  Gunicorn behind Cloudflare, workers  M9, M10-T3,    Production
                                 sized `2*CPU+1` (tune after load     M10-T4         backend live
                                 test); Celery worker pools split at                 with correct
                                 minimum into `merge` (capped                        process
                                 concurrency),                                       topology.
                                 `webhooks`+`validation` (higher                     
                                 concurrency),                                       
                                 `sync`+`notifications`+`analytics`                  
                                 (low concurrency); Celery beat                      
                                 running for scheduled                               
                                 reconciliation/rollups (§25).                       

  M10-T2         Frontend deploy Vite production build served via     M9             Production SPA
                                 Cloudflare (Pages/CDN), hashed                      live.
                                 assets, long cache headers (§25).                   

  M10-T3         Managed data    Managed Postgres (automated backups, M9             Data stores
                 stores          point-in-time recovery if plan                      confirmed
                                 supports it) and managed Redis                      durable per
                                 provisioned (§25).                                  hosting plan.

  M10-T4         Secrets         GitHub OAuth client secret, webhook  M9, M10-T3     No secret is
                                 secret, merge bot token,                            present in
                                 `SECRET_KEY`, DB/Redis URLs set via                 source or
                                 the hosting platform's secret                       unmanaged
                                 manager --- never in repo (§19,                     config.
                                 §25).                                               

  M10-T5         Observability   Sentry (backend + frontend DSNs)     M10-T1, M10-T2 Errors and
                 wiring          live; uptime monitor hitting                        uptime are
                                 `/health/` (§23, §25).                              actively
                                                                                     monitored
                                                                                     before
                                                                                     go-live.

  M10-T6         Full production Run the full sync (M2's mechanism)   M10-T1, M10-T3 Production
                 GitHub sync     against all \~67 repos / \~1,500                    data matches
                                 issues in production (§26, §28).                    the real
                                                                                     event's scale
                                                                                     target.

  M10-T7         End-to-end      Full user journey in production:     M10-T1--T6     Journey
                 smoke test      OAuth login → browse projects/issues                completes
                                 → (simulated) PR → contribution                     without error
                                 status → leaderboard/dashboard                      in production.
                                 update (§26, §28).                                  

  M10-T8         Buffer          Remaining time reserved for fires    M10-T7         Any
                                 found during T6/T7. Do not consume                  last-minute P0
                                 this buffer preemptively on new                     issue is fixed
                                 scope.                                              before
                                                                                     go-live.
  -------------------------------------------------------------------------------------------------

**Checkpoint / Launch Gate (M10 done when):** Every item in §28's Launch
Acceptance Criteria checklist passes in production. This is the formal
go/no-go gate for the event.

------------------------------------------------------------------------

## 4. Cross-Cutting Dependency Map

    M1 (Auth+Data model+Setup)
     └─▶ M2 (GitHub read-side sync)
          └─▶ M3 (Read APIs + Explorer UI)
     └─▶ M4 (Webhook ingestion)  [formal dep: M1 only, per §26 Day-table;
                                   functional dep: M2's Issue data, for meaningful testing]
          └─▶ M5 (State machine + validation)
               └─▶ M6 (Merge queue + points)
                    └─▶ M7 (Leaderboard/dashboard/profile)  [also depends on M3's frontend patterns]
     └─▶ M8 (Admin + emergency controls)  [depends on M5 + M6 existing to have something to pause/monitor]
          (M1, M5, M6, M8 all feed M9)
    M1, M2, M3, M4, M5, M6, M7, M8 ──▶ M9 (Testing/hardening) ──▶ M10 (Provision stores/secrets → deploy → reconcile → smoke test)

**True critical path (per §26):** M4 → M5 → M6 (webhook → validation →
merge → points). This is the hardest span to compress and the one the
PRD explicitly says must not be cut for schedule relief.

**Blocking decisions (see §6 below) sit on this path:** Open Question #1
blocks the start of M4; Open Question #2 blocks the start of M6.

------------------------------------------------------------------------

## 5. Priority & Scope-Cutting Guidance

**Protected --- never cut, regardless of schedule pressure** (P0
correctness, per §26 and the PRD's own "P0 Critical Path" list): -
GitHub OAuth login (M1) - Idempotent, signature-verified webhook
ingestion (M4) - Full contribution state machine with worker-crash
recovery (M5) - Bounded-concurrency merge queue via Redis semaphore
(M6) - Transactional, race-safe point award with daily limits;
over-limit contributions still recorded (M6) - Cached, consistent
leaderboard with own-rank visibility (M7) - Admin emergency
pause/resume/freeze controls (M8) - Reconciliation sync fallback (M4) -
Graceful degradation across all dependencies (cross-cutting, verified in
M9) - Full audit trail on points and admin actions (M6, M8) - Load
testing at target scale before go-live (M9)

**Cut in this order if the 10-day window is threatened** (P1 first, then
P2, per PRD's own guidance in §26): 1. Custom Ops React panel (M8-T6,
P1) --- fall back to Django Admin only. 2. Admin manual point adjustment
UI (M6-T6, P1) --- can be done via direct DB/Django Admin action if
needed. 3. `/stats/` aggregate dashboard (M7-T5, P1) --- keep if
feasible, cut if not. 4. Suspicious-activity view / suspend-participant
UI polish (P1, part of M8-T1) --- core suspend flag can remain a raw
Django Admin field. 5. Top-projects/top-languages stats (M7, P2). 6.
Daily/weekly leaderboard views (M7, P2). 7. Relevance/activity sort on
Issue Explorer (M3-T6, P2).

Never cut into M5/M6's correctness logic (state machine integrity,
idempotency, race-safety) to make room for the above --- per §26,
schedule slip absorbs into M9's buffer instead.

------------------------------------------------------------------------

## 6. Open Questions Impacting Planning

These are unresolved in the PRD (§29). This plan does not answer them
--- it marks where they block or affect execution.

  ----------------------------------------------------------------------------------------
  \#                Question                           Affects           Nature of impact
  ----------------- ---------------------------------- ----------------- -----------------
  1                 Webhook registration model: single M4                **Blocks module
                    org-level webhook vs. per-repo                       start** ---
                    registration                                         determines
                                                                         M4-T1's actual
                                                                         GitHub-side
                                                                         setup. PRD says
                                                                         resolve
                                                                         immediately
                                                                         (ideally during
                                                                         M1).

  2                 Merge bot interface (GitHub Action M6                **Blocks module
                    / bot PAT / third-party service)                     start** ---
                    --- not specified in PRD                             M6-T1/T2/T4
                                                                         cannot be
                                                                         implemented
                                                                         against an
                                                                         undefined
                                                                         interface. PRD
                                                                         states this is
                                                                         needed "by Day 5
                                                                         at the latest."

  3                 Deferred-points policy: lost       M6                Non-blocking ---
                    (current default)                                    PRD default
                    vs. banked-and-released-next-day                     ("lost") is
                                                                         buildable now,
                                                                         but UX copy and
                                                                         organizer
                                                                         sign-off should
                                                                         confirm this
                                                                         before it's
                                                                         treated as final.

  4                 OAuth email scope: is participant  M1, and the       Non-blocking ---
                    email needed for notifications?    `notifications`   affects OAuth
                                                       queue generally   scope request in
                                                                         M1-T3 and whether
                                                                         the
                                                                         `notifications`
                                                                         queue does
                                                                         anything
                                                                         meaningful
                                                                         (already
                                                                         P2/low-priority
                                                                         regardless).

  5                 Trivial-diff/low-effort PR         M5                Non-blocking ---
                    detection --- explicitly out of                      confirms M5-T2
                    scope for launch                                     should *not*
                                                                         attempt this;
                                                                         relies on repo
                                                                         maintainers' own
                                                                         review standards.

  6                 Django Admin only vs. custom Ops   M8                Non-blocking for
                    panel for emergency controls                         P0 (Django Admin
                                                                         is the P0 path,
                                                                         already planned
                                                                         in M8-T1--T5) ---
                                                                         affects only
                                                                         whether M8-T6
                                                                         (P1) gets built.

  7                 Post-event data retention / "final Not currently in  **Unscoped.** If
                    frozen" CSV export for prize       any module        confirmed needed,
                    distribution                                         it is a small
                                                                         addition that
                                                                         should be slotted
                                                                         into M10's Day
                                                                         9/10 buffer
                                                                         (M9-T6 or M10-T8)
                                                                         --- do not add it
                                                                         to earlier
                                                                         modules
                                                                         speculatively.
  ----------------------------------------------------------------------------------------

------------------------------------------------------------------------

## 7. Testing & Validation Stages

-   **Per-module unit tests** are written alongside each module
    (M1--M8), not deferred --- see each module's checkpoint criteria for
    what must already be verifiable by the time M9 starts.
-   **M9 is the dedicated integration/load/chaos/security pass** (§24 in
    full) --- see M9 above for the complete task breakdown. It assumes
    per-module correctness already holds and focuses on system-level
    behavior under scale and failure.
-   **M10-T7** is the final production smoke test --- the last
    validation stage before go-live, distinct from M9's
    staging-equivalent testing.

------------------------------------------------------------------------

## 8. Final Production-Readiness Stage

**M10 is the production-readiness stage.** The system is not "done"
until every item in the PRD's §28 Launch Acceptance Criteria checklist
passes in production, including: - Full 67-repo/\~1,500-issue production
sync completed successfully. - Sentry (backend+frontend) and uptime
monitoring live against `/health/`. - Load test at 300 concurrent users
meets §20 p95 targets without 5xx spikes. - All simulated-failure
acceptance criteria (GitHub outage, Redis outage, Celery crash) hold in
production, not just staging. - End-to-end user journey smoke test
passes.

No module beyond M10 exists in this plan --- M10's checkpoint **is** the
launch gate.
