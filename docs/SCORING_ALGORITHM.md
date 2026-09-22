# CommitRush Scoring Engine & Farming Detection Specification

## 1. Overview

CommitRush implements an automated, auditable, and cheat-resistant scoring pipeline for open-source contributions during events like HackIT / Hacktoberfest. The scoring system ensures that:
- Every contribution is evaluated through an authoritative, deterministic pipeline.
- Points reflect both the difficulty and category of the contribution via configurable multipliers.
- Per-PR maximum caps and daily allowances prevent spam and point farming.
- Transparent 5-row scoring breakdowns are provided to contributors.
- Heuristic farming signals are detected and surfaced to administrators without automated bans.
- Leaderboard rankings are strictly derived from `final_awarded_points`.

---

## 2. End-to-End Scoring Pipeline

The lifecycle of point awarding occurs atomically when a pull request reaches the `MERGED` state:

```
┌─────────────────┐
│ Pull Request    │
│ Merged on Repo  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Participant     │ ── Suspended? ──► [DEFERRED: 0 pts]
│ Gating          │
└────────┬────────┘
         │ Active
         ▼
┌─────────────────┐
│ Classification  │ ── 1. Issue.category ──► 2. Labels ──► 3. Title Prefix ──► 4. Fallback ('feature')
│ Cascade         │
└────────┬────────┘
         │ (category, multiplier)
         ▼
┌─────────────────┐
│ Base Points &   │ ── P_base = issue.points or 10
│ Multiplier      │ ── P_calc = round(P_base * Multiplier)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Per-PR Cap      │ ── P_pr_capped = min(P_calc, EventConfig.per_pr_max_points)
│ Enforcement     │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Farming         │ ── Non-banning heuristics (bursts, tiny docs, repo spam)
│ Detection       │ ── Flagged into ScoringBreakdown for Admin Review
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Daily Caps &    │ ── Contrib count > max? ──► [DEFERRED: 0 pts]
│ Allowance       │ ── Allowance <= 0?      ──► [DEFERRED: 0 pts]
│ Allocation      │ ── P > Allowance?       ──► [allow_partial? Yes: A_rem pts | No: 0 pts]
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Atomic Ledger & │ ── PointTransaction (status: AWARDED or DEFERRED)
│ Audit Breakdown │ ── ScoringBreakdown (immutable audit snapshot)
└────────┬────────┘    Participant.total_points += final_awarded_points
         │             DailyContributionUsage.points_count += final_awarded_points
         ▼
┌─────────────────┐
│ Leaderboard     │ ── Filtered & cached aggregate of final_awarded_points
│ & Badges        │ ── Contributor daily limit & allowance display
└─────────────────┘
```

---

## 3. Mathematical Formula

### Base Points ($P_{\text{base}}$)
$$P_{\text{base}} = \begin{cases} 
\text{Issue.points} & \text{if } \text{Issue.points} > 0 \\ 
10 & \text{otherwise} 
\end{cases}$$

### Category Multiplier ($M$)
$$M = \text{EventConfig.category\_multipliers}[\text{category}]$$

Default multiplier table:
| Category | Default Multiplier | Friendly Label |
| :--- | :--- | :--- |
| `feature` | **1.5×** | Feature |
| `bug` | **1.0×** | Bug Fix |
| `test` | **1.2×** | Testing & QA |
| `security` | **1.5×** | Security |
| `performance` | **1.3×** | Performance |
| `docs` | **0.8×** | Documentation |
| `refactor` | **1.0×** | Refactoring |
| `validation` | **1.0×** | Validation |
| `ui` | **1.1×** | UI |
| `database` | **1.2×** | Database & Storage |
| `networking` | **1.2×** | Networking |
| `frontend` | **1.1×** | Frontend |
| `backend` | **1.2×** | Backend |
| `devops` | **1.2×** | DevOps / Infrastructure |
| `fullstack` | **1.3×** | Fullstack |
| `dx` | **1.0×** | Developer Experience |

### Calculated Points ($P_{\text{calc}}$)
$$P_{\text{calc}} = \text{round}(P_{\text{base}} \times M)$$

### Per-PR Capped Points ($P_{\text{pr\_capped}}$)
$$P_{\text{pr\_capped}} = \min(P_{\text{calc}}, \text{EventConfig.per\_pr\_max\_points})$$
*(Default `per_pr_max_points` = 100)*

### Daily Allowance & Final Awarded Points ($P_{\text{final}}$)
Let:
- $C_{\text{today}}$ = participant contributions merged today
- $C_{\text{max}}$ = `EventConfig.max_contributions_per_day`
- $P_{\text{today}}$ = points awarded to participant today
- $L_{\text{daily}}$ = `EventConfig.max_points_per_day`
- $A_{\text{rem}} = \max(0, L_{\text{daily}} - P_{\text{today}})$ (Remaining daily allowance)

1. **Daily Contribution Limit Reached** ($C_{\text{today}} \ge C_{\text{max}}$):
   $$P_{\text{final}} = 0 \quad (\text{status} = \text{DEFERRED}, \text{cap} = \text{'Daily contribution limit'})$$

2. **Daily Points Cap Exhausted** ($A_{\text{rem}} \le 0$):
   $$P_{\text{final}} = 0 \quad (\text{status} = \text{DEFERRED}, \text{cap} = \text{'Daily limit'})$$

3. **Points Exceed Remaining Allowance** ($P_{\text{pr\_capped}} > A_{\text{rem}}$):
   - When `EventConfig.allow_partial_daily_points == True`:
     $$P_{\text{final}} = A_{\text{rem}} \quad (\text{status} = \text{AWARDED}, \text{cap} = \text{'Daily limit'})$$
   - When `EventConfig.allow_partial_daily_points == False`:
     $$P_{\text{final}} = 0 \quad (\text{status} = \text{DEFERRED}, \text{cap} = \text{'Daily limit'})$$

4. **Under All Caps** ($P_{\text{pr\_capped}} \le A_{\text{rem}}$):
   $$P_{\text{final}} = P_{\text{pr\_capped}} \quad (\text{status} = \text{AWARDED}, \text{cap} = \text{'Not reached'})$$

---

## 4. Deterministic Classification Cascade

To avoid arbitrary or subjective categorization, contributions are classified using an unambiguous cascade:

1. **Cascade Level 1: Authoritative Issue Category**
   - If the linked `Issue.category` is set and resolves to one of the 16 standard category keys or known aliases (`bugfix` $\to$ `bug`, `documentation` $\to$ `docs`, `perf` $\to$ `performance`, `ci` $\to$ `devops`, etc.).
2. **Cascade Level 2: Issue Cached Labels**
   - Matches issue labels (e.g. GitHub labels `documentation`, `bug`, `enhancement`, `security`).
3. **Cascade Level 3: Issue Title Prefix Convention**
   - Evaluates regular expressions against issue title prefix:
     - `^(feat|feature)(\(.*\))?:\s*` or `^\[(feat|feature)\]\s*` $\to$ `feature`
     - `^(fix|bug|bugfix)(\(.*\))?:\s*` or `^\[(fix|bug)\]\s*` $\to$ `bug`
     - `^(docs|doc)(\(.*\))?:\s*` or `^\[(docs|doc)\]\s*` $\to$ `docs`
     - `^(test|tests)(\(.*\))?:\s*` or `^\[(test|tests)\]\s*` $\to$ `test`
     - `^(sec|security)(\(.*\))?:\s*` or `^\[(sec|security)\]\s*` $\to$ `security`
     - `^(perf|performance)(\(.*\))?:\s*` or `^\[(perf|performance)\]\s*` $\to$ `performance`
     - `^(refactor|style)(\(.*\))?:\s*` $\to$ `refactor`
     - `^(ci|build|devops)(\(.*\))?:\s*` $\to$ `devops`
4. **Cascade Level 4: Deterministic Fallback**
   - If no indicators match, defaults to `('feature', 'Feature')`.

---

## 5. Farming Detection Heuristics

Farming detection monitors submission patterns across 24-hour and 60-minute windows. **Signals are non-banning** and exist exclusively to empower staff review:

1. **Rapid Burst (`rapid_burst`)**:
   - Condition: $\ge 3$ contributions submitted or merged within the last 60 minutes.
2. **Repeated Same Project (`repeated_same_project`)**:
   - Condition: $\ge 4$ contributions submitted against the identical repository within 24 hours.
3. **Multiple Tiny Docs (`multiple_tiny_docs`)**:
   - Condition: $\ge 3$ documentation contributions within 24 hours.
4. **Very Low-Impact Changes (`very_low_impact`)**:
   - Condition: $\ge 4$ contributions with base points $\le 15$ within 24 hours.
5. **Repeated Trivial Changes (`repeated_trivial_changes`)**:
   - Condition: $\ge 6$ contributions within 24 hours where $> 60\%$ are low-impact.

### Risk Level Scoring
- `HIGH`: $\ge 3$ active signals
- `MEDIUM`: 2 active signals
- `LOW`: 1 active signal
- `NONE`: 0 active signals

---

## 6. Auditability & Data Model

Every point evaluation records an immutable `ScoringBreakdown` entity linked 1:1 with `Contribution` and `PointTransaction`:

```python
class ScoringBreakdown(models.Model):
    contribution = models.OneToOneField(Contribution, related_name='scoring_breakdown')
    point_transaction = models.OneToOneField(PointTransaction, null=True, blank=True)
    base_points = models.IntegerField()
    category = models.CharField(max_length=50)
    category_label = models.CharField(max_length=100)
    multiplier = models.FloatField()
    calculated_points = models.IntegerField()
    per_pr_cap = models.IntegerField()
    points_after_pr_cap = models.IntegerField()
    daily_points_cap = models.IntegerField()
    daily_points_before = models.IntegerField()
    daily_allowance_remaining = models.IntegerField()
    cap_applied = models.CharField(max_length=50)
    final_awarded_points = models.IntegerField()
    farming_signals = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
```

### Contributor Facing Breakdown UI
The contributor dashboard and contribution detail views display this exact transparent 5-row table:

```
┌─────────────────────┬──────────────────┐
│ Metric              │ Value            │
├─────────────────────┼──────────────────┤
│ Base Points         │ 20               │
│ Contribution        │ Feature          │
│ Multiplier          │ 1.5×             │
│ Calculated Points   │ 30               │
│ Cap Applied         │ None / Daily limit
│ Points Awarded      │ 30 (or 20 capped)│
└─────────────────────┴──────────────────┘
```

> **Security & Privacy Note:** The internal `farming_signals` object is strictly withheld from standard contributor API responses to prevent bad actors from reverse-engineering anti-abuse thresholds. It is accessible exclusively to authenticated staff and administrators via `/api/v1/admin/farming-reviews/` and administrative contribution queries.

---

## 7. Administrative APIs

### 1. Dynamic Scoring Controls
- **Endpoint**: `PATCH /api/v1/admin/controls/`
- **Permissions**: Staff / Admin only (`IsAdminUser`)
- **Parameters**:
  - `per_pr_max_points`: Positive integer (e.g. `100`)
  - `allow_partial_daily_points`: Boolean (`true` / `false`)
  - `category_multipliers`: Dictionary mapping category keys to positive float multipliers:
    ```json
    {
      "feature": 1.5,
      "bug": 1.2,
      "docs": 0.8,
      "security": 1.8
    }
    ```

### 2. Farming Review Dashboard
- **Endpoint**: `GET /api/v1/admin/farming-reviews/`
- **Permissions**: Staff / Admin only (`IsAdminUser`)
- **Query Filters**:
  - `risk_level`: `HIGH` | `MEDIUM` | `LOW`
  - `username`: Filter by participant GitHub username
- **Response**: Paginated contributions with attached `farming_signals`, repo info, and scoring metrics.

---

## 8. Leaderboard Calculations

- **Authoritative Metric**: `Participant.total_points`, which is the direct atomic accumulation of `final_awarded_points`.
- **Enriched Contributor Context**:
  - `points_today`: Points earned in the current UTC calendar day.
  - `daily_limit`: `EventConfig.max_points_per_day`.
  - `remaining_daily_allowance`: Points remaining before daily cap.
  - `is_daily_limit_reached`: Boolean flag rendered as a **"Capped"** badge when daily limit is reached.
