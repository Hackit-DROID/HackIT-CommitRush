# HackIT CommitRush — AI Agent & Skill Map

---

## 1. Purpose

`awsmap.md` defines **who does what** in a multi-agent development setup: agent roles, subsystem ownership, task assignment, review requirements, handoff contracts, and conflict rules.

**This document controls:**
- Which agent role owns which subsystem and which plan task
- Which agents may review or support another agent's work
- Where handoffs are mandatory and what form they take
- Where parallel work is permitted and where it is forbidden
- What each agent is explicitly forbidden from modifying
- When an agent must stop and escalate

**This document does NOT control:**
- Product requirements or acceptance criteria — `PRD.md` owns those
- Execution order, task definitions, checkpoints, or the critical path — `.dev/plan.md` owns those
- Current project state, established decisions, or ambiguity status — `.dev/context.md` owns those
- The step-by-step execution loop an agent follows — `.dev/continue.md` will own that

This is not a second plan. Task descriptions are not reproduced here; task IDs reference `plan.md`.

---

## 2. Authority & Document Hierarchy

```
1. PRD.md            product requirements, priorities, acceptance criteria   [highest]
2. .dev/plan.md      execution order, task IDs, dependencies, checkpoints
3. .dev/context.md   current state, decisions, constraints, ambiguities
4. .dev/awsmap.md    agent ownership and collaboration                       [this file]
5. .dev/continue.md  execution workflow                                      [planned]
```

**If `awsmap.md` conflicts with PRD, plan, or context: `awsmap.md` loses.** An agent encountering such a conflict does not resolve it silently — it records the conflict and escalates per §12.

`.dev/` is internal AI orchestration context. It is gitignored by design, is not application source code, and must never be exposed through application functionality. Agents do not modify `.dev/` files during normal implementation; the only sanctioned exception is the context-update rules defined in `context.md` §13, executed through the workflow `continue.md` will define.

---

## 3. Agent Architecture

Eight roles. Each exists because its failure mode is distinct and its required expertise does not transfer cleanly from the others.

| ID | Role | Why it is a separate specialization |
|---|---|---|
| **A1** | Architecture & Integration Lead | Coordination, contract verification, and checkpoint sign-off must not be owned by any agent that also owns a subsystem it would be judging. Also the only role that touches `.dev/` documents. |
| **A2** | Backend / Django / DRF | Owns the synchronous request path and the admin surface. Distinct failure mode: broken API contracts and authorization gaps. |
| **A3** | Database & Data Integrity | The PRD's hardest correctness requirements — idempotency keys, single-award enforcement, transactional race-safe point award, row-level locking — are database-semantics problems, not general backend problems. Mis-assigning these is the single most expensive error available in this project. |
| **A4** | GitHub Integration | OAuth, read-side sync, webhook ingestion, reconciliation. Distinct external contract, distinct failure modes (rate limits, delivery gaps, signature verification). |
| **A5** | Async & Distributed Systems | Celery/Redis, queue isolation, bounded merge concurrency, retry policy, crash recovery, the contribution state machine. Concurrency correctness is a specialist discipline separate from request-path backend work. |
| **A6** | Frontend | React/TypeScript SPA. Consumes contracts, never defines them. |
| **A7** | QA, Security & Reliability | Must be able to **reject** a checkpoint independently of whoever built it. Cannot hold implementation ownership of the code it judges. |
| **A8** | DevOps, Deployment & Observability | Process topology, managed services, secrets, monitoring. Distinct from application development and concentrated almost entirely in M10. |

**Topology:**

```
                          ┌──────────────────────────────┐
                          │  A1  Architecture &          │
                          │      Integration Lead        │
                          │  contracts · checkpoints ·   │
                          │  conflict arbitration        │
                          └──────────────┬───────────────┘
                                         │ coordinates (does not implement for)
     ┌───────────────┬───────────────┬───┴───────────┬───────────────┐
     │               │               │               │               │
┌────▼────┐    ┌─────▼─────┐   ┌─────▼─────┐   ┌─────▼─────┐   ┌─────▼─────┐
│   A3    │    │    A4     │   │    A5     │   │    A2     │   │    A6     │
│Database │───▶│  GitHub   │──▶│  Async /  │──▶│ Backend / │──▶│ Frontend  │
│Integrity│    │Integration│   │  Pipeline │   │ DRF APIs  │   │   SPA     │
└────┬────┘    └─────┬─────┘   └─────┬─────┘   └─────┬─────┘   └─────┬─────┘
     │               │               │               │               │
     └───────────────┴───────┬───────┴───────────────┴───────────────┘
                             │
                   ┌─────────▼─────────┐        ┌────────────────────┐
                   │  A7  QA/Security  │        │  A8  DevOps /      │
                   │  verifies · may   │        │  Deployment /      │
                   │  reject checkpoint│        │  Observability     │
                   └───────────────────┘        └────────────────────┘

Arrows = contract flow (producer → consumer), not command authority.
```

**Agent bindings.** The project owner has indicated that Antigravity CLI and Kiro AI are available coding agents and that Claude is generating and maintaining the `.dev/` orchestration documents. No technical capability, model version, context limit, or integration beyond that is established in the project files, so no role is bound to a specific tool on that basis.

| Role | Binding |
|---|---|
| A1 — `.dev/` document authoring and maintenance | **Claude** (established: owner is using Claude for the internal orchestration documents) |
| A1 — integration/verification execution | **TBD** |
| A2, A3, A4, A5, A6, A7, A8 | **TBD** — candidate pool: Antigravity CLI, Kiro AI, Claude |

Bindings must be recorded by the project owner before execution begins, and recorded **here**, in this table. An agent must not self-assign a role. One tool instance may carry more than one role, but when it does it must still honor the review requirements in §9 — a role cannot review itself, and where a mandatory reviewer resolves to the same tool instance as the owner, that review escalates to A1 or the project owner instead.

---

## 4. Agent Registry

### A1 — Architecture & Integration Lead

| Field | Value |
|---|---|
| **Primary responsibility** | Verify dependencies, contracts, and module checkpoints; arbitrate ownership conflicts; coordinate handoffs; prevent scope expansion |
| **Secondary responsibility** | Maintain `.dev/` orchestration documents; route defects to owning agents; escalate unresolved decisions to the project owner |
| **Primary tools/technology** | Cross-cutting — no exclusive stack |
| **Owns** | `.dev/` (all orchestration documents); cross-subsystem integration verification; the contract registry in §8 |
| **May modify** | `.dev/` documents; nothing in `backend/` or `frontend/` except with explicit project-owner authorization for a specific integration fix |
| **Must NOT modify** | Any subsystem owned by A2–A8 by default. A1 **requests changes from the owner**; it does not silently take ownership or rewrite another agent's work |
| **Plan tasks owned** | M10-T8 |
| **Consumes** | All agents' handoff reports; `plan.md` checkpoints; `context.md` ambiguity register |
| **Produces / hands off** | Checkpoint verdicts; contract-change approvals; context updates; escalation records |
| **Required reviewers** | Project owner, for any change to established decisions or ambiguity status |
| **Stop and escalate when** | An ambiguity (AMB-1…AMB-12) blocks a task; PRD/plan/context conflict; a P0 requirement is at risk; an agent requests a contract break after downstream work began |
| **Parallelism** | Runs continuously alongside all agents (verification role) |

### A2 — Backend / Django / DRF

| Field | Value |
|---|---|
| **Primary responsibility** | Synchronous request path: DRF views, serializers, filtering, pagination, throttling, session auth enforcement, aggregated endpoints |
| **Secondary responsibility** | Django Admin surface (M8) |
| **Primary tools/technology** | Django, DRF |
| **Owns** | Backend API layer (views, serializers, routing, permissions, throttles); Django Admin configuration |
| **May modify** | Its own API layer; may **propose** model changes to A3 |
| **Must NOT modify** | Models/migrations (A3); Celery tasks or queue config (A5); GitHub client/webhook logic (A4); frontend (A6); deployment config (A8) |
| **Plan tasks owned** | M1-T1, M1-T5, M3-T1, M3-T2, M3-T3, M3-T4, M3-T5, M5-T4, M6-T6, M7-T1, M7-T2, M7-T3, M7-T4, M7-T5, M8-T1, M8-T2, M8-T3, M8-T4 |
| **Consumes** | A3 schema contract; A5 pipeline state semantics; A4 identity/session output from OAuth |
| **Produces / hands off** | **API contract** (endpoint, method, auth, params, response shape, error cases) to A6 — required before any dependent frontend task starts |
| **Required reviewers** | A3 for anything touching query shape, indexes, or write semantics; A7 before any module checkpoint involving auth, authorization, or public endpoints; A5 for admin actions that force state transitions |
| **Stop and escalate when** | A required field or endpoint is undefined (AMB-9, AMB-11); a contract change would break published frontend work; an authorization rule is ambiguous |
| **Parallelism** | Yes, once its module's schema dependency is satisfied |

### A3 — Database & Data Integrity

| Field | Value |
|---|---|
| **Primary responsibility** | Schema, migrations, constraints, indexes; all idempotency-key enforcement; transactional and race-safe point-award logic |
| **Secondary responsibility** | Review of every write path owned by other agents |
| **Primary tools/technology** | PostgreSQL, Django ORM/migrations |
| **Owns** | Models, migrations, constraints/indexes, the point-award transaction, daily-usage locking |
| **May modify** | Schema and data-integrity logic; may **require** changes in other agents' write paths that violate integrity guarantees |
| **Must NOT modify** | API views/serializers (A2); Celery task orchestration (A5); GitHub client code (A4); frontend (A6) |
| **Plan tasks owned** | M1-T2, M1-T4, M4-T2, M6-T5 |
| **Consumes** | PRD §15 schema specification; AMB-8/AMB-9/AMB-10 resolutions |
| **Produces / hands off** | **Schema contract** — entities, fields, constraints, indexes, and the guarantees each enforces — to A2, A4, A5 |
| **Required reviewers** | A1 for any schema change after M1 checkpoint; A7 for M6-T5 (race safety); A5 for locking behavior under concurrency |
| **Stop and escalate when** | A field is referenced by a requirement but undefined (AMB-9); the participant total-points mechanism is needed before AMB-10 is resolved; a config field for an emergency control does not exist (AMB-8) |
| **Parallelism** | Limited. Schema changes serialize against all consumers — see §7 |

### A4 — GitHub Integration

| Field | Value |
|---|---|
| **Primary responsibility** | GitHub OAuth, read-side sync, webhook ingestion and signature verification, event→domain mapping, reconciliation, rate-limit handling |
| **Secondary responsibility** | GitHub-facing review for any other agent's change that touches GitHub semantics |
| **Primary tools/technology** | GitHub REST API, OAuth, webhook signature verification |
| **Owns** | GitHub API client, OAuth flow, webhook receiver endpoint, sync and reconciliation logic |
| **May modify** | Its own integration layer |
| **Must NOT modify** | Models/migrations (A3); queue configuration or concurrency control (A5); unrelated API endpoints (A2); frontend (A6) |
| **Plan tasks owned** | M1-T3, M2-T1, M2-T2, M2-T3, M2-T4, M4-T1, M4-T5, M10-T6 |
| **Consumes** | A3 schema contract; A5 queue contract (which queue, task signature, enqueue semantics) |
| **Produces / hands off** | **Webhook/event contract** — which events are consumed, what each produces, dedup semantics, pause behavior — to A5 and A2 |
| **Required reviewers** | A7 for signature verification and anything on the webhook path; A3 for every write; A5 for enqueue/task boundaries |
| **Stop and escalate when** | Webhook registration model is unresolved (**AMB-1 blocks M4**); merge-bot interface is needed (AMB-2); OAuth email scope undecided (AMB-4); an issue-author field is required but undefined (AMB-9) |
| **Parallelism** | M2 can proceed alongside M3 once schema is stable |

### A5 — Async & Distributed Systems

| Field | Value |
|---|---|
| **Primary responsibility** | Celery/Redis topology, queue isolation, contribution state machine, validation pipeline, bounded merge concurrency, retry policy, crash-recovery sweep, pause-flag enforcement in tasks |
| **Secondary responsibility** | Concurrency review of any code that runs in or triggers a worker |
| **Primary tools/technology** | Celery, Redis, distributed-systems concurrency control |
| **Owns** | Celery app/queue configuration, task definitions, state-transition logic, merge concurrency gate, retry/backoff, heartbeat sweep |
| **May modify** | Task and pipeline code; queue configuration |
| **Must NOT modify** | Models/migrations (A3); point-award transaction internals (A3); API views (A2); GitHub client internals (A4); deployment process topology (A8 — though A5 specifies the requirement) |
| **Plan tasks owned** | M4-T3, M4-T4, M5-T1, M5-T2, M5-T3, M6-T1, M6-T2, M6-T3, M6-T4, M8-T5 |
| **Consumes** | A4 event contract; A3 schema contract (state fields, locking fields); `EventConfig` pause/concurrency flags |
| **Produces / hands off** | **Pipeline contract** — state vocabulary and transition triggers, queue names and priorities, concurrency gate semantics, retry classes, pause semantics — to A2 (status APIs, admin actions), A3 (point award trigger), A8 (worker topology), A7 (test targets) |
| **Required reviewers** | A3 for every state write and for concurrency interaction with locking; A7 for M6-T1/T4 and M5-T3; A1 for any change to queue topology after M6 |
| **Stop and escalate when** | Merge-bot interface is undefined (**AMB-2 blocks M6**); a pause control has no backing config field (AMB-8); priority/heartbeat fields are undefined (AMB-9) |
| **Parallelism** | **No** across M4→M5→M6 — these are strictly sequential (see §7) |

### A6 — Frontend

| Field | Value |
|---|---|
| **Primary responsibility** | React/TypeScript SPA: routing, data fetching, list/detail views, loading/empty/error states, status display, auth-gated routes |
| **Secondary responsibility** | Optional Ops panel (P1) if authorized |
| **Primary tools/technology** | React, TypeScript, Vite, Tailwind, React Router, TanStack Query |
| **Owns** | Everything under the frontend application; the typed API client and query hooks |
| **May modify** | Frontend code only |
| **Must NOT modify** | Any backend code, models, tasks, or deployment config. **Must not invent, stub, or assume a backend endpoint, field, or response shape that A2 has not published as a contract** |
| **Plan tasks owned** | M3-T6, M5-T5, M7-T6, M7-T7, M8-T6 |
| **Consumes** | A2 API contracts (mandatory prerequisite); A5 status vocabulary via A2 |
| **Produces / hands off** | UI surfaces; contract-gap reports back to A2 when a required field is missing |
| **Required reviewers** | A2 for contract conformance; A7 before checkpoint for XSS/authorization-surface concerns |
| **Stop and escalate when** | A required API contract is not yet published; the status-banner data source is undecided (**AMB-11 affects M7-T7**); a UI requirement implies an unlisted endpoint |
| **Parallelism** | Yes — but only behind a published, stable contract |

### A7 — QA, Security & Reliability

| Field | Value |
|---|---|
| **Primary responsibility** | Unit/integration/load/chaos/security testing; verification against PRD acceptance criteria; authority to **reject** a checkpoint |
| **Secondary responsibility** | Security review of auth, authorization, signature verification, input validation, secret handling |
| **Primary tools/technology** | Test frameworks, load-testing and fault-injection tooling (specific tooling: **TBD**) |
| **Owns** | Test suites, test fixtures, load/chaos scenarios, security test cases |
| **May modify** | Test code and fixtures. **May not implement production fixes** — it reports defects; the owning agent fixes them |
| **Must NOT modify** | Production application code in `backend/` or `frontend/`; schema; deployment config |
| **Plan tasks owned** | M9-T1, M9-T2, M9-T3, M9-T4, M9-T5, M10-T7 |
| **Consumes** | All agents' handoffs; PRD §24 testing strategy and §28 acceptance criteria |
| **Produces / hands off** | Test results; defect reports routed through A1; checkpoint verdicts (pass/reject with evidence) |
| **Required reviewers** | A1 for checkpoint verdicts that block a module |
| **Stop and escalate when** | A P0 acceptance criterion cannot be verified; a defect requires a design decision rather than a fix |
| **Parallelism** | Writes tests alongside M1–M8 development; M9 is a dedicated pass requiring M1–M8 complete |

### A8 — DevOps, Deployment & Observability

| Field | Value |
|---|---|
| **Primary responsibility** | Production deployment, process topology, managed data stores, secret management, error tracking and uptime monitoring |
| **Secondary responsibility** | Provisioning environments A7 needs for load/chaos testing |
| **Primary tools/technology** | Hosting platform (**TBD** — not established in project files), Gunicorn/Celery process configuration, CDN, monitoring |
| **Owns** | Deployment configuration, environment/secret configuration, process/worker topology, monitoring wiring |
| **May modify** | Deployment and infrastructure configuration |
| **Must NOT modify** | Application logic of any kind; schema; test assertions |
| **Plan tasks owned** | M10-T1, M10-T2, M10-T3, M10-T4, M10-T5 |
| **Consumes** | A5 worker/queue topology requirements; A2 process sizing inputs; A7 load-test results for tuning |
| **Produces / hands off** | Deployed environments; monitoring endpoints; confirmation that no secret resides in the repository |
| **Required reviewers** | A7 for secrets and monitoring; A5 for worker topology; A1 before go-live |
| **Stop and escalate when** | Hosting/managed-service choices are not yet decided; a required secret (merge-bot credential) does not exist because AMB-2 is unresolved |
| **Parallelism** | Preparation work may run alongside M9; deployment itself follows M9 |

---

## 5. Ownership Boundaries

Confirmed repository structure only. **No specific filenames below are asserted to exist** — the actual contents of `backend/` and `frontend/` are unverified (see `context.md` §9). Ownership is expressed by subsystem; an agent resolves a subsystem to actual paths by inspecting the repository, not by assuming a conventional layout.

| Area | Primary owner | Notes |
|---|---|---|
| `.dev/` | **A1** | Gitignored internal orchestration. No other agent modifies these files during implementation. Never exposed by the application |
| `.gitignore` | **A8** | Change requires A1 approval. `.dev/` exclusion must never be removed |
| `backend/` — models, migrations, constraints | **A3** | Exclusive. Others propose, A3 implements |
| `backend/` — DRF views, serializers, routing, permissions, throttling | **A2** | |
| `backend/` — Django Admin configuration | **A2** | A5 reviews any admin action that forces a state transition |
| `backend/` — GitHub client, OAuth, webhook receiver, sync/reconciliation | **A4** | |
| `backend/` — Celery app, queue config, tasks, state machine, merge gate | **A5** | |
| `backend/` — point-award transaction and daily-usage locking | **A3** | Lives in backend but is data-integrity territory; A5 reviews the trigger path |
| `backend/` — Django settings/configuration | **A2** (custodian) | Shared file — see §10 |
| `backend/` — tests and fixtures | **A7** | |
| `frontend/` — all application code, API client, query hooks | **A6** | |
| Deployment, environment, secret, and process configuration | **A8** | |

Unclaimed area rule: if work falls into no listed area, the agent does **not** claim it. It escalates to A1, who assigns ownership and records the assignment here.

---

## 6. Task-to-Agent Assignment

Exactly one primary owner per task. "Support" contributes input; "Review" must sign off before the task is reported complete. Task IDs are from `plan.md` and are not redefined here. Dependencies are abbreviated — `plan.md` is authoritative.

| Task | Primary | Review / Support | Depends on | Parallel? | Handoff produced |
|---|---|---|---|---|---|
| M1-T1 | **A2** | Support A1, A6 | — | — | Repository structure; stack confirmation |
| M1-T2 | **A3** | Review A2, A1 | M1-T1 | No — blocks nearly everything | **Schema contract** → A2, A4, A5 |
| M1-T3 | **A4** | Review A2 (session), A7 (security) | M1-T2 | After M1-T2 | Identity/session behavior → A2, A6 |
| M1-T4 | A3 | Review A2, A1 | M1-T2 | With M1-T3 | Config field inventory → A5, A2 |
| M1-T5 | A2 | Review A8 | M1-T1 | Yes | Health semantics → A8 |
| M2-T1 | A4 | Review A3 (writes) | M1-T2 | — | — |
| M2-T2 | A4 | Review A3 | M2-T1 | No (after T1) | Issue data availability → A2, A5 |
| M2-T3 | A4 | Review A3 | M2-T2 | After T2 | — |
| M2-T4 | A4 | Review A5 (queue wiring) | M2-T1, M2-T2 | After T1/T2 | Sync task contract → A5, A8 |
| M3-T1 | A2 | Review A3 (query/index) | M1-T2, M2-T1 | With M3-T3 | **API contract** → A6 |
| M3-T2 | A2 | Review A3 | M3-T1 | After T1 | API contract → A6 (**AMB-9: slug**) |
| M3-T3 | A2 | Review A3 (filter indexes) | M1-T2, M2-T2 | With M3-T1 | **API contract** → A6 |
| M3-T4 | A2 | Review A3 | M3-T3 | After T3 | API contract → A6 |
| M3-T5 | A2 | **Review A7** | M3-T1, M3-T3 | Yes | Throttle policy → A7, A8 |
| M3-T6 | **A6** | Review A2 (conformance), A7 | M3-T1…T4 **published** | Only behind published contracts | UI surfaces |
| M4-T1 | **A4** | **Review A7** (signature), A2 (view) | M1-T2 | No — critical path | Webhook endpoint contract → A5 |
| M4-T2 | **A3** | Review A4, A7 | M4-T1 | No | **Dedup guarantee** → A4, A5 |
| M4-T3 | **A5** | Review A4 (event semantics), **A3** (write idempotency) | M4-T1, M4-T2 | No | **Event→domain contract** → A2 |
| M4-T4 | **A5** | Review A4 (pause/event semantics), A2 | M4-T3, M1-T4 | No | Pause semantics → A4, A8 |
| M4-T5 | A4 | Review A5 (beat scheduling) | M2-T1, M2-T2 | Yes (off critical path) | Reconciliation contract → A5, A7 |
| M5-T1 | **A5** | **Review A3** (state writes), A2, A1 | M4-T3 | No — critical path | **Pipeline/state contract** → A2, A3, A6, A7 |
| M5-T2 | A5 | Review A4 (GitHub semantics), A3 | M5-T1 | No | Validation rule set → A7 (**AMB-5, AMB-9**) |
| M5-T3 | A5 | Review A3 (lock fields), **A7** | M5-T1 | No | Recovery guarantee → A7 (**AMB-9: heartbeat**) |
| M5-T4 | A2 | Review A5 (status semantics), **A7** (object-level auth) | M5-T1 | After T1 | **API contract** → A6 |
| M5-T5 | A6 | Review A2, A5 (status vocabulary) | M5-T4 published | Behind contract | UI surfaces |
| M6-T1 | **A5** | **Review A7**, A1 | M5-T1, M1-T4 | No — critical path | **Concurrency gate contract** → A7, A8 |
| M6-T2 | A5 | Review A4 (merge confirmation), A3 | M6-T1 | No | Merge-state transitions → A3 (award trigger) |
| M6-T3 | A5 | Review A3 (priority field) | M6-T1 | After T1 | Ordering guarantee (**AMB-9**) |
| M6-T4 | A5 | Review A4 (rate-limit classes), **A7** | M6-T2 | After T2 | Retry contract → A7 |
| M6-T5 | **A3** | **Review A7 + A5 + A1** — strongest review in the project | M6-T2 | No | **Point-award guarantee** → A2, A7 (**AMB-3, AMB-10**) |
| M6-T6 (P1) | A2 | Review A3 (ledger), A7 (audit) | M6-T5 | Deferrable | Admin adjustment path |
| M7-T1 | A2 | Review A3 (index/cache), A5 (refresh task) | M6-T5 | Yes | **API contract** → A6 |
| M7-T2 | A2 | Review A5, A1 | M7-T1, M1-T4 | Yes | Freeze semantics → A6, A7 |
| M7-T3 | A2 | Review A3 (aggregation cost) | M6-T5, M5-T4 | Yes | **API contract** → A6 |
| M7-T4 | A2 | **Review A7** (field exposure) | M6-T5 | Yes | API contract → A6 |
| M7-T5 (P1) | A2 | Review A5 (beat refresh) | M6-T5 | Deferrable | API contract → A6 |
| M7-T6 | A6 | Review A2, A7 | M7-T1…T5 published | Behind contracts | UI surfaces |
| M7-T7 | A6 | Review A2, A1 | Status source decided | **Blocked by AMB-11** | Banner behavior |
| M8-T1 | A2 | Review A4 (sync-now actions), A3 | M1, M2 | Yes | Admin capability set |
| M8-T2 | A2 | **Review A5** (forced transitions must respect the state machine), A3 (audit) | M5, M6 | Yes | Admin action set → A7 |
| M8-T3 | A2 | Review A3, A1 | M1-T4 | Yes | Config surface (**AMB-8**) |
| M8-T4 | A2 | Review A3 | M1-T2 | Yes | Audit visibility → A7 |
| M8-T5 | **A5** | Review A2 (view-side checks), A1, A7 | M5, M6, M4-T4 | No — touches every task | **Pause/resume guarantee** → A7, A8 (**AMB-8**) |
| M8-T6 (P1) | A6 | Review A2, A1 | M8-T1…T5 | Deferrable | Ops panel (**AMB-6**) |
| M9-T1 | **A7** | Support A2, A3, A4, A5 | M1–M8 | Written alongside M1–M8 | Unit results |
| M9-T2 | A7 | Support A5, A4 | M1–M8 | Yes with T1 | Integration results |
| M9-T3 | A7 | Support A8 (environment), A2 | M1–M8 | Yes | Load results → A8 (tuning) |
| M9-T4 | A7 | Support A5, A8 | M1–M8 | Yes | Chaos results → A5 |
| M9-T5 | A7 | Support A4, A2 | M1–M8 | Yes | Security findings |
| M9-T6 | **A7** | Fixes implemented by each **owning** agent; A7 re-verifies; A1 coordinates routing | M9-T1…T5 | Coordinated | Defect routing; fix verification |
| M10-T1 | A8 | Review A5 (worker topology), A2 | M9, M10-T3, M10-T4 | No | Deployed backend |
| M10-T2 | A8 | Review A6 | M9 | May run in parallel with M10-T1 | Deployed frontend |
| M10-T3 | A8 | Review A3 (durability) | M9 | Before M10-T1 | Managed stores |
| M10-T4 | A8 | **Review A7** | M9, M10-T3 | Before M10-T1 | Secret inventory |
| M10-T5 | A8 | Review A7 | M10-T1, M10-T2 | Yes | Monitoring live |
| M10-T6 | **A4** | Support A8, A3 | M10-T1, M10-T3 | No | Production data at scale |
| M10-T7 | **A7** | Support A1, all agents on defects | M10-T1…T6 | No | Go/no-go evidence |
| M10-T8 | A1 | All agents on assigned fixes | M10-T7 | — | Launch readiness |

**Coverage check:** all 58 plan tasks are assigned, each to exactly one primary owner.

---

## 7. Parallel Execution Matrix

Parallel work is permitted only when dependencies are genuinely satisfied, ownership does not overlap, and the consumed contract is already published and stable.

| Combination | Allowed? | Condition |
|---|---|---|
| A3 schema work (M1-T2) ∥ anything else | **No** | Schema is the universal prerequisite. Everything waits |
| A4 sync (M2) ∥ A2 read APIs (M3) | **Yes** | After M1-T2 and M2-T2; different subsystems, shared schema is stable |
| A2 read APIs (M3-T1/T3) ∥ each other | Yes | Same agent, independent endpoints |
| A6 frontend (M3-T6) ∥ A2 backend (M3) | **Only behind published contracts** | A6 starts a view only after its endpoints are published and stable |
| **M4 ∥ M5** | **No** | Critical path. State machine consumes the event contract |
| **M5 ∥ M6** | **No** | Critical path. Merge queue consumes the state machine |
| **M4 ∥ M5 ∥ M6 in any combination** | **Forbidden** | This dependency is real, not an artifact of scheduling. Agents may not "parallelize" it away |
| A4 reconciliation (M4-T5) ∥ M5 work | Yes | Off the critical path; different subsystem |
| A2 status API (M5-T4) ∥ A5 pipeline (M5-T1/T2/T3) | Yes | After M5-T1 publishes the state vocabulary |
| A3 point award (M6-T5) ∥ A5 merge queue (M6-T1…T4) | **No** | M6-T5 consumes merge-state transitions from M6-T2 |
| A2 leaderboard/dashboard (M7) ∥ A2 admin (M8) | Yes | Plan permits M8 to buffer into M7's window; sequence within A2 |
| A5 pause wiring (M8-T5) ∥ active M5/M6 development | **No** | It edits the top of every task other agents own. Serialize it |
| A7 test authoring ∥ M1–M8 development | **Yes — expected** | Per-module tests are written during development, not deferred |
| A7 M9 dedicated pass ∥ feature development | **No** | M9 requires M1–M8 complete |
| A8 deployment prep ∥ M9 | Yes | Environment provisioning; production deploy still follows M9 |
| A6 frontend ∥ A6 frontend (two instances) | **No** | Single owner per subsystem. Do not split frontend across concurrent agents |
| Any two agents editing the same file | **Never** | See §10 |

---

## 8. Contract & Handoff Rules

A **contract** is a published, written statement of an interface another agent depends on. Development is backend-first: contracts flow downstream, and a consumer never invents what its producer has not published.

| # | Producer → Consumer | Contract contents | Rule |
|---|---|---|---|
| C1 | **A3 → A2, A4, A5** | Entities, fields, constraints, indexes, and the guarantee each enforces | No agent writes to a table before the schema contract covers it. Schema changes after M1 checkpoint require A1 approval and notification to every consumer |
| C2 | **A4 → A5, A2** | Which GitHub events are consumed, what each produces, dedup semantics, signature requirements, pause behavior | A5 does not infer event semantics from payload shape; it consumes this contract |
| C3 | **A5 → A2, A3, A6, A7** | State vocabulary and transition triggers, queue names/priorities, concurrency gate semantics, retry classes, pause semantics | A2 maps states to API/UI status; A3 receives the point-award trigger; nobody invents a state |
| C4 | **A5 → A3** | The precise event that triggers a point award and the state guarantees at that moment | A3 owns the award transaction; A5 owns what fires it. Neither reaches into the other |
| C5 | **A2 → A6** | Endpoint, method, auth, parameters, response shape, error cases, pagination behavior | **A6 must not invent, stub, or assume an endpoint or field.** If something is missing, A6 files a gap report and waits |
| C6 | **A2 ⇄ A6 (change protection)** | — | **A2 must not break a published contract after A6 has begun consuming it.** A break requires: A1 approval, notification to A6, and a coordinated change. Additive, non-breaking changes are fine |
| C7 | **A5 → A8** | Worker/queue topology and concurrency requirements | A8 deploys to the requirement; it does not redesign the topology |
| C8 | **All → A7** | Handoff report per §14 | A7 verifies against PRD acceptance criteria, not against the implementer's own description of success |
| C9 | **A7 → A1 → owning agent** | Defect reports with reproduction and evidence | A7 reports; the owning agent fixes; A7 re-verifies. **A7 never fixes production code itself** |
| C10 | **A1 → all** | Checkpoint verdicts, contract approvals, ambiguity status | A1 coordinates; it does not implement on another agent's behalf without explicit authorization |

**Contract publication:** a contract is "published" only when it is written down and handed to the consumer in a handoff report (§14). Verbal agreement, code-as-documentation, or "read my implementation" does not count. A consumer waiting on an unpublished contract escalates rather than guessing.

---

## 9. Review & Verification Model

Review is proportional to blast radius, not to effort. Cosmetic UI work gets light review; correctness work on the critical path gets the heaviest review in the project.

| Change category | Mandatory reviewers | Rationale |
|---|---|---|
| Schema, constraints, indexes, migrations | A3 (owner) + A1 | Every consumer depends on these |
| **Point-award transaction, daily-limit logic (M6-T5)** | **A7 + A5 + A1** | Race safety is a stated P0 correctness property; a silent bug here corrupts the leaderboard |
| **Merge concurrency control (M6-T1), retry policy (M6-T4)** | **A7 + A1** | Bounded concurrency is an explicit acceptance criterion |
| **State machine & crash recovery (M5-T1, M5-T3)** | **A3 + A7** | Lost or stuck contributions are unrecoverable trust damage |
| Webhook path (M4-T1…T4) | **A7** (signature/security) + A3 (idempotency) | Signature verification is mandatory; dedup is a P0 guarantee |
| Pause/resume wiring (M8-T5) | A2 + A1 + A7 | Touches every task; a missed check silently defeats an emergency control |
| GitHub-facing changes anywhere | A4 | Rate limits, delivery semantics, redelivery behavior |
| Any write path owned by A2/A4/A5 | A3 | Integrity guarantees must hold at every write |
| Public API endpoints, auth, authorization | A7 before checkpoint | Authorization gaps are the highest-likelihood security defect here |
| Frontend views | A2 (contract conformance) + A7 before checkpoint | Prevents drift from the published contract |
| Deployment, secrets, monitoring | A7 (secrets) + A5 (topology) + A1 (go-live) | Secret leakage and wrong worker topology are both launch-blocking |
| Admin actions that force state transitions | **A5** | An admin action must not bypass state-machine invariants |

**Rejection authority.** A7 may reject a module checkpoint. A rejection is binding: the module is not complete, regardless of how much code exists. A7 must supply reproducible evidence. Disputes go to A1, then to the project owner. A7 does not gain implementation ownership by rejecting — it reports, the owner fixes.

---

## 10. Shared File / Conflict Resolution Rules

The failure mode this section prevents: two agents editing models while a third changes serializers and a fourth changes the API client, all concurrently, with no coordination.

**Baseline rule: one owner per file. Others propose; the owner implements.**

| Shared area | Primary owner | Who may request changes | Rule |
|---|---|---|---|
| Models / migrations | **A3** | A2, A4, A5 | Never edited by a non-owner. Requests go to A3 with the requirement and its PRD/plan source. After M1 checkpoint, changes also need A1 approval |
| Serializers / API contracts | **A2** | A6 (gap reports), A3 (field semantics) | Breaking changes after A6 begins consuming require C6 coordination |
| Backend settings/configuration | **A2** (custodian) | A5 (Celery/broker settings), A8 (environment, deployment-facing settings), A4 (integration settings), A7 (test settings) | High-conflict file. One change at a time. Announce before editing; A2 arbitrates; A1 arbitrates if A2 is a party |
| Celery app / queue configuration | **A5** | A8 (deployment implications), A4 (enqueue needs) | A8 deploys to A5's topology; it does not alter the topology |
| Authentication / session middleware | **A2** | A4 (OAuth flow), A7 (security findings) | Changes require A7 review |
| Shared TypeScript types / API client | **A6** | A2 (contract updates) | A2 publishes the contract; A6 implements the types. A2 does not write frontend types |
| Test fixtures | **A7** | Any agent may request a fixture | Only A7 edits them, so production agents cannot weaken assertions |
| Deployment / environment configuration | **A8** | A5 (topology), A7 (secrets/monitoring) | No application agent edits deployment config |
| `.gitignore` | **A8** | A1 | The `.dev/` exclusion is never removed |
| `.dev/` documents | **A1** | All agents, via handoff reports | Not modified during normal implementation |

**Coordination protocol for a shared file:**
1. Consumer states the need with its task ID and its PRD/plan justification.
2. Owner confirms the change is in scope for that task (and not future-module work).
3. Owner implements, or explicitly delegates in writing for that one change.
4. Owner records the change in its handoff; affected consumers are notified.
5. No concurrent edits to the same file by two agents, ever — serialize instead.

**Deadlock rule:** if two agents each need a change in the other's area for the same task, neither proceeds unilaterally. A1 sequences the work.

---

## 11. Skills / Capability Map

These are **required capabilities**, not installed skill names. No skill package, plugin, or tool integration is asserted to exist.

| Agent | Required capability | Actual installed skill |
|---|---|---|
| A1 | Systems architecture review; dependency and contract verification; technical documentation maintenance | **TBD** (Claude currently performs the `.dev/` documentation function) |
| A2 | Django / DRF: viewsets, serializers, filtering, pagination, throttling, session auth, Django Admin customization | **TBD** |
| A3 | PostgreSQL and relational data integrity: constraints, indexes, transaction isolation, row-level locking, migration safety | **TBD** |
| A4 | GitHub REST API; OAuth Authorization Code flow; webhook signature verification; rate-limit-aware pagination | **TBD** |
| A5 | Celery/Redis distributed task processing; queue isolation and priority; concurrency limiting; retry/backoff design; state-machine implementation; crash recovery | **TBD** |
| A6 | React + TypeScript; Vite; Tailwind; React Router; TanStack Query; loading/empty/error state patterns | **TBD** |
| A7 | Test design (unit/integration); load testing; fault injection; web application security testing | **TBD** |
| A8 | Production deployment of Python web applications; managed database/cache provisioning; secret management; error tracking and uptime monitoring | **TBD** |

**Rule:** an agent must not be assigned a task requiring a capability it does not have. If a binding lacks the capability its role requires, that is an escalation to the project owner — not a reason to hand the task to a general-purpose agent and hope. Concurrency correctness (A5) and data integrity (A3) in particular must not be delegated to a generalist.

---

## 12. Escalation & Open-Question Handling

`context.md` §11 records unresolved ambiguities. **No agent may resolve any of them.** An agent may not "make a reasonable assumption and continue."

**When a task is blocked:**
1. Stop. Do not implement a workaround, a placeholder, or a guess.
2. Identify the blocker by its AMB ID.
3. Identify the affected task ID and what the blocker prevents.
4. State precisely what decision is required — not a recommendation presented as a decision.
5. Escalate to the project owner through A1.
6. Resume only after the decision is recorded in `context.md`.

| Ambiguity | Blocks / affects | Owning agent at the point of impact |
|---|---|---|
| AMB-1 webhook registration model | **Blocks M4** (start) | A4 |
| AMB-2 merge bot interface | **Blocks M6** (start); also M10-T4 credentials | A5 (with A8) |
| AMB-3 deferred points policy | Affects M6-T5 behavior and its UI copy | A3 (with A6) |
| AMB-4 OAuth email scope | Affects M1-T3 scope request | A4 |
| AMB-5 trivial/low-effort PR detection | Bounds M5-T2 — **do not implement diff scoring** | A5 |
| AMB-6 Django Admin vs. custom Ops panel | Affects whether M8-T6 is built at all | A6 |
| AMB-7 post-event retention/export | Unscoped; would slot into M9/M10 buffer only if authorized | A1 |
| AMB-8 point-awarding emergency-control field | Affects M1-T4, M8-T3, M8-T5 — **do not invent the field** | A3, A5 |
| AMB-9 referenced-but-undefined schema fields | Affects M1-T2, M3-T2, M5-T2, M5-T3, M6-T3, M8-T3 | A3 |
| AMB-10 participant total-points update mechanism | Affects M6-T5 and M7-T1 | A3 |
| AMB-11 status endpoint | **Blocks M7-T7** | A6 (with A2) |
| AMB-12 root working-directory naming | Affects path assumptions for every agent | A1 |

AMB-13 is resolved: the canonical agent-map filename is `.dev/awsmap.md`.

**Also escalate when:** PRD, plan, and context conflict; a P0 requirement is at risk of being cut or downgraded; a contract break is requested after downstream consumption began; a task appears to require a technology the PRD rejected; a required capability is missing from the assigned binding.

---

## 13. Git / Change Safety

No branching strategy is established in the project files, so none is invented here. If one is needed, it will be established in `continue.md`. These principles apply regardless of strategy:

1. **One logical task per change set** where practical. A change set should be attributable to a single plan task ID.
2. **Inspect current repository and git state before modifying anything.** Never assume the working tree matches your last known state.
3. **Never overwrite, reset, or revert another agent's unreviewed work** without explicit project-owner authorization.
4. **No broad reformatting or refactoring** outside the assigned task's scope — it destroys reviewability and hides real changes.
5. **Never commit `.dev/` contents.** The directory is gitignored deliberately; do not remove the exclusion, and do not copy `.dev/` content into tracked files.
6. **Never commit secrets** — no tokens, client secrets, webhook secrets, or connection strings in tracked files, in any form, including tests and fixtures.
7. **Do not integrate your own work.** A1 verifies before integration.
8. If a change set has grown beyond its task, stop and split it rather than reporting it as one task.

---

## 14. Standard Agent Handoff Format

Every completed task produces this report. **"Done" means the task's observable outcome and its required validation are satisfied — not that code was written.**

```
HANDOFF
Agent:              A#
Task:               M#-T#
Status:             COMPLETE | BLOCKED | PARTIAL

What changed:       <concise description of the actual change>
Files changed:      <paths, as verified in the repository>

Tests run:          <what was executed>
Test results:       <pass/fail with specifics — not "tests pass">

Contract changes:   API / schema / pipeline contract published or modified.
                    NONE if nothing downstream is affected.
Consumers notified: <agent IDs, or NONE>

Reviews obtained:   <reviewer agent IDs + verdicts, per §9>

Known limitations:  <what this does not do>
Unresolved issues:  <including any AMB blockers encountered>
Follow-up tasks:    <existing plan task IDs only — do not invent task IDs>

Checkpoint status:  Does this satisfy the task's validation criteria in plan.md?
                    YES / NO / NOT APPLICABLE (task is not a module checkpoint)
                    If NO: what remains.
```

A report claiming COMPLETE without required reviews obtained, or without test results, is not accepted by A1.

---

## 15. Module-Level Collaboration Flow

```
M1  A2 scaffolds ▸ A3 schema ▸ A4 OAuth ▸ A3 config ▸ A2 health
    A3's schema contract gates everything downstream. Resolve AMB-9/AMB-8 first.

M2  A4 owns end to end, A3 reviews every write. A5 reviews queue wiring.

M3  A2 builds and PUBLISHES contracts ▸ then A6 consumes. Never the reverse.
    A3 reviews query shape against indexes. A7 reviews throttling.

━━━━━━━━━━━━━━ CRITICAL PATH — STRICTLY SEQUENTIAL ━━━━━━━━━━━━━━

M4  A4 (endpoint, event semantics, reconciliation) ▸ A3 (dedup) ▸ A5 (queue processing, pause)
    ▸ AMB-1 must be resolved BEFORE this module starts
    ▸ A7 reviews signature verification; A3 owns the dedup guarantee
    ▸ publishes the EVENT CONTRACT
                              │
                              ▼
M5  A5 (state machine, validation, crash recovery) + A2 (status API) + A6 (status UI)
    ▸ consumes A4's event contract
    ▸ A3 reviews every state write; A7 reviews recovery
    ▸ publishes the PIPELINE CONTRACT
                              │
                              ▼
M6  A5 (merge gate, transitions, ordering, retry) ▸ A3 (point award)
    ▸ AMB-2 must be resolved BEFORE this module starts
    ▸ M6-T5 receives the project's strongest review: A7 + A5 + A1
    ▸ ownership split is deliberate: A5 owns WHAT FIRES the award,
      A3 owns the AWARD TRANSACTION. Neither reaches into the other.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

M7  A2 builds and publishes contracts ▸ A6 consumes. A3 reviews leaderboard
    index/cache correctness. M7-T7 blocked pending AMB-11.

M8  A2 owns the admin surface; A5 owns pause wiring (M8-T5) because it edits
    the top of every task A5 owns. A5 reviews any admin action that forces a
    state transition. M8-T6 is P1 and deferrable (AMB-6).

M9  A7 leads. Owning agents fix their own defects; A1 routes; A7 re-verifies.
    A7 may reject a checkpoint. A7 does not fix production code.

M10 A8 provisions stores/secrets ▸ deploys to A5's topology ▸ A4 runs the production sync ▸ A7 runs the
    smoke test and supplies go/no-go evidence ▸ A1 holds the buffer.
```

---

## 16. Checkpoint Ownership

A module is complete only when its `plan.md` checkpoint criteria are observably met. The verifier is never solely the agent that built the module.

| Module | Checkpoint verifier | Mandatory co-signer | Notes |
|---|---|---|---|
| M1 | A1 | A3 (schema), A7 (OAuth security) | Schema correctness gates everything after |
| M2 | A1 | A3 (data written correctly) | Full-scale sync is M10-T6, not here |
| M3 | A1 | A7 (throttling/auth), A6 (contract conformance) | |
| M4 | **A7** | A1, A3 (dedup guarantee) | Signature + idempotency are P0 acceptance criteria |
| M5 | **A7** | A1, A3 (state integrity) | Crash recovery must be demonstrated, not asserted |
| M6 | **A7** | A1, A3, A5 — all three | Highest-risk module. Concurrency cap and award-exactly-once must be demonstrated under concurrency |
| M7 | A1 | A7 (consistency under load), A3 (cache/index) | |
| M8 | **A7** | A1, A5 (pause effectiveness) | Each control independently toggleable, no restart |
| M9 | **A7** | A1 | A7 leads; A1 confirms defect closure |
| M10 | **A7 + A1 jointly** | Project owner for go/no-go | Full PRD §28 acceptance checklist in production |

---

## 17. Anti-Overlap Rules

Agents must not:

1. **Implement work outside their assigned task ID**, even if the fix is small and obviously correct. Report it; let the owner do it.
2. **Implement a future module early** without explicit authorization.
3. **Modify another agent's owned subsystem** because it could be improved.
4. **Edit a shared file concurrently with another agent.** Serialize through §10.
5. **Invent a schema field, endpoint, config flag, or state** that the PRD does not establish — particularly around EventConfig and emergency controls (AMB-8, AMB-9).
6. **Invent a backend API** (A6) or **break a published contract** (A2) without the §8 process.
7. **Resolve an open question** (AMB-1…AMB-12) independently.
8. **Add a technology the PRD rejected**, or add any technology because it is conventional for this kind of system.
9. **Introduce architecture changes** without approval; no agent silently changes another agent's architectural decision.
10. **Promote P1/P2 work to P0**, or downgrade/drop P0 work. Scope cuts follow `plan.md` §5 order and must be recorded.
11. **Create abstractions without demonstrated need.**
12. **Duplicate functionality** another agent already owns.
13. **Introduce a synchronous GitHub or merge-bot call into a user-facing request path** — this is an architectural invariant, not a preference.
14. **Report a task complete** without required reviews and validation evidence.
15. **Modify `.dev/` files** during implementation, or expose `.dev/` contents through the application.
16. **Weaken a test or fixture** to make a task pass. Only A7 edits tests; a failing test is a defect report, not an obstacle.
17. **Claim a repository file or capability exists** without verifying it.

---

## 18. Quick Start for an Assigned Agent

1. **Read `PRD.md`** — authoritative for requirements, priorities, and acceptance criteria.
2. **Read `.dev/plan.md`** — locate your assigned task ID, its dependencies, expected outcome, and validation criteria.
3. **Read `.dev/context.md`** — current state, established decisions, constraints, and the ambiguity register.
4. **Read this file** — confirm you are the primary owner of the task, know exactly which subsystem you may modify, and know your mandatory reviewers.
5. **Inspect the repository.** Verify actual state. Do not assume any file exists.
6. **Verify dependencies are satisfied in reality**, not merely scheduled.
7. **Check §12** — if an AMB blocker affects your task, **stop and escalate**. Do not assume.
8. **Confirm your input contracts are published.** If a contract you depend on is not written down, request it; do not guess.
9. **Execute only your assigned task**, within your ownership boundary, respecting the constraints in `context.md` §8.
10. **Test** against the task's validation criteria.
11. **Obtain required reviews** per §9.
12. **Produce the handoff report** per §14 — honestly, including partial completion.
13. **Publish any contract** your consumers need, and notify them.
14. **Stop.** Do not begin the next task on your own initiative; `continue.md` will govern task selection.
