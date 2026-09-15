# HackIT CommitRush — Execution Workflow (`continue.md`)

---

## 1. Purpose

**This document controls:** the operational loop an AI coding agent follows to select, execute, validate, and hand off one unit of work safely, and to decide what happens next.

**This document does NOT control:**
- Product requirements or acceptance criteria — `PRD.md`
- Execution order, task IDs, dependencies, or checkpoints — `.dev/plan.md`
- Current implementation state, decisions, or ambiguities — `.dev/context.md`
- Agent ownership, review requirements, or contracts — `.dev/awsmap.md`

`continue.md` does not repeat what those documents contain. It tells an agent **how** to use them correctly. Where anything here appears to conflict with PRD.md, plan.md, context.md, or awsmap.md, **those win and this document is wrong** — stop and escalate rather than acting on the conflicting instruction here.

---

## 2. Authority & Required Reading Order

```
1. PRD.md            — WHAT the product must do
2. .dev/plan.md       — WHAT to build and in WHAT ORDER
3. .dev/context.md    — WHAT currently IS true
4. .dev/awsmap.md     — WHO does WHAT
5. .dev/continue.md   — HOW to execute all of the above     [this file]
```

An agent reads all four upstream documents, **in this order, in full**, before touching the repository — every session, not only the first one. Do not rely on a memory of having read them previously; documents may have changed.

---

## 3. Agent Startup Procedure

On starting any session, in order:

1. Read `PRD.md`.
2. Read `.dev/plan.md`.
3. Read `.dev/context.md` — pay particular attention to §3 (current state), §9 (implementation reality), and §11 (open ambiguities).
4. Read `.dev/awsmap.md` — identify your agent ID and its ownership boundary, forbidden modifications, and review requirements.
5. Proceed to the Repository Reality Check (§4). Do not select a task before completing it.

**Never assume, at startup:**
- That any module or task described as "planned" in `context.md` is implemented.
- That the repository matches the state described in your last session.
- That no other agent has touched the repository since you last worked.
- That an ambiguity listed as open in `context.md` §11 has been resolved, unless `context.md` itself now says so.
- That you are the only agent with a task currently in progress.

---

## 4. Repository Reality Check

Before selecting a task, establish ground truth. Documents describe intent and history; the repository is the only source of *current fact*.

1. **Inspect the actual directory structure and file contents** relevant to your candidate task's ownership area (per `awsmap.md` §5). Do not infer contents from what a Django/React project "usually" has.
2. **Inspect git status and recent history** — uncommitted changes, unmerged work, or commits since `context.md` was last updated all indicate work `context.md` may not yet reflect.
3. **Cross-check `context.md` §9 (Implemented / In Progress / Planned / Unknown)** against what you actually observe. If they disagree, `context.md` is stale — do not silently trust it, and do not silently trust your own read either. Record the discrepancy (see §15) before proceeding.
4. **Detect work already performed by another agent.** Look for commits, branches, or handoff reports (§14) not yet reflected in `context.md`. If found, treat that work as authoritative for its stated scope and do not redo or overwrite it.
5. If the repository state cannot be determined with confidence (e.g., ambiguous partial implementation, conflicting evidence), **stop** — this is a Stop Condition (§21), not a judgment call to resolve by guessing.

**Rule: "scheduled" ≠ "completed."** A task's presence and ordering in `plan.md` is a schedule, not a status report. A task is only "done" per the Definition of Done in §22, evidenced by a handoff report (§14) and, where applicable, by what you directly observe in the repository.

---

## 5. Task Selection Algorithm

A task from `plan.md` (M1-T1 through M10-T8 — no other task IDs exist and none are invented here) is **eligible for a given agent** only when ALL of the following hold:

1. **Dependency satisfaction is real, not scheduled.** Every task/module `plan.md` lists as a dependency is verified complete per §4 and §22 — not merely earlier in the sequence.
2. **No open ambiguity blocks it.** Cross-check the task against `context.md` §11 and `awsmap.md` §12. If an AMB ID affects this task and remains unresolved, the task is **not eligible** (see §7).
3. **The requesting agent is the task's primary owner** per `awsmap.md` §6. An agent does not pick up a task assigned to another agent merely because it is idle or the task looks easy.
4. **Required upstream contracts are published**, per `awsmap.md` §8 — not merely implied by another agent's code. If a contract this task depends on has not been handed off in writing, the task is not eligible.
5. **No conflicting work is currently in progress** — check for uncommitted changes or open work from another agent in the same ownership area (`awsmap.md` §10). If found, coordinate or wait; do not proceed concurrently.
6. **No higher-priority blocking work is being skipped.** In particular: the M4 → M5 → M6 critical path (§19) may never be bypassed by jumping to a later dependent task "because it's available." Respect the actual task dependencies in `plan.md`; do not treat every off-critical-path task in M4 as a prerequisite for all M5 work.

Task order itself is never re-derived here — `plan.md` is the sole source of sequence and dependency. If this document and `plan.md` ever appear to disagree on order, `plan.md` wins and the discrepancy is escalated (§17).

If no task is eligible for your agent role, **stop** and report that — do not select an ineligible task to appear productive, and do not perform unassigned "helpful" work (`awsmap.md` §17).

---

## 6. Dependency Verification

For every dependency `plan.md` lists for the candidate task:

- If the dependency is a **prior task**, confirm via §4 that its implementation is actually present and via §22 that it met its Definition of Done — not merely that a handoff report exists claiming so, if the report itself is inconsistent with what you observe.
- If the dependency is a **contract** (schema, API, event, pipeline — per `awsmap.md` §8), confirm the contract was actually published in a handoff, and read it. Do not proceed on an assumed or inferred contract.
- If the dependency is a **module checkpoint** (e.g., M9 requires M1–M8 complete), confirm the checkpoint was verified per `awsmap.md` §16 — module completion is a checkpoint verdict, not a tally of finished-looking tasks (§16 below).

If a dependency cannot be verified as actually satisfied, the task is not eligible. Do not proceed "provisionally."

---

## 7. Open Question / AMB Handling

`context.md` §11 lists AMB-1 through AMB-13. **AMB-13 is resolved** (the agent-map filename is `.dev/awsmap.md`). **AMB-1 through AMB-12 remain open** unless `context.md` itself states otherwise at the time you read it — this document does not change any of their status.

**No agent may resolve an AMB.** Not by "reasonable assumption," not by picking the option that seems more likely, not by implementing a placeholder "until it's decided."

If a task is blocked by an open AMB:

1. **Identify the exact AMB ID** from `context.md` §11.
2. **Identify the exact task ID** it blocks.
3. **State precisely what is blocked and why** — which specific decision the task cannot proceed without.
4. **Escalate through the mechanism `awsmap.md` §12 defines** — route through A1 to the project owner.
5. **Stop that task.** Do not implement a guessed workaround, a stubbed default, or a "temporary" version of the blocked behavior.
6. **Resume only after the decision is officially recorded in `context.md`** (moved from §11 to §7 there, per its own update rules) — not merely mentioned in conversation.

Known critical-path blockers to watch for specifically: **AMB-1 blocks M4**; **AMB-2 blocks M6**. Do not start either module while its blocking AMB is open.

---

## 8. Agent Ownership Enforcement

Ownership is defined in `awsmap.md` §4–§6 and is binding.

- An agent executes only tasks for which `awsmap.md` §6 names it the **primary owner**.
- An agent does not take another agent's task because it is convenient, faster, or already understood — even under schedule pressure.
- Required reviewers (`awsmap.md` §9) and required contract producers/consumers (§8) must be respected exactly as listed; an agent does not skip a review because it is confident the work is correct.
- Forbidden modifications (`awsmap.md` §4, per-agent "Must NOT modify" rows) are absolute. An agent noticing an issue outside its ownership **reports it** — it does not fix it.
- **A1 remains a coordination and verification role.** A1 verifies dependencies, contracts, and checkpoints, and arbitrates conflicts — A1 does not become a general implementation agent by default. A1 implements directly only where `awsmap.md` explicitly assigns it a task ID (e.g., M9-T6 or M10-T8) or where a specific integration fix has explicit project-owner authorization.
- Shared-file conflicts follow `awsmap.md` §10's coordination protocol exactly — request, confirm, implement by the owner, record, notify. No concurrent edits to a shared file.

---

## 9. Contract-First / Backend-First Rules

- Backend-first sequencing is structural, not a suggestion: a frontend task (owned by A6) does not start until its backing API contract (owned by A2, per `awsmap.md` §8 C5) is published and stable.
- **A6 must never invent, stub, or assume a backend endpoint, field, or response shape.** If a needed contract is missing, A6 files a gap report (per `awsmap.md` §8 C5) and stops — it does not build against a guess.
- **A2 must never break a published contract** once a consumer has begun using it, without the coordinated change process in `awsmap.md` §8 C6 (A1 approval, consumer notification).
- The same contract-first rule applies upstream: A3's schema contract gates A2/A4/A5; A4's event contract gates A5; A5's pipeline contract gates A2/A3/A6/A7. No agent proceeds against an unpublished upstream contract.
- Agents do not bypass a real dependency to "parallelize" work. `awsmap.md` §7 (Parallel Execution Matrix) governs exactly what may run concurrently; it is not open to reinterpretation for convenience.

---

## 10. Implementation Rules

While executing an eligible task:

- **Modify only the assigned scope** — the files and subsystem `awsmap.md` §5/§6 assign to this task and this agent.
- **Preserve existing architecture.** Do not redesign, restructure, or introduce a different pattern than what the PRD and plan establish.
- **Do not introduce rejected technologies** — Kubernetes, microservices, GraphQL, Kafka, or any other technology PRD §5/§10.3 explicitly rejects, and do not introduce any technology "because it's common for this kind of system" (`awsmap.md` §17).
- **No opportunistic refactors.** A task fixes or builds what it was assigned; it does not also clean up, rename, or restructure adjacent code.
- **Do not modify unrelated modules or tasks**, even ones that look related.
- **Do not modify `.dev/` orchestration files** during implementation, except the specific `context.md` updates this document authorizes in §15. `.dev/` stays gitignored and is never exposed through application functionality.
- **Do not silently change another agent's established decision.** If you believe a prior decision is wrong, report it — do not overwrite it unilaterally.

---

## 11. P0 Correctness Guardrails

These are the project's non-negotiable correctness properties (PRD, as reflected in `context.md` §7–§8). **No schedule pressure, task difficulty, or convenience justifies weakening any of these:**

- No user-facing request path may synchronously call GitHub.
- No user-facing request path may synchronously call the merge bot.
- Every webhook request must pass signature verification before any processing.
- Webhook payloads must be durably stored before or as part of acknowledgment — never lost if downstream processing fails.
- Webhook processing must be idempotent on GitHub's delivery ID — duplicate deliveries never duplicate effects.
- The contribution state machine's defined transitions must be followed exactly — no shortcut transitions, no skipped states.
- Worker-crash recovery (the heartbeat/lock-timeout sweep) must remain functional — no contribution may become permanently stuck.
- Daily-limit enforcement must remain race-safe under concurrent merges (per-participant-per-day row-level locking) — never a global lock, never an unlocked check-then-act.
- Point award must remain a single atomic transaction — never partially applied.
- Exactly one credited award per contribution must hold, enforced at the database level.
- Merge concurrency must remain bounded to the configured limit at all times, including under burst load.
- Graceful degradation must hold for every dependency the PRD names (GitHub, merge bot, Redis, Postgres, Celery workers) — the read-facing site stays usable even when any one of them fails.
- Emergency pause/resume/freeze controls must remain effective without a restart, and each must remain independently toggleable.
- Required audit logging (admin actions, point adjustments) must remain in place wherever the PRD requires it.

If completing a task as scoped would require weakening any of the above, **stop** — this is a Stop Condition (§21), not a trade-off to make locally.

---

## 12. Validation & Testing Gate

**Writing code is not completion.** Before a task may be reported as anything other than PARTIAL or BLOCKED:

- Relevant tests (unit/integration, per the task's nature) must exist and must pass — reported with actual results, not "tests pass."
- Where the task touches a migration, the migration must be verified to apply cleanly against the current schema state.
- Where the task touches an API or other contract, the contract must be verified against what was actually published — not assumed compatible.
- Where the task touches auth, authorization, signature verification, or any security-relevant path, security verification appropriate to that surface must be performed or explicitly deferred to the owning reviewer (A7, per `awsmap.md` §9).
- Manual verification is required wherever automated coverage cannot reasonably confirm the task's observable outcome (e.g., confirming an emergency-control flag takes effect without a restart).
- Evidence — actual output, not a claim — must be captured for the handoff report (§14).

A task with failing, missing, or unverifiable validation is **not complete**, regardless of how much implementation exists.

---

## 13. Review Gate

Review requirements come from `awsmap.md` §9 and are mandatory, not advisory.

- Determine the task's required reviewer(s) from `awsmap.md` §9's category table before starting — know the review bar in advance, not as an afterthought.
- **Self-declared completion does not satisfy a review requirement.** A task requiring A3, A5, or A7 review is not complete until that agent has actually reviewed it and recorded a verdict.
- The highest-risk work in the project (M6-T5 point award: A7 + A5 + A1; M5/M6 state and concurrency correctness; the webhook path) carries the review load `awsmap.md` §9 specifies — do not shortcut it because the implementer is confident.
- A7 (or any required reviewer) may reject the work. A rejection is binding: the task is not complete regardless of implementation effort. The owning agent addresses the rejection and resubmits; the reviewer does not take over implementation.

---

## 14. Handoff Procedure

Use the handoff format `awsmap.md` §14 defines exactly — no alternate or abbreviated format:

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

Reviews obtained:   <reviewer agent IDs + verdicts, per awsmap.md §9>

Known limitations:  <what this does not do>
Unresolved issues:  <including any AMB blockers encountered>
Follow-up tasks:    <existing plan.md task IDs only — never invent a task ID>

Checkpoint status:  Does this satisfy the task's validation criteria in plan.md?
                    YES / NO / NOT APPLICABLE (task is not a module checkpoint)
                    If NO: what remains.
```

Produce this report for every task regardless of outcome — a BLOCKED or PARTIAL result is reported with the same rigor as COMPLETE. A handoff claiming COMPLETE without recorded reviews and test results is invalid and must not be accepted or built upon by another agent.

---

## 15. Context Update Procedure

`context.md` represents **current state**, not a running log. Update it — following its own §13 rules — only when one of these becomes true:

- Implementation reality actually changed (an item moves between Implemented / In Progress / Planned / Unknown in its §9).
- A task or module checkpoint was verified per §16 below.
- An AMB in its §11 was **officially** resolved (moved to §7 with its decision and source — never resolved by an agent's inference).
- A significant architectural or product decision was made and needs recording in its §7.
- A constraint changed (its §8).
- A conflict between documents, or between documents and observed repository state, was discovered (recorded in its §11 as a new entry, not silently absorbed).

**Do not turn `context.md` into a diary.** Routine per-command progress, intermediate attempts, and task-in-progress narration belong in the task's own working notes or the handoff report — not in `context.md`. When updating, replace what is stale; do not stack a new paragraph on top of an old one describing the same fact.

---

## 16. Module Checkpoint Gate

A module (M1–M10) is **not** complete because its listed tasks each report COMPLETE. It is complete only when its checkpoint criteria, as defined in `plan.md`, are independently verified true — per the checkpoint-verifier assignment in `awsmap.md` §16.

Procedure:
1. Confirm every task belonging to the module has a COMPLETE handoff with required reviews obtained.
2. The module's designated checkpoint verifier (per `awsmap.md` §16 — often A7, always with A1) evaluates the module against `plan.md`'s stated checkpoint criteria directly, not against the task list.
3. If the checkpoint criteria are met: record the module as complete in `context.md` per §15 above.
4. If the checkpoint criteria are **not** met, even though tasks look finished: the module remains incomplete. Identify exactly which checkpoint criterion fails, route the fix to the owning agent per `awsmap.md` §6, and revalidate from step 1 for the affected criterion.

Do not advance to a dependent module until the checkpoint gate has actually passed.

---

## 17. Failure / Blocked Task Procedure

None of the following are ever hidden, silently retried into a different approach without recording it, or worked around without escalation:

| Situation | Required action |
|---|---|
| Tests fail | Report failure with evidence in the handoff; task is PARTIAL/BLOCKED, not COMPLETE. Fix within scope or escalate if the fix requires a decision. |
| A claimed dependency turns out unsatisfied on inspection | Stop the task. Correct `context.md` if it misrepresented the state (§15). Re-run Task Selection (§5). |
| A required contract is missing or unpublished | Stop. Request it from the owning agent per `awsmap.md` §8. Do not proceed on an assumed contract. |
| Merge conflict in a shared file | Do not force-resolve unilaterally. Follow `awsmap.md` §10's coordination protocol; involve the file's primary owner. |
| Another agent has modified files this task needs | Do not overwrite. Determine via git history/handoffs whether that work is reviewed/complete; coordinate rather than clobber. |
| Required infrastructure/environment is unavailable | Report as BLOCKED with the specific unavailable dependency; do not simulate or fake the missing piece silently. |
| An open AMB blocks the task | Follow §7 exactly. Stop and escalate. |
| Repository state is unexpected or inconsistent with documents | Stop (§4). Record the discrepancy. Do not proceed on a best guess of what "must have happened." |
| A genuine architecture conflict is discovered (e.g., PRD and an existing implementation disagree) | Do not silently pick a side. Escalate per `awsmap.md` §12/this document §21. |

In every case: report the real state, including uncertainty. A vague or optimistic status is worse than an explicit BLOCKED.

---

## 18. Multi-Agent Concurrency Rules

- Before editing, inspect current git state (§4) — do not assume the repository matches what you last touched or what a handoff report described, without confirming.
- Never overwrite another agent's unreviewed work. If work exists that you did not expect, treat it as real and investigate before acting.
- Do not edit a file another agent currently owns or is actively working in without the coordination protocol (`awsmap.md` §10).
- Communicate exclusively through handoff reports (§14) and the escalation path (§7/§21) — not through undocumented assumptions about what another agent "probably did."
- Escalate ownership conflicts (two agents believing they own the same task or file) to A1 rather than resolving by whoever acts first.
- **Never reset, revert, or discard another agent's changes without explicit project-owner authorization**, even if you believe your version is better.
- Respect the Parallel Execution Matrix in `awsmap.md` §7 exactly — it defines both where concurrency is safe and where it is forbidden (most notably M4/M5/M6, see §19 below).

---

## 19. Scope-Cutting / Schedule Pressure

The PRD's priority model (P0/P1/P2) remains authoritative regardless of how the 10-day schedule is tracking. If time pressure appears:

1. **Cut P2 items first**, in the order `plan.md` §5 lists them.
2. **Then cut P1 items**, in that same documented order.
3. **Never silently cut, defer, or downgrade a P0 requirement.** If a P0 item appears at risk, that is an escalation (§21), not a scope decision an agent makes alone.
4. **Record every deliberate scope cut** — what was cut, why, and by what authority — in `context.md` per §15, not left implicit.

**The M4 → M5 → M6 critical path (webhook ingestion → contribution state machine/validation → merge queue/points) is explicitly protected.** The real dependency chain must never be bypassed, reordered, or parallelized away. This does **not** mean every M4 task must finish before every M5 task: off-critical-path work such as M4-T5 reconciliation may run in parallel when its own dependencies are satisfied, exactly as permitted by `awsmap.md` §7. If the schedule is genuinely at risk, the absorption point is the hardening/buffer capacity in M9/M10 — not this path's P0 correctness work.

---

## 20. M10 / Production Execution

M10 uses exactly the current canonical structure from `plan.md`: **M10-T1 through M10-T8**, with the dependencies `plan.md` defines for each — no other numbering, and no task invented beyond these eight.

Execution follows the exact dependencies in `plan.md`: **M10-T3 (managed stores) depends on M9; M10-T4 (secrets) depends on M9 + M10-T3; M10-T1 (backend deploy) depends on M9 + M10-T3 + M10-T4; M10-T2 (frontend deploy) depends only on M9 and may proceed independently of T1; M10-T5 depends on T1 + T2; M10-T6 depends on T1 + T3; M10-T7 depends on T1–T6; M10-T8 depends on T7.** Do not invent an additional dependency between T1 and T2. Ownership and review of each M10 task are resolved from `awsmap.md` at execution time rather than duplicated here.

Do not introduce deployment infrastructure, tooling, or a process topology beyond what PRD §25 and `plan.md`'s M10 tasks establish. M10 does not begin until M9's checkpoint (per `awsmap.md` §16) has actually passed — not merely until M9's tasks look finished.

---

## 21. Stop Conditions

An agent **must stop** — not pause-and-guess, not proceed cautiously, stop — when any of the following occurs:

- An open AMB (context.md §11) blocks the current task.
- A required decision has not been made and is not an agent's to make.
- An ownership conflict exists (two agents, one task; or a task with no clear owner in `awsmap.md`).
- A claimed dependency is not actually satisfied on inspection.
- A required reviewer is unavailable and the task's risk category (`awsmap.md` §9) does not permit proceeding without that review.
- A genuine security concern is identified, whether or not it was the task's original focus.
- A genuine data-integrity concern is identified (idempotency, race-safety, transactional guarantees).
- An architecture conflict is discovered between documents, or between a document and observed repository state.
- The task as scoped cannot be completed without exceeding its assigned boundary (per `awsmap.md` ownership) or without violating a P0 guardrail (§11).
- A module checkpoint fails verification and the failure requires a decision beyond a straightforward fix within the owning agent's scope.

Stopping means: record the exact reason (which condition, which task, which document/section it references), produce a handoff reporting BLOCKED with full detail, and escalate per §7/§17. Stopping is not a failure state to avoid — proceeding past a real stop condition is the actual failure.

---

## 22. Definition of Done

A task is **COMPLETE** only when every one of these holds simultaneously:

1. The implementation satisfies the task's defined objective and expected outcome exactly as `plan.md` states them — no more, no less.
2. Every dependency the task relied on remains intact and unbroken by this change.
3. Required tests/validation (§12) pass, with evidence, not merely "should work."
4. Required review (§13) has been obtained from the correct reviewer(s) per `awsmap.md` §9, with a recorded verdict.
5. No blocking issue remains open against this task — including no unresolved AMB, no missing contract, no unreviewed conflict.
6. A handoff report (§14) has been produced, honestly reflecting status, limitations, and any unresolved issues.
7. Where the task constitutes or contributes to a module checkpoint, `context.md` and, where applicable, the checkpoint record (§16) have been updated to reflect the true, verified state.

If any one of these does not hold, the task is **PARTIAL** or **BLOCKED**, and is reported as such. A task is never marked COMPLETE to reflect effort rather than verified outcome.

---

## 23. Quick Reference / Agent Checklist

1. Read PRD.md → plan.md → context.md → awsmap.md, in full, this session.
2. Inspect the actual repository and git state. Trust what you observe over what any document assumed.
3. Identify your agent ID and confirm you are the primary owner of your candidate task per awsmap.md §6.
4. Verify every dependency is *actually* satisfied — not just earlier in the schedule.
5. Check context.md §11 and awsmap.md §12 for any AMB blocking this task. If blocked: stop, escalate, do not proceed.
6. Confirm every contract you depend on has been published (awsmap.md §8). Do not infer one.
7. Check for conflicting concurrent work in your ownership area before editing anything.
8. Implement strictly within your assigned scope. No refactors, no rejected technologies, no architecture changes, no `.dev/` edits.
9. Protect every P0 guardrail in §11 — never trade one away for schedule convenience.
10. Run and record real validation (§12). "Written" is not "done."
11. Obtain every required review (§13) before calling the task complete.
12. Produce the full handoff report (§14) — honestly, including BLOCKED/PARTIAL outcomes.
13. Update `context.md` only per §15 — current state, not a diary.
14. If this task completes a module, verify the checkpoint per §16 before treating the module as done.
15. If schedule pressure appears, cut P2 then P1 only, per §19 — never P0, and protect M4 → M5 → M6 absolutely.
16. If any Stop Condition (§21) applies, stop. Report. Escalate. Do not guess your way past it.
17. Only after all of the above: return to Task Selection (§5) for the next eligible task.
