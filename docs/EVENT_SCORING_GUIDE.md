# HackIT CommitRush — Official Event Scoring & Daily Limit Guide

**Event:** HackIT CommitRush Open Source Contribution Drive  
**Target Repository:** `Hackit-DROID/Open-Source-Contribution-Drive`  
**Official Event Timezone:** `Asia/Kolkata` (IST, UTC+05:30)  
**Daily Scoring Cap:** **120 Points** per participant per calendar day  

---

## Table of Contents
1. [Overview & Core Philosophy](#1-overview--core-philosophy)
2. [Difficulty Scoring Rubric](#2-difficulty-scoring-rubric)
3. [The 120-Point Daily Limit](#3-the-120-point-daily-limit)
4. [Official Timezone & Midnight Reset](#4-official-timezone--midnight-reset)
5. [Definition of a Valid Contribution](#5-definition-of-a-valid-contribution)
6. [Single-Claim & Anti-Duplication Rules](#6-single-claim--anti-duplication-rules)
7. [What Happens When a Participant Reaches 120 Points](#7-what-happens-when-a-participant-reaches-120-points)
8. [Leaderboard Points Calculation & Persistence](#8-leaderboard-points-calculation--persistence)
9. [Scoring Examples (Scenarios 1 to 5)](#9-scoring-examples-scenarios-1-to-5)
10. [Organizer Guide: Verification & Auditing](#10-organizer-guide-verification--auditing)
11. [Organizer Guide: Manual Adjustments & Overrides](#11-organizer-guide-manual-adjustments--overrides)

---

## 1. Overview & Core Philosophy

The **HackIT CommitRush Open Source Contribution Drive** encourages quality, sustainable open-source contributions. To foster healthy pacing, prevent burnout, and stop point farming, the event enforces a strict **daily cap of 120 points per participant per calendar day**.

Key principles:
- **Quality Over Volume:** High-impact contributions (Medium, Hard, Master) are recognized and prioritized.
- **Fair Play & Anti-Farming:** A daily point ceiling stops rapid script-based point accumulation.
- **Open Collaboration:** Hitting the daily cap never prevents contributors from opening or merging valid pull requests. PRs can always merge; only the point accumulation stops for that day.
- **Strict Determinism:** Every point award is verifiable, idempotent, and tied to an immutable transaction ledger.

---

## 2. Difficulty Scoring Rubric

Each candidate issue in `COMMITRUSH_ISSUE_CANDIDATES.md` is assigned an official difficulty level. Points are awarded based on difficulty:

| Difficulty Level | Points Awarded | Expected Effort / Scope |
|:---|:---:|:---|
| **Beginner** | **5** | Minor documentation fixes, typo corrections, comments, single-line adjustments. |
| **Easy** | **10** | Small bug fixes, simple tests, minor component updates, style fixes. |
| **Medium** | **20** | Multi-file features, bug fixes requiring debugging, new unit/integration tests. |
| **Hard** | **30** | Complex architecture changes, performance refactoring, security hardening. |
| **Master** | **50** | Major subsystem implementations, core algorithm redesign, large cross-cutting features. |

> **Note:** Points are derived strictly from the referenced issue's difficulty. Per-PR maximum points are configured at **50 points** (the Master tier).

---

## 3. The 120-Point Daily Limit

### Rule Definition
Each participant can earn a maximum of **120 points** toward the competition leaderboard on any given calendar day.

### No Partial Credits Policy
The CommitRush scoring engine enforces an **all-or-nothing (no partial credit)** rule for contributions when approaching the cap:
- If a participant has earned 115 points today and merges an Easy PR (worth 10 points):
  - $115 + 10 = 125 > 120$.
  - The PR receives **0 competition points**.
  - The participant's daily score remains **115 points**.
  - **Rationale:** Awarding partial points (e.g. 5 points for a 10-point PR) distorts the difficulty value of contributions and creates ambiguity. By keeping PR difficulty atomic, participants are incentivized to plan their submissions strategically (e.g., submitting a 5-point Beginner issue to hit exactly 120).

### Daily Cap Exhaustion
- If a participant has already reached **120 points** today, any further PRs merged on that same day receive **0 competition points**.
- The contribution is marked with status `DEFERRED` and flagged reason `DAILY LIMIT REACHED`.

---

## 4. Official Timezone & Midnight Reset

The official timezone for HackIT CommitRush is **Asia/Kolkata (Indian Standard Time, IST / UTC+05:30)**.

### Midnight Reset Mechanism
- The daily counter resets every calendar day at **00:00:00 IST** (midnight).
- Daily quotas are grouped by the date in `Asia/Kolkata`:
  $$\text{event\_date} = \text{merged\_at.astimezone(ZoneInfo('Asia/Kolkata')).date()}$$
- **UTC vs. IST Boundary Notice:**
  - UTC midnight is **05:30 IST**.
  - Therefore, contributions merged between **18:30 UTC and 23:59 UTC** belong to the **next calendar day** in IST!
  - Example: A PR merged at `2026-09-22 23:30:00 UTC` is evaluated at `2026-09-23 05:00:00 IST`. Its points count toward **September 23**, with a fresh 120-point allowance.

---

## 5. Definition of a Valid Contribution

For a pull request to be awarded competition points, all of the following conditions must be met:

1. **Merged Successfully:** The PR must be merged (`merged == True`). Open, draft, or closed-unmerged PRs earn 0 points.
2. **Targets Designated Event Branch:** The PR must target the official branch: `main`. PRs merged into feature branches, `develop`, or release branches earn 0 points.
3. **Valid CommitRush Issue Reference:** The PR title or body must reference a valid CommitRush issue format (e.g., `CR-101`, `CR-1234`, `#101`).
4. **Issue Exists in Candidate Catalog:** The referenced issue must exist in `COMMITRUSH_ISSUE_CANDIDATES.md` and the event database.
5. **PR Author Match:** The PR author's GitHub username must match an active participant registered in CommitRush.
6. **Within Event Window:** The PR merge timestamp must fall within `EVENT_START_DATE` (`2026-09-22`) and `EVENT_END_DATE` (`2026-10-31`).

---

## 6. Single-Claim & Anti-Duplication Rules

To ensure fair opportunity across the community:
1. **Single-Claim per Issue:** Each issue in the repository can only be scored once across the entire drive.
2. **Duplicate Issue Prevention:** If Participant B merges a PR for `CR-205` after Participant A already had a PR merged and scored for `CR-205`, Participant B receives 0 points (`DUPLICATE_ISSUE`).
3. **Idempotent PR Evaluation:** Rerunning a GitHub Actions workflow or scoring script on an already-scored PR will detect the existing transaction and return `ALREADY_PROCESSED` with 0 additional points.

---

## 7. What Happens When a Participant Reaches 120 Points

When a participant reaches 120 points on a given day:
1. **Merge Is Allowed:** Maintainers and GitHub Actions **do NOT block** the pull request. Legitimate contributions are welcomed and merged.
2. **Scoring Engine Flags Limit:** The scoring engine evaluates the PR and marks points as:
   - `awarded_points = 0`
   - `sub_status = "DAILY_LIMIT_REACHED"`
   - `cap_applied = "Daily limit"`
   - `flagged_reason = "DAILY LIMIT REACHED: Participant already reached the 120-point daily limit for today (120/120)"`
3. **PR Feedback:** The GitHub Actions check posts a transparent comment or status notice:
   ```
   CommitRush Daily Limit Check: NOT COUNTED
   Status: 0 points awarded - daily cap reached (120/120 points used today).
   Your PR was merged cleanly, but your competition daily quota is full.
   Points will reset at 00:00 IST.
   ```

---

## 8. Leaderboard Points Calculation & Persistence

The competition leaderboard reflects verified, capped scores:
- **Participant Total Score:** $\sum \text{final\_awarded\_points}$ across all valid merged PRs.
- **Today's Score:** Points awarded on the current calendar day in `Asia/Kolkata` (range: $0 \le P_{\text{today}} \le 120$).
- **Remaining Daily Allowance:** $\max(0, 120 - P_{\text{today}})$.
- **Persistent Artifact:** Generated to `leaderboard.json` and committed / served via `/api/v1/leaderboard/export/`.

Format of `leaderboard.json`:
```json
{
  "event": "HackIT CommitRush Open Source Contribution Drive",
  "repository": "Hackit-DROID/Open-Source-Contribution-Drive",
  "timezone": "Asia/Kolkata",
  "daily_limit": 120,
  "participants": {
    "alice": {
      "rank": 1,
      "github_username": "alice",
      "total_points": 120,
      "counted_prs": 4,
      "today_points": 120,
      "remaining_today": 0,
      "daily_limit": 120,
      "is_daily_limit_reached": true,
      "daily": {
        "2026-09-22": {
          "points": 120,
          "merged_prs": 4
        }
      }
    }
  },
  "scored_issues": {
    "101": { "author": "alice", "pr_number": 1, "points": 20, "date": "2026-09-22" }
  },
  "processed_prs": {
    "1": { "author": "alice", "points": 20, "status": "AWARDED", "result_label": "COUNTED" }
  }
}
```

---

## 9. Scoring Examples (Scenarios 1 to 5)

### Example 1: Alice's Day 1 (Hitting Exactly 120 Points)
Alice opens and merges 5 valid pull requests on Day 1 (all targeting `main`):
- **PR 1:** References `CR-101` (Medium, 20 pts)
  - Daily points before: 0. Added: 20.
  - Daily points after: **20 / 120**. Status: `COUNTED`.
- **PR 2:** References `CR-205` (Hard, 30 pts)
  - Daily points before: 20. Added: 30.
  - Daily points after: **50 / 120**. Status: `COUNTED`.
- **PR 3:** References `CR-310` (Master, 50 pts)
  - Daily points before: 50. Added: 50.
  - Daily points after: **100 / 120**. Status: `COUNTED`.
- **PR 4:** References `CR-415` (Medium, 20 pts)
  - Daily points before: 100. Added: 20.
  - Daily points after: **120 / 120** (Daily cap reached!). Status: `COUNTED`.
- **PR 5:** References `CR-520` (Easy, 10 pts)
  - Daily points before: 120. Daily cap already reached.
  - Daily points after: **120 / 120**. Added: 0. Status: `NOT COUNTED - DAILY LIMIT`.

**Alice's Day 1 Total:** **120 points**. Alice merges 5 PRs, with 4 counted toward the competition score.

---

### Example 2: Bob's Day 1 (Boundary Case with No Partial Credits)
Bob works on larger issues on Day 1:
- **PR 1:** References `CR-001` (Master, 50 pts)
  - Daily points: **50 / 120**. Status: `COUNTED`.
- **PR 2:** References `CR-002` (Master, 50 pts)
  - Daily points: **100 / 120**. Status: `COUNTED`.
- **PR 3:** References `CR-003` (Hard, 30 pts)
  - Remaining allowance: $120 - 100 = 20\text{ points}$.
  - PR value: 30 points ($30 > 20$).
  - **Result:** Under the **No Partial Credits** policy, Bob does **NOT** receive 20 points. He receives **0 points**.
  - Status: `NOT COUNTED - DAILY LIMIT (Exceeds daily cap)`.
  - Daily score remains **100 points**.

**Bob's Day 1 Total:** **100 points**. If Bob instead submits an Easy PR (10 pts) or Medium PR (20 pts), he can reach 110 or 120 points.

---

### Example 3: Charlie's Multi-Day Drive (Daily Reset)
Charlie participates across two consecutive days:
- **Day 1 (2026-09-22):**
  - PR 1: Hard (30 pts) $\to$ 30 pts
  - PR 2: Hard (30 pts) $\to$ 60 pts
  - PR 3: Hard (30 pts) $\to$ 90 pts
  - **Day 1 Total:** **90 points** (Remaining allowance: 30 pts).
- **Midnight (00:00 IST):**
  - Quota resets. Daily points for 2026-09-23 starts at **0 / 120**.
- **Day 2 (2026-09-23):**
  - PR 4: Master (50 pts) $\to$ 50 pts
  - PR 5: Master (50 pts) $\to$ 100 pts
  - PR 6: Medium (20 pts) $\to$ 120 pts (Daily cap reached)
  - **Day 2 Total:** **120 points**.

**Charlie's Cumulative Score:** $90 + 120 =$ **210 points** across 6 counted PRs.

---

### Example 4: Invalid Contributions (Zero Points)
The following pull requests receive **0 points** and do not alter the daily allowance:
1. **No CR Issue Referenced:**
   - PR titled `"Fix navbar styles"` with no `CR-xxx` reference $\to$ **0 points** (`INVALID_ISSUE`).
2. **Merged into Non-Designated Branch:**
   - PR merged into branch `develop` or `feature/ui` instead of `main` $\to$ **0 points** (`INVALID_BRANCH`).
3. **Already-Claimed Issue:**
   - PR references `CR-101`, which was already scored in an earlier merged PR $\to$ **0 points** (`DUPLICATE_ISSUE`).
4. **Closed Without Merge:**
   - PR closed or abandoned without being merged $\to$ **0 points** (`UNMERGED`).

---

### Example 5: Daily Reset Timing & Timezone Evaluation
Consider two PRs merged around the midnight boundary:
- **PR A Merged at `2026-09-22 23:59:00 IST`:**
  - Evaluated under date: **2026-09-22**.
  - Counts against Day 1's 120-point quota.
- **PR B Merged at `2026-09-23 00:01:00 IST`:**
  - Evaluated under date: **2026-09-23**.
  - Counts against Day 2's fresh 120-point quota.

**UTC Equivalents:**
- `23:59:00 IST` on Sep 22 = `18:29:00 UTC` on Sep 22.
- `00:01:00 IST` on Sep 23 = `18:31:00 UTC` on Sep 22.
- The scoring engine explicitly converts UTC timestamps from GitHub (`merged_at`) into `Asia/Kolkata` before extracting the calendar date.

---

## 10. Organizer Guide: Verification & Auditing

Organizers have several methods to verify and audit scores:

### Method 1: Standalone CLI Evaluation
Inspect how any PR will score before or after merge without modifying the database:
```bash
python scripts/check_pr_daily_limit.py \
  --username alice \
  --pr 105 \
  --title "[CR-205] Add caching layer" \
  --branch main \
  --labels "difficulty:hard"
```

### Method 2: Standalone PR Processing Tool
Simulate or record merged PR scoring against `leaderboard.json`:
```bash
python scripts/process_pr_scoring.py \
  --username alice \
  --pr 105 \
  --title "[CR-205] Add caching layer" \
  --branch main \
  --merged \
  --merged-at "2026-09-22T14:30:00Z" \
  --labels "difficulty:hard"
```

### Method 3: Django Management Export Command
Regenerate and audit the authoritative leaderboard from the database:
```bash
python backend/manage.py export_leaderboard --output leaderboard.json
```

### Method 4: Django Shell Auditing
Inspect a participant's daily usage directly:
```python
from core.models import Participant, DailyContributionUsage
from core.scoring.constants import get_event_today

p = Participant.objects.get(github_username='alice')
today = get_event_today()
usage = DailyContributionUsage.objects.filter(participant=p, date=today).first()
print(f"Points today: {usage.points_count} / 120 (PRs: {usage.contributions_count})")
```

---

## 11. Organizer Guide: Manual Adjustments & Overrides

If a participant requires a manual point adjustment or correction (e.g., disqualified PR, re-categorization, or retroactive grant):

### Option A: REST API Endpoint (`/api/v1/admin/points/adjust/`)
Authenticated staff/organizers can issue adjustments via POST request:
```bash
curl -X POST http://localhost:8000/api/v1/admin/points/adjust/ \
  -H "Authorization: Bearer <ORGANIZER_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "participant_id": 1,
    "points": -20,
    "reason": "Administrative correction for duplicate issue CR-101"
  }'
```

### Option B: Django Admin Dashboard
1. Log in to Django Admin at `http://localhost:8000/admin/`.
2. Navigate to **Core $\to$ Point Transactions** or **Core $\to$ Participants**.
3. To adjust points, create a new `PointTransaction`:
   - Set `Participant`: Select participant.
   - Set `Points`: Number of points (positive or negative).
   - Set `Transaction Type`: `ADMIN_ADJUSTMENT`.
   - Set `Status`: `AWARDED`.
   - Set `Reason`: Document why the adjustment was made.
4. Update the participant's `total_points` or run `export_leaderboard` to synchronize.

### Option C: Runtime Event Controls (`/api/v1/admin/controls/`)
Organizers can dynamically adjust daily limit rules without restarting the server:
```bash
curl -X PATCH http://localhost:8000/api/v1/admin/controls/ \
  -H "Authorization: Bearer <ORGANIZER_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "allow_partial_daily_points": false,
    "per_pr_max_points": 50
  }'
```
