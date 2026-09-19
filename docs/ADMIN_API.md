# CommitRush Internal Administrator API Specification

This document specifies the internal administrator-only REST API layer for CommitRush. Administrative management is conducted exclusively via these server-side authorized endpoints under the `/api/v1/admin/` namespace.

---

## 1. Security Architecture & Authorization Model

### Server-Side Authorization Principle
CommitRush enforces access control strictly at the server boundary. The participant web interface contains no administrative buttons, links, or discoverable "Ops Portal" routes. All admin endpoints verify staff privilege server-side.

### Authentication & Headers
- **Session Authentication**: All administrative endpoints use Django session cookies (`sessionid`).
- **CSRF Protection**: State-changing requests (`POST`, `PUT`, `PATCH`, `DELETE`) require a valid CSRF token transmitted in the `X-CSRFToken` HTTP request header matching the session `csrftoken` cookie.
- **Content Type**: `application/json` for all request bodies.

### Response Codes for Access Control
- **`401 Unauthorized`**: Unauthenticated requests (no valid session cookie).
  ```json
  {
    "detail": "Authentication credentials were not provided."
  }
  ```
- **`403 Forbidden`**: Authenticated participants who lack administrator (`is_staff` / `is_superuser`) privileges.
  ```json
  {
    "detail": "Administrator privileges are required to perform this action."
  }
  ```
- **`409 Conflict`**: Debounce / concurrency lock conflict when a sensitive administrative action is triggered while another is in progress.
- **`429 Too Many Requests`**: Rate limits exceeded.

---

## 2. Admin Endpoints Overview

| Endpoint | Method | Scope | Description |
|---|---|---|---|
| `/api/v1/admin/controls/` | `GET`, `PATCH`, `POST` | System | Inspect and mutate runtime circuit breakers, concurrency, and event lifecycle status. |
| `/api/v1/admin/metrics/` | `GET` | Monitoring | Inspect queue depths, merge semaphore utilization, and webhook pipeline health. |
| `/api/v1/admin/github/sync/` | `POST` | Integration | Trigger repository metadata and issue synchronization from GitHub. |
| `/api/v1/admin/issues/` | `GET` | Metadata | List tracked issues with administrative filtering (status, project, difficulty, category, featured). |
| `/api/v1/admin/issues/<id>/` | `GET`, `PATCH` | Metadata | Retrieve or update issue points, difficulty, category, status, or featured state. |
| `/api/v1/admin/participants/<id>/` | `GET` | Moderation | Retrieve detailed participant user record and moderation status. |
| `/api/v1/admin/participants/<id>/suspend/` | `POST` | Moderation | Suspend or reinstate a participant with mandatory audit reasoning. |
| `/api/v1/admin/points/adjust/` | `POST` | Ledger | Apply manual point adjustments or penalties to a participant's ledger balance. |
| `/api/v1/admin/audit-logs/` | `GET` | Compliance | Paginated audit trail of all administrative actions. |

---

## 3. Detailed Endpoint Specifications

### 3.1. System Controls (`/api/v1/admin/controls/`)

Inspect and modify the singleton `EventConfig` runtime controls.

#### `GET /api/v1/admin/controls/`
Retrieves current circuit breakers and event parameters.

**Response `200 OK`**:
```json
{
  "event_status": "active",
  "merge_concurrency": 5,
  "max_contributions_per_day": 5,
  "max_points_per_day": 500,
  "merge_paused": false,
  "validation_paused": false,
  "submissions_paused": false,
  "leaderboard_frozen": false,
  "leaderboard_frozen_at": null
}
```

#### `PATCH /api/v1/admin/controls/`
Mutate one or more runtime settings. All mutations are recorded in `AuditLog`.

**Request Body**:
```json
{
  "merge_paused": true,
  "leaderboard_frozen": true,
  "merge_concurrency": 10,
  "event_status": "paused",
  "reason": "Emergency investigation into merge worker backlog"
}
```

**Field Constraints**:
- `event_status`: One of `"pending"`, `"active"`, `"paused"`, `"ended"`.
- `merge_concurrency`: Integer between `1` and `50`.
- `max_contributions_per_day`: Integer `>= 1`.
- `max_points_per_day`: Integer `>= 1`.
- `merge_paused`: Boolean.
- `validation_paused`: Boolean.
- `submissions_paused`: Boolean.
- `leaderboard_frozen`: Boolean.
- `reason`: Optional string describing reason for audit records.

**Response `200 OK`**: Returns updated controls object.

---

### 3.2. Pipeline & Queue Metrics (`/api/v1/admin/metrics/`)

#### `GET /api/v1/admin/metrics/`
Provides real-time visibility into asynchronous worker queues and merge semaphores without synchronous GitHub API calls.

**Response `200 OK`**:
```json
{
  "event_status": "active",
  "system_status": {
    "merge_paused": false,
    "validation_paused": false,
    "submissions_paused": false,
    "leaderboard_frozen": false
  },
  "queues": {
    "validation_queued": 2,
    "validation_under_review": 1,
    "merge_approved": 4,
    "merge_active": 1,
    "flagged_or_retry": 0,
    "webhooks_total": 1420,
    "webhooks_unprocessed": 0
  },
  "semaphore": {
    "configured_concurrency": 5,
    "active_semaphore_slots": 1,
    "available_slots": 4
  },
  "oldest_queued_item_age_seconds": 12,
  "last_webhook_received_at": "2026-09-19T14:30:00Z",
  "generated_at": "2026-09-19T14:30:15Z"
}
```

---

### 3.3. GitHub Repository Synchronization (`/api/v1/admin/github/sync/`)

#### `POST /api/v1/admin/github/sync/`
Triggers synchronization of repository metadata and contribution issues from GitHub.
- **Throttling**: Rate-limited per admin (`admin_sync` scope: `10/minute`).
- **Debounce**: Protected by a 15-second cache mutex per repository to prevent concurrent stampedes.

**Request Body**:
```json
{
  "repo": "Hackit-DROID/Open-Source-Contribution-Drive",
  "sync_issues": true,
  "async_mode": false,
  "reason": "Scheduled sync of newly added beginner issues"
}
```

**Parameters**:
- `repo` *(string, optional)*: Target repository (`owner/name`). Defaults to `Hackit-DROID/Open-Source-Contribution-Drive`.
- `sync_issues` *(boolean, optional)*: Whether to synchronize issues. Defaults to `true`.
- `async_mode` *(boolean, optional)*: If `true`, dispatches background Celery task and returns `202 Accepted`. If `false`, executes synchronously and returns `200 OK`.
- `reason` *(string, optional)*: Reason for audit logging.

**Response `200 OK` (Synchronous)**:
```json
{
  "status": "completed",
  "project": {
    "id": 1,
    "full_name": "Hackit-DROID/Open-Source-Contribution-Drive",
    "created": false
  },
  "issues_created": 4,
  "issues_updated": 12
}
```

**Response `202 Accepted` (Asynchronous)**:
```json
{
  "status": "enqueued",
  "task_id": "87f3b890-349c-482a-bc9e-e3fa029f6350",
  "repo": "Hackit-DROID/Open-Source-Contribution-Drive",
  "sync_issues": true
}
```

**Response `409 Conflict` (Debounced)**:
```json
{
  "status": "conflict",
  "error": "A sync operation for 'Hackit-DROID/Open-Source-Contribution-Drive' is currently in progress or was triggered within the last 15 seconds. Please wait before retrying.",
  "repo": "Hackit-DROID/Open-Source-Contribution-Drive"
}
```

---

### 3.4. Issue Metadata Management (`/api/v1/admin/issues/`)

#### `GET /api/v1/admin/issues/`
Query parameters for filtering:
- `status`: `"open"`, `"closed"`, `"disabled"`.
- `difficulty`: `"beginner"`, `"intermediate"`, `"advanced"`.
- `category`: `"backend"`, `"frontend"`, `"fullstack"`, `"docs"`, `"devops"`, `"design"`, `"mobile"`.
- `project`: Repository name or slug.
- `is_featured`: `"true"` or `"false"`.
- `page`, `page_size`: Pagination parameters.

#### `GET /api/v1/admin/issues/<id>/`
Returns full issue detail.

#### `PATCH /api/v1/admin/issues/<id>/`
Update issue points, difficulty tier, category, status, or featured state.

**Security Constraint**: Mass-assignment protection strictly rejects any attempt to overwrite immutable fields (`github_issue_id`, `number`, `project`, `created_at`).

**Request Body**:
```json
{
  "points": 150,
  "difficulty": "advanced",
  "category": "backend",
  "is_featured": true,
  "status": "open",
  "reason": "Reassessed difficulty based on architectural complexity"
}
```

**Response `200 OK`**:
```json
{
  "id": 42,
  "github_issue_id": 456789,
  "project": 1,
  "project_full_name": "Hackit-DROID/Open-Source-Contribution-Drive",
  "number": 105,
  "title": "Optimize Redis pipeline throughput",
  "points": 150,
  "difficulty": "advanced",
  "category": "backend",
  "status": "open",
  "is_featured": true,
  "labels": ["enhancement", "performance"],
  "created_at": "2026-09-18T10:00:00Z",
  "created_by_github_id": 987654
}
```

---

### 3.5. Participant Moderation (`/api/v1/admin/participants/`)

#### `GET /api/v1/admin/participants/<id>/`
Retrieve administrator view of a participant including authentication details and flags.

#### `POST /api/v1/admin/participants/<id>/suspend/`
Suspend or reinstate a participant. Automatically invalidates cached leaderboards.

**Request Body**:
```json
{
  "is_suspended": true,
  "reason": "Repeated automated spam pull requests detected"
}
```

**Field Requirements**:
- `is_suspended`: Boolean (required).
- `reason`: String with at least 3 characters (required).

**Response `200 OK`**:
```json
{
  "id": 14,
  "user_id": 18,
  "username": "spammer_user",
  "email": "spammer@example.com",
  "github_id": 112233,
  "github_username": "spammer_user",
  "avatar_url": null,
  "is_suspended": true,
  "total_points": 100,
  "merged_count": 1,
  "is_staff": false,
  "is_superuser": false
}
```

---

### 3.6. Manual Point Adjustments (`/api/v1/admin/points/adjust/`)

#### `POST /api/v1/admin/points/adjust/`
Manually credit or deduct points from a participant's ledger balance with row-level locks and non-negative balance checks.

**Request Body**:
```json
{
  "participant_id": 14,
  "points": 50,
  "reason": "Special bonus for organizing community workshop"
}
```

**Field Requirements**:
- `participant_id`: Integer ID of the target `Participant`.
- `points`: Non-zero integer (positive for credit, negative for penalty).
- `reason`: Non-empty explanation string.

**Balance Guard**: Adjustments that would cause `total_points` to drop below zero are rejected with `400 Bad Request`.

**Response `200 OK`**:
```json
{
  "status": "success",
  "participant_id": 14,
  "github_username": "sarah_dev",
  "previous_points": 200,
  "new_points": 250,
  "delta": 50,
  "transaction_id": 381,
  "reason": "Special bonus for organizing community workshop"
}
```

---

### 3.7. Audit Log Inspection (`/api/v1/admin/audit-logs/`)

#### `GET /api/v1/admin/audit-logs/`
Inspect administrative activity logs.

**Query Parameters**:
- `action`: Filter by action identifier (`admin_update_system_controls`, `admin_point_adjustment`, `admin_suspend_participant`, `admin_reinstate_participant`, `admin_update_issue_metadata`, `admin_github_sync_completed`).
- `target_type`: Filter by entity type (`Participant`, `EventConfig`, `Issue`, `Project`, `Repository`).
- `page`, `page_size`: Pagination.

**Response `200 OK`**:
```json
{
  "count": 1,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": 102,
      "actor": 1,
      "actor_username": "admin_staff",
      "action": "admin_update_system_controls",
      "target_type": "EventConfig",
      "target_id": "1",
      "details": {
        "previous": { "merge_paused": false },
        "updated": { "merge_paused": true },
        "reason": "Emergency investigation into merge worker backlog"
      },
      "created_at": "2026-09-19T14:45:00Z"
    }
  ]
}
```

---

## 4. Audit Logging Standard

Every state-changing administrative action must generate an `AuditLog` entry containing:
1. `actor`: The authenticated Django `User` who initiated the action.
2. `action`: Machine-readable action code prefixed with `admin_`.
3. `target_type`: The model or entity name affected.
4. `target_id`: String identifier of the target record.
5. `details`: JSON payload documenting the previous state, new state, and administrator reason.
6. `created_at`: Timestamp automatically populated by the database.

> [!CAUTION]
> **Data Privacy & Secrets**: Sensitive credentials (passwords, GitHub access tokens, webhook HMAC secrets) are strictly forbidden from being logged in `AuditLog.details` or application log streams.
