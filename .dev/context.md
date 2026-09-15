# HackIT CommitRush --- Project Context

------------------------------------------------------------------------

## 1. Purpose of This Document

`context.md` is the **current-state** document for this project. It
tells anyone entering the repository --- human or AI agent --- what
CommitRush is, what has actually been decided, what has actually been
built, and what remains unknown or unresolved.

-   **PRD.md** defines *what the product must do*.
-   **`.dev/plan.md`** defines *what must be built and in what order*.
-   **`.dev/context.md`** (this file) defines *what the project
    currently is, what is decided, what is done, and what agents must
    respect before touching anything*.

This is not a second PRD and not a task plan. Read it before selecting
or executing work.

`.dev/` is internal AI-development orchestration context. It is
gitignored, is **not application source code**, and must never be
exposed through application functionality.

------------------------------------------------------------------------

## 2. Project Identity

  ---------------------------------------------------------------------------------------
  Field                               Value
  ----------------------------------- ---------------------------------------------------
  Project                             HackIT CommitRush

  Repository                          https://github.com/Hackit-DROID/HackIT-CommitRush

  Stated working tree                 `.dev/`, `backend/`, `frontend/`, `.gitignore`
                                      (root directory name given as `OxideAuth/` --- see
                                      §11, AMB-9)

  Scale target (PRD)                  500 participants, 300 concurrent requests, 67
                                      repos, \~1,500 issues

  Timeline constraint (PRD §26)       10 days to production-ready launch
  ---------------------------------------------------------------------------------------

**High-level purpose (PRD §1):** CommitRush is an event orchestration
layer sitting on top of GitHub for a college open-source contribution
event. GitHub remains the system of record for code, issues, PRs,
reviews, and merges. CommitRush owns what GitHub does not: participant
identity, issue/project discovery, contribution tracking, validation,
daily limits, points, leaderboard, and administration.

**Actors (PRD §6):**

  -----------------------------------------------------------------------
  Persona                             Role
  ----------------------------------- -----------------------------------
  Participant                         Student with a GitHub account,
                                      competing for points

  Project Maintainer (internal)       HackIT member who curated a repo
                                      --- **not a distinct system role
                                      for launch**; managed via Django
                                      Admin

  Event Admin                         HackIT organizer: configures the
                                      event, monitors the pipeline,
                                      resolves disputes, operates
                                      emergency controls

  Spectator (unauthenticated)         Views landing page, public
                                      leaderboard, stats
  -----------------------------------------------------------------------

**System concept (PRD §10.1):** No user-facing request synchronously
touches GitHub or the merge bot. User-facing reads are served from
PostgreSQL (optionally via Redis cache); everything touching GitHub
happens in Celery workers, decoupled from the request/response cycle.

------------------------------------------------------------------------

## 3. Current Development State

The project is in the **PLANNING / INITIAL SETUP** stage. Nothing in the
table below is marked implemented, because no supplied material confirms
implementation.

  -----------------------------------------------------------------------
  Area                    Status                  Notes
  ----------------------- ----------------------- -----------------------
  Product requirements    **Complete**            PRD.md exists and is
                                                  authoritative. Contains
                                                  7 explicit open
                                                  questions (§29).

  Project planning        **Complete**            `.dev/plan.md` exists:
                                                  10 modules (M1--M10),
                                                  \~60 tasks, checkpoints
                                                  and dependencies
                                                  defined.

  Project context         **Complete**            `.dev/context.md`
                                                  exists and records
                                                  current state.

  Agent mapping           **Not created**         Planned future
  (`awsmap.md`)                                   document; filename is
                                                  canonicalized as
                                                  `.dev/awsmap.md`.

  Continuation doc        **Not created**         Planned future
  (`continue.md`)                                 document.

  Backend                 **Not confirmed         `backend/` directory
                          implemented**           reported to exist;
                                                  contents unverified.
                                                  Plan module M1
                                                  (scaffolding) not
                                                  confirmed started.

  Frontend                **Not confirmed         `frontend/` directory
                          implemented**           reported to exist;
                                                  contents unverified.

  Database                **Not confirmed         Schema fully specified
                          implemented**           in PRD §15; no
                                                  migrations confirmed to
                                                  exist.

  GitHub integration      **Not confirmed         Specified PRD §8.1,
  (OAuth)                 implemented**           §13.1; planned M1-T3.

  GitHub read-side sync   **Not confirmed         Specified PRD §13.5,
                          implemented**           §13.6; planned M2.

  Webhooks                **Not confirmed         Specified PRD
                          implemented**           §13.2--§13.4; planned
                                                  M4. **Blocked by open
                                                  question AMB-1.**

  Contribution pipeline   **Not confirmed         Specified PRD §11, §22;
  (state machine +        implemented**           planned M5.
  validation)                                     

  Merge system            **Not confirmed         Specified PRD §12;
                          implemented**           planned M6. **Blocked
                                                  by open question AMB-2
                                                  (merge bot interface
                                                  undefined).**

  Points & daily limits   **Not confirmed         Specified PRD §14;
                          implemented**           planned M6.

  Leaderboard / dashboard **Not confirmed         Specified PRD §8.6,
  / profile               implemented**           §16; planned M7.

  Admin / operations      **Not confirmed         Specified PRD §18;
                          implemented**           planned M8.

  Testing                 **Not started           Strategy defined PRD
                          (unconfirmed)**         §24; planned per-module
                                                  plus dedicated pass M9.

  Deployment              **Not started           Architecture defined
                          (unconfirmed)**         PRD §25; planned M10.
  -----------------------------------------------------------------------

> A task appearing in `plan.md` means it is **planned**, never that it
> is **done**. Verify the repository before claiming any of the above
> has changed.

------------------------------------------------------------------------

## 4. Authoritative Documents

  --------------------------------------------------------------------------
  Document             Exists?           Role              Authority
  -------------------- ----------------- ----------------- -----------------
  `PRD.md`             **Yes**           Product           **1 --- highest**
                                         requirements,     
                                         priorities        
                                         (P0/P1/P2),       
                                         architecture      
                                         decisions,        
                                         acceptance        
                                         criteria          

  `.dev/plan.md`       **Yes**           Execution order,  2
                                         modules           
                                         (M1--M10), tasks, 
                                         dependencies,     
                                         checkpoints       

  `.dev/context.md`    **Yes** (this     Current project   3
                       file)             state and         
                                         accumulated       
                                         development       
                                         context           

  `.dev/awsmap.md`     **No ---          Maps plan         ---
                       planned**         modules/tasks to  
                                         appropriate AI    
                                         agents, skills,   
                                         and workflows     

  `.dev/continue.md`   **No ---          Execution         ---
                       planned**         instructions for  
                                         the primary       
                                         coding agent:     
                                         inspect context,  
                                         select next task, 
                                         consult the agent 
                                         map, execute,     
                                         update context,   
                                         follow the        
                                         checkpoint        
                                         workflow          
  --------------------------------------------------------------------------

**Intended relationship:**

    PRD.md
      ↓
    .dev/plan.md
      ↓
    .dev/context.md  +  .dev/awsmap.md
      ↓
    .dev/continue.md  (execution / continuation)

**Conflict rule:** if these documents disagree, do **not** silently
resolve it. PRD.md wins on product requirements; plan.md wins on
sequencing. Record the conflict in §11 of this document and escalate.

**Naming note:** the plan document internally refers to the
agent-mapping file as `ASWmap.md`; the current task brief calls it
`awsmap.md`. See AMB-10 --- confirm one spelling before creating the
file, so two competing files are not produced.

------------------------------------------------------------------------

## 5. Product / System Understanding

Summarized at the level an agent needs before working. Detail lives in
the PRD.

-   **Authentication (§8.1, §13.1):** GitHub OAuth only --- no manual
    username entry. Authorization Code flow with `state` CSRF
    protection. Session-based auth for the SPA. `github_id` is the
    immutable identity key; `username`/`avatar_url` are cached and
    refreshed at login. Revoked OAuth grants must re-prompt, not
    hard-fail.
-   **Participants (§6, §15):** Event profile extending the Django user,
    carrying GitHub identity, suspension flag, and a denormalized point
    total.
-   **Projects & Issues (§8.2, §13.5, §15):** Tracked repos and their
    issues are cached locally in PostgreSQL so all discovery (search,
    filter, sort, server-side pagination) is served from the database,
    never from live GitHub calls. GitHub remains canonical for
    issue/PR/repo content; CommitRush is canonical for contribution
    lifecycle, points, and event rules.
-   **GitHub synchronization (§13.4, §13.6):** Bulk read-side import
    plus a scheduled reconciliation sweep that catches missed or lost
    webhooks. GitHub API usage is rate-limit aware and backs off; it
    never blocks a user-facing request.
-   **Webhooks / events (§13.2, §13.3):** `pull_request` and `issues`
    events. The endpoint verifies `X-Hub-Signature-256`, durably stores
    the raw payload keyed by GitHub's delivery ID, enqueues async work,
    and returns 200 fast. All parsing and business logic happen in the
    async task.
-   **Contributions (§11):** The core entity --- CommitRush's view of a
    PR raised against a tracked issue. Moves through an explicit state
    machine (`PENDING`, `QUEUED`, `UNDER_REVIEW`/`VALIDATING`,
    `APPROVED`, `MERGING`, `MERGED`, `REJECTED`, `FLAGGED`, `RETRY`).
    Only `MERGED` is credited. Worker crashes are recovered by a
    heartbeat/lock-timeout sweep --- state lives in Postgres, never in
    worker memory.
-   **Validation (§22):** Deterministic rules plus admin review. No ML
    fraud detection, and no trivial-diff/LOC scoring for launch
    (explicit non-goal).
-   **Merge processing (§12):** Bounded-concurrency queue. Merge-bot
    invocation is gated so that only a configured number (5--10) of
    merge calls are ever active at once; the rest wait visibly in
    `APPROVED`. FIFO by approval time with an admin priority override.
    Separate Celery queues isolate failure domains so a merge-bot outage
    never starves webhook intake.
-   **Points & limits (§14):** Per-issue configurable point values.
    Points awarded only on transition to `MERGED`, exactly once, inside
    a single transaction using per-participant-per-day row-level
    locking. Daily limits cap **credited throughput, not
    participation**: an over-limit merged PR is still fully recorded and
    still reaches `MERGED`, with its point transaction recorded as
    deferred at zero points.
-   **Leaderboard / dashboard / profile (§8.6, §16):** Cached
    leaderboard with short TTL and a defined tie-break; a participant's
    own rank is visible even when off the top page; leaderboard can be
    frozen at event end. A single aggregated dashboard endpoint
    minimizes round trips.
-   **Administration (§18):** Django Admin is the primary admin surface
    for launch, covering participants, projects, issues, contributions,
    event config, and a read-only audit log. A custom Ops panel is a P1
    nice-to-have, not the launch path.
-   **Emergency controls (§18):** Pause/resume controls for pipeline
    stages and a leaderboard freeze, held as flags read at the top of
    the relevant task/view so they take effect without a restart. Resume
    is always explicit and manual, never automatic.
-   **Graceful degradation (§21):** If GitHub, the merge bot, or Redis
    is unavailable, the site stays browsable from Postgres and no
    contribution data is lost --- work queues or defers and recovers via
    retry/reconciliation.

------------------------------------------------------------------------

## 6. Core Domain Concepts

PRD terminology. Do not substitute synonyms.

  -----------------------------------------------------------------------
  Concept                             Meaning
  ----------------------------------- -----------------------------------
  Participant                         A registered student competing in
                                      the event; identified by immutable
                                      GitHub id

  Project                             A tracked GitHub repository

  Issue                               A tracked GitHub issue belonging to
                                      a Project, carrying an event point
                                      value, difficulty, and category

  IssueLabel                          Cached GitHub label attached to
                                      Issues

  PullRequest                         Local cache of a GitHub PR (merged
                                      flag, head SHA, author)

  Contribution                        **Core entity** --- CommitRush's
                                      record of a PR raised against a
                                      tracked Issue by a Participant;
                                      carries the state machine status

  PointTransaction                    Immutable ledger entry for a point
                                      event (awarded / deferred / revoked
                                      / admin adjustment)

  DailyContributionUsage              Per-participant, per-day counters
                                      used to enforce daily limits

  EventConfig                         Singleton runtime configuration:
                                      limits, merge concurrency, pause
                                      switches, leaderboard freeze, event
                                      status

  WebhookEvent                        Durable record of an inbound GitHub
                                      webhook delivery; the primary
                                      deduplication key

  AuditLog                            Trail of admin and system actions

  Merge queue                         The bounded-concurrency pipeline
                                      that drives merge processing

  Merge bot                           The external component that
                                      performs merges --- **interface not
                                      defined in the PRD** (see AMB-2)

  Reconciliation sync                 Scheduled fallback that catches
                                      webhooks GitHub never delivered or
                                      that were lost

  Deferred points                     Points not granted because a daily
                                      limit was reached; the contribution
                                      is still recorded and merged

  Credited state                      Only `MERGED` --- no other state
                                      awards points
  -----------------------------------------------------------------------

Field-level schema is specified in PRD §15. Do not invent fields; where
the PRD references a field it does not define, see §11 (AMB-4 through
AMB-8).

------------------------------------------------------------------------

## 7. Established Decisions

Each is supported by the cited source. These are decided, not open.

  -------------------------------------------------------------------------
  Decision                  Reason / context        Source
  ------------------------- ----------------------- -----------------------
  One production release,   Lets the team cut scope PRD §1
  no MVP1/2/3; scope        under time pressure     
  controlled via P0/P1/P2   without breaking        
  tags                      correctness             

  No user-facing request    GitHub latency/rate     PRD §10.1
  synchronously calls       limits and merge-bot    
  GitHub or the merge bot   instability must never  
                            block page loads        

  Backend-first sequencing; Senior instruction; PRD PRD §26, plan §1
  a frontend feature waits  states backend for a    
  on its API contract       resource should land    
                            0.5--1 day ahead of its 
                            frontend                

  Fixed critical-path order PRD-established         PRD §26, plan §1
  (auth → data model → sync dependency progression; 
  → APIs/UI → webhooks →    not to be reordered for 
  state machine →           convenience             
  merge/points →                                    
  leaderboard → admin →                             
  testing → deploy)                                 

  PostgreSQL is the         All event state lives   PRD §13.5, §15
  authoritative application there; GitHub stays     
  database                  canonical only for      
                            code/issues/PRs         

  Webhook ingestion is      Duplicate deliveries    PRD §13.2, §15, §28
  idempotent on GitHub's    must never create       
  delivery ID               duplicate contributions 
                            or point rows           

  Webhook payloads are      Guarantees no payload   PRD §21.1
  stored durably before     loss if the             
  async processing          broker/cache is         
                            unavailable             

  Contribution lifecycle is Prevents accidental     PRD §11
  an explicit state machine crediting from          
  with only `MERGED`        intermediate states     
  credited                                          

  Worker-crash recovery via Contributions are never PRD §11.2
  heartbeat/lock-timeout    stuck or silently lost  
  sweep                     because state lives in  
                            Postgres                

  Point award is            Prevents daily-limit    PRD §14.4
  transactional and         bypass under concurrent 
  race-safe, using          merges without a global 
  per-participant-per-day   lock                    
  row locking                                       

  Exactly one award per     Prevents                PRD §15, §28
  credited contribution,    double-awarding         
  enforced at the database                          
  level                                             

  Over-limit merged         Rejecting a legitimate  PRD §14.3
  contributions are         merged PR is bad UX;    
  recorded with deferred    cap points, not         
  points, never rejected    participation           

  Deferred points are       Avoids retroactive      PRD §14.3, §29
  **not** banked to the     leaderboard jumps;      
  next day                  keeps the rule simple   
                            --- *pending organizer  
                            confirmation, AMB-3*    

  Merge concurrency is      One bot hiccup must not PRD §12.2
  bounded (5--10) and       become 300 concurrent   
  admin-adjustable without  merge calls             
  redeploy                                          

  Separate Celery queues    Isolates failure        PRD §12.1
  per workload with merge   domains; a merge outage 
  highest priority          must not starve webhook 
                            intake                  

  Leaderboard is cached     Read performance under  PRD §8.6, §20
  with short TTL;           deadline-time load      
  participant's own rank                            
  always visible                                    

  Emergency pause/resume    Takes effect without    PRD §18
  flags live on the config  restart; a human must   
  singleton, checked per    confirm the fix before  
  task/view, resumed        resuming                
  explicitly                                        

  Django Admin is the P0    Minimizes custom UI     PRD §18, §9
  admin surface; a custom   work inside 10 days     
  Ops panel is P1                                   

  Reconciliation sync is    Webhook delivery gaps   PRD §13.4, §27
  the safety net for missed must not lose           
  webhooks                  contributions           

  Full audit trail on point Disputes must be        PRD §19, §18
  transactions and admin    resolvable              
  actions                                           

  Contribution rows are     Contribution history    PRD §11.2
  never deleted; a bad      stays honest and        
  merge is reversed via a   complete                
  ledger entry                                      

  Explicitly rejected       Adds deployment risk    PRD §5, §10.3
  infrastructure:           and learning cost with  
  Kubernetes,               no benefit at this      
  microservices, GraphQL,   scale                   
  Kafka                                             

  Schedule slip absorbs     Merge-concurrency       PRD §26, plan §5
  into the hardening/buffer control and idempotency 
  period, never into        are correctness, not    
  cutting correctness work  polish                  
  -------------------------------------------------------------------------

------------------------------------------------------------------------

## 8. Non-Negotiable Constraints

### Product constraints

-   10-day window to production launch (PRD §26).
-   P0 functionality is non-negotiable for launch. Cut P1, then P2, in
    the order given in plan §5. Never silently downgrade or drop a P0
    requirement.
-   Non-Goals (PRD §5) are the enforcement mechanism against scope
    creep. Anything not listed P0/P1 defaults to out of scope. New asks
    get a "post-launch" answer by default.
-   No custom Git hosting, in-browser editor, chat platform, social
    feed, GitHub PR/review UI replacement, ML fraud detection, native
    mobile app, or elaborate badge system.
-   Multi-tenancy is not built now, but the design should not preclude
    it.

### Data / integrity constraints

-   Every idempotency key in PRD §15 must exist and be enforced at the
    database level, not only in application logic.
-   One award per credited contribution. Duplicate webhook deliveries
    must never produce duplicate contributions or duplicate point rows.
-   Point award must be a single atomic transaction; no partial or
    half-applied awards.
-   Daily-limit enforcement must be structurally race-safe (row-level
    locking), not advisory.
-   Contribution rows are never deleted; corrections go through the
    ledger, audited.

### GitHub integration constraints

-   GitHub remains canonical for code, issues, PRs, reviews, and merges.
-   CommitRush never pushes on a participant's behalf; participant OAuth
    requires no repository write scope.
-   Webhook signature verification is mandatory before any processing;
    unsigned or mis-signed requests are rejected.
-   GitHub API calls back off when the remaining rate limit falls below
    the safety threshold; non-critical sync deprioritizes itself.
-   A legitimate GitHub redelivery must never receive an error response.

### Reliability constraints

-   The site must stay browsable from the database when GitHub, the
    merge bot, or the cache is unavailable.
-   Broker unavailability must not lose webhook payloads; processing
    resumes from durable records.
-   Stuck in-flight contributions must be recoverable by the heartbeat
    sweep within the timeout window.
-   Queue isolation must hold: one failing queue must not starve the
    others.

### Security constraints

-   OAuth Authorization Code flow with `state` CSRF protection.
-   Secure, HttpOnly, SameSite session cookies; CSRF required on unsafe
    methods.
-   CORS restricted to the deployed frontend origin only.
-   Secrets live in environment/secret manager --- never in the
    repository, never in the database.
-   ORM only; no raw string-interpolated SQL. All filter/query params
    validated through serializers.
-   GitHub-sourced text is rendered as text, not raw HTML, unless
    explicitly sanitized.
-   Object-level authorization: a participant sees only their own full
    contribution detail; admin actions require staff.
-   Rate limiting active on public list endpoints.

### Operational constraints

-   Emergency pause/resume controls must take effect without a restart,
    and each must be independently toggleable.
-   Resume is always an explicit human action.
-   All admin actions and point adjustments are audit-logged.

### UX constraints

-   Server-side pagination everywhere; never load the full issue set
    client-side.
-   Every list view has explicit loading, empty, and error-with-retry
    states.
-   No optimistic updates for anything touching points or contribution
    status --- optimistic UI is limited to trivial local state such as
    filter selection.
-   Contribution status shown to the participant must map to the defined
    status vocabulary with a plain-language explanation.
-   A service-status banner surfaces degraded-mode notices.

------------------------------------------------------------------------

## 9. Current Implementation Reality

### Implemented

-   Nothing is confirmed implemented in the application (`backend/`,
    `frontend/`).
-   Documentation artifacts confirmed to exist: `PRD.md`,
    `.dev/plan.md`, `.dev/context.md`.

### In Progress

-   `.dev/context.md` --- complete for the current
    planning/initial-setup state.
-   No application work is confirmed to be in progress.

### Planned (exists in `plan.md`, **not** built)

-   M1 --- Project setup, full data model, GitHub OAuth, config
    singleton bootstrap, health endpoint
-   M2 --- GitHub read-side sync (repos, issues, labels,
    rate-limit-aware)
-   M3 --- Project/Issue read APIs, throttling, Explorer UI
-   M4 --- Webhook ingestion, deduplication, async processing,
    reconciliation scaffold
-   M5 --- Contribution state machine, validation rules, crash-recovery
    sweep, status APIs and UI
-   M6 --- Merge queue with bounded concurrency, retry policy,
    transactional point award with daily limits
-   M7 --- Leaderboard, dashboard, profile, stats, status banner
-   M8 --- Admin system and emergency controls
-   M9 --- Unit/integration/load/failure/security testing and hardening
-   M10 --- Deployment, observability, full production sync, smoke test,
    buffer

### Unknown / Requires Verification

-   Actual contents of `backend/` and `frontend/` --- directories are
    reported to exist; whether they contain scaffolding, partial work,
    or nothing is unverified.
-   Whether any dependency manifests, migrations, or configuration files
    exist.
-   Whether the repository root directory name is `OxideAuth/` or
    something else (AMB-9).
-   Whether any external accounts or infrastructure exist yet: GitHub
    OAuth app, webhook secret, merge-bot credentials, hosting, managed
    database/cache, error tracking, uptime monitoring.
-   Whether the tracked repository list (the \~67 repos) has been
    assembled.
-   Whether any of the seven PRD open questions have been answered
    outside these documents.

**An agent must inspect the repository before claiming any item above
has changed state.**

------------------------------------------------------------------------

## 10. Important Dependencies and Ordering

The execution chain from `plan.md` (which preserves PRD §26):

    M1  Auth / foundation / data model
     → M2  GitHub read-side synchronization
     → M3  Project & Issue APIs + Explorer UI
     → M4  Webhook ingestion
     → M5  Contribution state machine + validation
     → M6  Merge queue + points
     → M7  Leaderboard / dashboard / profile
     → M8  Administration + emergency controls
     → M9  Load, failure & security testing
     → M10 Deployment + final reconciliation + buffer

**Caveats that must be preserved, not smoothed over:**

-   **True critical path is M4 → M5 → M6** (webhook → validation → merge
    → points). The PRD identifies this as the hardest span to compress.
    If the schedule slips, it slips into M9/M10 buffer --- never into
    cutting merge-concurrency control or idempotency.
-   **M4's formal dependency is M1 only** (per the PRD day-table), but
    it has a **functional** dependency on M2: "references a tracked
    issue" logic cannot be meaningfully tested without real issue data.
    The plan records this distinction deliberately --- do not collapse
    it in either direction.
-   **M8 depends on M5 and M6 existing**, since there must be pipeline
    stages to pause and contributions to act on.
-   **M7 depends on M6** for point data and on M3 for established
    frontend patterns.
-   **M9 requires M1--M8 complete.** M9 is a system-level hardening
    pass; per-module unit tests are written during M1--M8, not deferred
    to M9.
-   **Two open decisions sit on the critical path:** AMB-1 blocks the
    start of M4; AMB-2 blocks the start of M6.
-   Backend-first applies within modules too: frontend tasks live inside
    the module that owns their backing API and are not a parallel track.

Task-level detail lives in `plan.md`. Do not duplicate it here.

------------------------------------------------------------------------

## 11. Known Ambiguities / Open Decisions

AMB-1 through AMB-7 are the PRD's own open questions (§29) and **must
not be answered by an agent**. AMB-8 through AMB-13 are additional gaps
or inconsistencies surfaced between PRD sections or between the PRD and
plan; they are recorded, not resolved.

  --------------------------------------------------------------------------
  ID                Issue                Current State     Required Action
  ----------------- -------------------- ----------------- -----------------
  AMB-1             Webhook registration Unresolved. PRD   Confirm
                    model: single        §29 marks it      repository
                    org-level webhook    "resolve          ownership
                    vs. per-repo         immediately";     structure with
                    registration across  plan marks it as  the event team
                    scattered accounts   **blocking M4**   before starting
                                                           M4

  AMB-2             Merge bot interface  Unresolved. PRD   Obtain the
                    is undefined ---     §29 states the    merge-bot
                    GitHub Action, bot   backend team      contract before
                    account with a       needs this        implementing
                    token, or            contract by Day   merge processing.
                    third-party service? 5; plan marks it  Do not assume an
                                         as **blocking     interface
                                         M6**              

  AMB-3             Deferred points      PRD default is    Confirm with
                    policy: lost at the  "not banked."     event organizers
                    cap (PRD default)    Buildable now,    before treating
                    vs. banked and       but unconfirmed   the behavior or
                    released next day    with organizers   its UI copy as
                                                           final

  AMB-4             OAuth email scope:   Unresolved.       Decide before
                    is participant email Affects the scope finalizing the
                    needed, or are       requested in M1   OAuth scope
                    username/avatar      and whether       request
                    sufficient?          notifications do  
                                         anything at       
                                         launch            

  AMB-5             Trivial/low-effort   Explicitly out of Confirm
                    PR detection         scope for launch; organizers accept
                                         reliance on       this. Do **not**
                                         maintainer review implement diff
                                         standards         scoring absent an
                                                           explicit decision

  AMB-6             Django Admin alone   PRD default:      Confirm Django
                    vs. a custom Ops     Django Admin is   Admin UX is
                    panel for            P0, custom panel  acceptable to
                    live-incident        is P1             admins during an
                    emergency controls                     incident

  AMB-7             Post-event data      Not currently     If confirmed
                    retention / final    scoped into any   needed, slot into
                    frozen export for    module            the M9/M10
                    prize distribution                     buffer. Do not
                                                           add speculatively
                                                           to earlier
                                                           modules

  AMB-8             **Emergency control  Requirement       Obtain an
                    without a defined    exists; the       explicit decision
                    config field:** PRD  backing           on the field and
                    §18 lists "pause     configuration     semantics for
                    point awarding" as a field is **not    pausing point
                    P0 emergency         defined**         awarding. **Do
                    control, but the                       not invent the
                    EventConfig field                      field or infer
                    list in §15 defines                    its behavior**
                    only merge,                            
                    validation, and                        
                    submissions pauses                     
                    plus leaderboard                       
                    freeze. Plan M8-T5                     
                    wires only the three                   
                    defined pause flags                    

  AMB-9             Fields referenced by Requirements      Resolve schema
                    PRD prose but absent exist; schema     additions
                    from the §15 entity  definitions are   explicitly during
                    field lists: the     incomplete        M1 rather than
                    merged-count value                     improvising them
                    used for leaderboard                   mid-module.
                    tie-breaking; the                      Record each
                    issue-author                           resolution here
                    identifier used by                     
                    the                                    
                    self-created-issue                     
                    validation rule; the                   
                    project slug used in                   
                    the project detail                     
                    route; the                             
                    per-contribution                       
                    priority flag used                     
                    for merge-queue                        
                    override; the                          
                    retry-limit                            
                    configuration the                      
                    admin panel claims                     
                    is editable; the                       
                    worker heartbeat                       
                    value referenced by                    
                    the crash-recovery                     
                    sweep                                  

  AMB-10            Denormalized         Two mechanisms    Choose one
                    participant point    described for the explicitly before
                    total: §15 describes same value        implementing
                    it as recomputed by                    point award;
                    trigger/signal,                        transactional
                    while §15's                            consistency is a
                    leaderboard note and                   stated P0
                    §14.4 describe it as                   correctness
                    updated inside the                     property
                    same transaction as                    
                    the ledger insert                      

  AMB-11            A lightweight status Endpoint          Decide whether
                    endpoint is          existence         the banner is fed
                    referenced as a      undecided         by the stats
                    possible feed for                      endpoint or a
                    the service-status                     dedicated one
                    banner but does not                    before building
                    appear in the API                      M7
                    specification                          

  AMB-12            Root                 Naming            Verify actual
                    working-directory    discrepancy,      repository layout
                    name given as        unexplained       before assuming
                    `OxideAuth/` while                     paths
                    the project and                        
                    repository are named                   
                    HackIT CommitRush                      

  AMB-13            Agent-mapping        Naming            Confirm one
                    document is referred discrepancy       spelling before
                    to as both                             creating the
                    `ASWmap.md` (in                        file, to avoid
                    plan.md) and                           two competing
                    `awsmap.md` (in the                    documents
                    current brief)                         

  AMB-14            M1-T5 Redis health   Known deferred    /health/ currently
                    check deferred       item              verifies PostgreSQL/
                                                           database connectivity
                                                           only. Redis is not
                                                           introduced until M4/M5,
                                                           so Redis connectivity is
                                                           intentionally not
                                                           checked during M1. When
                                                           Redis is introduced, the
                                                           health endpoint must be
                                                           extended to report
                                                           Redis connectivity as
                                                           required by PRD §23.
                                                           This must not be
                                                           forgotten or treated
                                                           as the final health-
                                                           response shape.

  AMB-15            Path traversal via   Resolved in       REPO_PATTERN regex
                    dot-segment repo     M2-T1             allows dot-only parts
                    names (NC-1)                           ('owner/..'). Resolved
                                                           in M2-T1 by adding
                                                           explicit validation
                                                           in parse_repo_identifier
                                                           rejecting dot-only
                                                           segments.

  AMB-16            Concurrent new-repo  Deferred to       select_for_update() on
                    creation race in     M2-T4             empty queryset acquires
                    sync_project (NC-4)                    no lock. Concurrent
                                                           first-time syncs hit
                                                           unique constraint
                                                           IntegrityError. Safe
                                                           for M2-T1 management
                                                           command; M2-T4 Celery
                                                           task layer must add
                                                           get_or_create/retry
                                                           semantics.
  --------------------------------------------------------------------------

------------------------------------------------------------------------

## 12. Agent Safety Rules

1.  **Read `PRD.md` before making any product-level decision.** It is
    authoritative.
2.  **Read `.dev/plan.md` before selecting work.** Work is selected by
    module and task ID, not improvised.
3.  **Read this file before modifying anything**, and re-read it if
    returning after a gap.
4.  **Never assume planned functionality is implemented.** Inspect the
    repository and verify.
5.  **Never silently resolve a contradiction.** Record it in §11, state
    which source has authority, and escalate.
6.  **Never answer an open question on the project's behalf** (AMB-1
    through AMB-13). If a task is blocked by one, stop and report the
    block.
7.  **Do not invent schema fields, endpoints, config flags, or
    workflows** that the PRD does not establish --- particularly around
    EventConfig and emergency controls (AMB-8, AMB-9).
8.  **Do not redesign the architecture.** Explicitly rejected
    technologies stay rejected. Do not add a technology because it is
    common for this kind of system.
9.  **Do not change public API contracts casually.** The frontend
    depends on stable contracts; backend-first sequencing exists for
    this reason.
10. **Preserve idempotency and data-integrity guarantees in every
    change.** Deduplication keys, single-award enforcement,
    transactional point award, and row-level locking are correctness,
    not optimization.
11. **Never introduce a synchronous GitHub or merge-bot call into a
    user-facing request path.**
12. **Do not bypass security constraints** --- signature verification,
    object-level authorization, secret handling, input validation.
13. **Do not silently downgrade, defer, or drop a P0 requirement.** Cut
    P1/P2 in the documented order instead, and record the cut.
14. **Keep changes scoped to the assigned task.** No opportunistic
    refactors outside the task boundary.
15. **Do not modify `.dev/` orchestration files unless explicitly
    instructed**, other than the context updates described in §13.
16. **Never expose `.dev/` contents through application functionality**,
    and never commit them --- the directory is gitignored by design.
17. **Respect module checkpoints.** A module is complete only when its
    checkpoint criteria are observably met --- not when its tasks look
    finished.
18. **Report honestly.** If a task was partially completed or a
    checkpoint was not met, say so rather than marking it done.

------------------------------------------------------------------------

## 13. Context Update Rules

Update this document when:

-   a module or major task reaches its checkpoint (update §3 and §9),
-   an open question or ambiguity in §11 is resolved (move it to §7 with
    its source, and remove it from §11),
-   a significant architectural or product decision is made (§7),
-   a constraint changes (§8),
-   implementation reality diverges from what §9 records,
-   a new conflict between PRD and plan is discovered (§11),
-   a future document (`awsmap.md`, `continue.md`) is created (§4).

**This document represents the CURRENT STATE.** It is not an append-only
diary and not a changelog. When something becomes true, replace what was
there --- do not stack historical entries. Keep it concise enough that
an agent will actually read it end to end.

Routine per-task progress belongs in the execution workflow, not in
every section of this file.

------------------------------------------------------------------------

## 14. Quick Start for a New Agent

1.  Read `PRD.md` --- it is authoritative for product requirements and
    acceptance criteria.
2.  Read `.dev/plan.md` --- modules M1--M10, task IDs, dependencies,
    checkpoints.
3.  Read `.dev/context.md` (this file) --- current state, established
    decisions, constraints, open questions.
4.  **Inspect the repository.** Do not assume implementation state from
    any document.
5.  Identify the assigned task by its module and task ID.
6.  Check that the task's dependencies are actually satisfied, not
    merely scheduled.
7.  Check §11 --- confirm no open decision blocks the task. If one does,
    stop and report.
8.  Implement only the assigned scope, respecting §8 constraints and §12
    safety rules.
9.  Validate against the task's expected outcome and the module's
    checkpoint criteria.
10. Update §3, §9, and §11 of this document when state genuinely
    changes.
