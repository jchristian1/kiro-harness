# worker-api.md — Worker API Contract

## Purpose

This document defines the complete HTTP API contract for kiro-worker: all 11 endpoints, request/response schemas, state transition wiring, error codes, and concrete JSON examples.

**Cross-references:**
- Domain entity fields → `task-model.md`
- State transition IDs (T1–T14) → `state-machine.md`
- System layer responsibilities → `architecture.md`
- Artifact content shapes → `kiro-output-contract.md`

---

## Base URL and Conventions

- Base URL: `http://localhost:4000` (configurable)
- All request and response bodies are `application/json`
- All timestamps are ISO 8601 UTC strings
- All IDs are UUIDs stored as TEXT
- HTTP status codes: 200 OK, 201 Created, 400 Bad Request, 404 Not Found, 409 Conflict, 500 Internal Server Error

---

## Standard Error Response Format

```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human-readable description.",
    "details": {}
  }
}
```

---

## Error Codes

| Code | HTTP Status | Description |
|---|---|---|
| `VALIDATION_ERROR` | 400 | Missing required fields or invalid values |
| `NOT_FOUND` | 404 | Resource does not exist |
| `APPROVAL_REQUIRED` | 409 | Run requested on a task in `awaiting_approval` without prior approval |
| `INVALID_STATE_FOR_APPROVAL` | 409 | `POST /tasks/{id}/approve` called on task not in `awaiting_approval` |
| `INVALID_STATE_TRANSITION` | 409 | Operation would cause a forbidden state transition |
| `INVALID_STATE_FOR_RESUME` | 409 | Resume attempted on a non-resumable state |
| `INVALID_RUN_MODE` | 400 | `mode` not valid for the task's current state or operation |
| `PROJECT_NAME_CONFLICT` | 409 | Project with that name already exists |
| `WORKSPACE_ALREADY_EXISTS` | 409 | Project already has an active workspace |
| `NO_ACTIVE_TASK` | 404 | Project has no active (non-terminal) task |
| `ARTIFACT_NOT_FOUND` | 404 | Run exists but has no artifact |
| `INTERNAL_ERROR` | 500 | Unexpected server error |

---

## Endpoint Index

| # | Method | Path | Purpose |
|---|---|---|---|
| 1 | POST | `/projects` | Create a project |
| 2 | POST | `/projects/{id}/workspaces` | Open or clone a workspace |
| 3 | POST | `/tasks` | Create a task |
| 4 | GET | `/tasks/{id}` | Get task status and last run summary |
| 5 | POST | `/tasks/{id}/approve` | Approve task (approval gate) |
| 6 | GET | `/projects/{id}/active-task` | Get the active task for a project |
| 7 | POST | `/tasks/{id}/runs` | Trigger a run (analyze / implement / validate) |
| 8 | GET | `/tasks/{id}/runs` | List all runs for a task |
| 9 | GET | `/runs/{id}` | Get run details |
| 10 | GET | `/runs/{id}/artifact` | Get the artifact for a completed run |
| 11 | POST | `/tasks/{id}/revise` | Submit revision instructions |

---

## 1. POST /projects

**Purpose:** Create a new project. Does not open a workspace.

**State transition:** None.

### Request Body

| Field | Type | Required | Description |
|---|---|---|---|
| `name` | string | Yes | Unique project name |
| `source` | string | Yes | One of: `new_project`, `github_repo`, `local_repo`, `local_folder` |
| `source_url` | string | Conditional | Required for `github_repo`, `local_repo`, `local_folder`. Null for `new_project`. |

### Source Modes

| Value | `source_url` required? | Notes |
|---|---|---|
| `new_project` | No | Worker creates empty workspace |
| `github_repo` | Yes — HTTPS GitHub URL | Worker clones repo |
| `local_repo` | Yes — absolute path | Existing git repo |
| `local_folder` | Yes — absolute path | May not be a git repo |

### Response — 201 Created

```json
{
  "id": "proj_01HZ3K8VXQM2N4P7R9T6W0YBCD",
  "name": "storefront-api",
  "source": "github_repo",
  "source_url": "https://github.com/acme/storefront-api",
  "workspace_id": null,
  "owner_id": null,
  "created_at": "2025-07-14T09:00:00Z",
  "updated_at": "2025-07-14T09:00:00Z"
}
```

### Errors

| Status | Code | When |
|---|---|---|
| 400 | `VALIDATION_ERROR` | Missing `name`, invalid `source`, or missing `source_url` when required |
| 409 | `PROJECT_NAME_CONFLICT` | Name already taken |

### Error Example

```json
{
  "error": {
    "code": "PROJECT_NAME_CONFLICT",
    "message": "A project named 'storefront-api' already exists.",
    "details": { "existing_project_id": "proj_01HZ3K8VXQM2N4P7R9T6W0YBCD" }
  }
}
```

---

## 2. POST /projects/{id}/workspaces

**Purpose:** Open or clone the workspace for a project. Idempotent — returns existing workspace if already open.

**State transition:** None. Updates `projects.workspace_id`.

### Request Body

| Field | Type | Required | Description |
|---|---|---|---|
| `git_branch` | string | No | Branch to check out. Defaults to repo default. Only for `github_repo` / `local_repo`. |

### Response — 201 Created

```json
{
  "id": "ws_01HZ3K9FXQM2N4P7R9T6W0YBCE",
  "project_id": "proj_01HZ3K8VXQM2N4P7R9T6W0YBCD",
  "path": "/var/kiro-worker/workspaces/storefront-api",
  "git_remote": "https://github.com/acme/storefront-api",
  "git_branch": "main",
  "created_at": "2025-07-14T09:01:00Z",
  "last_accessed_at": "2025-07-14T09:01:00Z"
}
```

### Errors

| Status | Code | When |
|---|---|---|
| 404 | `NOT_FOUND` | Project does not exist |
| 409 | `WORKSPACE_ALREADY_EXISTS` | Project already has an active workspace |
| 500 | `INTERNAL_ERROR` | Clone failed or path outside safe root |

---

## 3. POST /tasks

**Purpose:** Create a task for a project in `created` state. Project must have an active workspace.

**State transition:** Sets `tasks.status = 'created'`.

### Request Body

| Field | Type | Required | Description |
|---|---|---|---|
| `project_id` | string | Yes | FK → `projects.id` |
| `intent` | string | Yes | One of: `new_project`, `add_feature`, `refactor`, `fix_bug`, `analyze_codebase`, `upgrade_dependencies`, `prepare_pr` |
| `source` | string | Yes | One of: `new_project`, `github_repo`, `local_repo`, `local_folder` |
| `operation` | string | Yes | One of: `plan_only`, `analyze_then_approve`, `implement_now`, `implement_and_prepare_pr` |
| `description` | string | Yes | Free-text task description from the user |

### Response — 201 Created

```json
{
  "id": "task_01HZ3KA2XQM2N4P7R9T6W0YBCF",
  "project_id": "proj_01HZ3K8VXQM2N4P7R9T6W0YBCD",
  "workspace_id": "ws_01HZ3K9FXQM2N4P7R9T6W0YBCE",
  "intent": "add_feature",
  "source": "github_repo",
  "operation": "analyze_then_approve",
  "description": "Add JWT-based authentication to the storefront API.",
  "status": "created",
  "approved_at": null,
  "created_at": "2025-07-14T09:05:00Z",
  "updated_at": "2025-07-14T09:05:00Z"
}
```

### Errors

| Status | Code | When |
|---|---|---|
| 400 | `VALIDATION_ERROR` | Missing field or invalid enum value |
| 404 | `NOT_FOUND` | Project not found or has no active workspace |

---

## 4. GET /tasks/{id}

**Purpose:** Get current task status and last run summary. Read-only.

**State transition:** None.

### Response — 200 OK

```json
{
  "id": "task_01HZ3KA2XQM2N4P7R9T6W0YBCF",
  "project_id": "proj_01HZ3K8VXQM2N4P7R9T6W0YBCD",
  "workspace_id": "ws_01HZ3K9FXQM2N4P7R9T6W0YBCE",
  "intent": "add_feature",
  "source": "github_repo",
  "operation": "analyze_then_approve",
  "description": "Add JWT-based authentication to the storefront API.",
  "status": "awaiting_approval",
  "approved_at": null,
  "created_at": "2025-07-14T09:05:00Z",
  "updated_at": "2025-07-14T09:47:00Z",
  "last_run": {
    "id": "run_01HZ3KB5XQM2N4P7R9T6W0YBCG",
    "mode": "analyze",
    "status": "completed",
    "started_at": "2025-07-14T09:10:00Z",
    "completed_at": "2025-07-14T09:47:00Z",
    "failure_reason": null
  }
}
```

### Errors

| Status | Code | When |
|---|---|---|
| 404 | `NOT_FOUND` | Task does not exist |

---

## 5. POST /tasks/{id}/approve

**Purpose:** Approve a task in `awaiting_approval`. The only mechanism to pass the approval gate. Immediately triggers an implementation run.

**State transition:** T6: `awaiting_approval → implementing`

**Cross-reference:** `state-machine.md` § T6, § Approval Gate

### Request Body

None required.

### Preconditions

1. Task must exist.
2. Task must be in `awaiting_approval`. Otherwise: 409 `INVALID_STATE_FOR_APPROVAL`.
3. At least one `analysis` artifact must exist for the task.

### What the worker does

1. Validates task is in `awaiting_approval`.
2. Sets `tasks.approved_at` to current UTC timestamp.
3. Transitions `tasks.status` to `implementing`.
4. Constructs resume context from DB (task + analysis artifact).
5. Triggers new Kiro CLI invocation with `implementation-workflow` skill.
6. Creates new Run record.
7. Returns updated task.

### Response — 200 OK

```json
{
  "id": "task_01HZ3KA2XQM2N4P7R9T6W0YBCF",
  "project_id": "proj_01HZ3K8VXQM2N4P7R9T6W0YBCD",
  "workspace_id": "ws_01HZ3K9FXQM2N4P7R9T6W0YBCE",
  "intent": "add_feature",
  "source": "github_repo",
  "operation": "analyze_then_approve",
  "description": "Add JWT-based authentication to the storefront API.",
  "status": "implementing",
  "approved_at": "2025-07-14T10:02:00Z",
  "created_at": "2025-07-14T09:05:00Z",
  "updated_at": "2025-07-14T10:02:00Z",
  "last_run": {
    "id": "run_01HZ3KC1XQM2N4P7R9T6W0YBCH",
    "mode": "implement",
    "status": "running",
    "started_at": "2025-07-14T10:02:01Z",
    "completed_at": null,
    "failure_reason": null
  }
}
```

### Errors

| Status | Code | When |
|---|---|---|
| 404 | `NOT_FOUND` | Task does not exist |
| 409 | `INVALID_STATE_FOR_APPROVAL` | Task not in `awaiting_approval` |
| 409 | `INVALID_STATE_TRANSITION` | Task in `awaiting_approval` but no analysis artifact exists |

### Error Example

```json
{
  "error": {
    "code": "INVALID_STATE_FOR_APPROVAL",
    "message": "Task is not in awaiting_approval state.",
    "details": { "current_status": "implementing" }
  }
}
```

---

## 6. GET /projects/{id}/active-task

**Purpose:** Get the active (non-terminal) task for a project. Used by Henry for resume flows and status checks.

**State transition:** None. Read-only.

### Response — 200 OK

Same shape as `GET /tasks/{id}`.

```json
{
  "id": "task_01HZ3KA2XQM2N4P7R9T6W0YBCF",
  "project_id": "proj_01HZ3K8VXQM2N4P7R9T6W0YBCD",
  "workspace_id": "ws_01HZ3K9FXQM2N4P7R9T6W0YBCE",
  "intent": "add_feature",
  "source": "github_repo",
  "operation": "analyze_then_approve",
  "description": "Add JWT-based authentication to the storefront API.",
  "status": "awaiting_approval",
  "approved_at": null,
  "created_at": "2025-07-14T09:05:00Z",
  "updated_at": "2025-07-14T09:47:00Z",
  "last_run": {
    "id": "run_01HZ3KB5XQM2N4P7R9T6W0YBCG",
    "mode": "analyze",
    "status": "completed",
    "started_at": "2025-07-14T09:10:00Z",
    "completed_at": "2025-07-14T09:47:00Z",
    "failure_reason": null
  }
}
```

### Errors

| Status | Code | When |
|---|---|---|
| 404 | `NOT_FOUND` | Project does not exist |
| 404 | `NO_ACTIVE_TASK` | Project has no active task |

---

## 7. POST /tasks/{id}/runs

**Purpose:** Trigger a Kiro CLI run. Drives the primary execution loop and handles retries from `failed`.

**State transitions triggered:**
- T1: `created → opening` (when mode=analyze and task is `created`)
- Retry from `failed`: re-enters appropriate in-progress state

**Rejection (not a transition):** If task is in `awaiting_approval`, returns 409 `APPROVAL_REQUIRED`. Task stays in `awaiting_approval`.

### Request Body

| Field | Type | Required | Description |
|---|---|---|---|
| `mode` | string | Yes | One of: `analyze`, `implement`, `validate` |

### Valid mode/state combinations

| Task status | Allowed modes |
|---|---|
| `created` | `analyze`, `implement` |
| `failed` | `analyze`, `implement`, `validate` (retry — must match failed phase) |
| `awaiting_approval` | None — rejected with `APPROVAL_REQUIRED` |
| Any other non-terminal | None — rejected with `INVALID_STATE_TRANSITION` |

### Response — 201 Created

```json
{
  "id": "run_01HZ3KB5XQM2N4P7R9T6W0YBCG",
  "task_id": "task_01HZ3KA2XQM2N4P7R9T6W0YBCF",
  "mode": "analyze",
  "status": "running",
  "agent": "repo-engineer",
  "skill": "analysis-workflow",
  "started_at": "2025-07-14T09:10:00Z",
  "completed_at": null
}
```

### Errors

| Status | Code | When |
|---|---|---|
| 404 | `NOT_FOUND` | Task does not exist |
| 400 | `VALIDATION_ERROR` | `mode` missing or invalid |
| 400 | `INVALID_RUN_MODE` | Mode not valid for task's current state or operation |
| 409 | `APPROVAL_REQUIRED` | Task is in `awaiting_approval` |
| 409 | `INVALID_STATE_TRANSITION` | Task already running or in terminal state |

### Error Example

```json
{
  "error": {
    "code": "APPROVAL_REQUIRED",
    "message": "Task is awaiting approval. Call POST /tasks/{id}/approve before triggering a run.",
    "details": {
      "current_status": "awaiting_approval",
      "approve_endpoint": "/tasks/task_01HZ3KA2XQM2N4P7R9T6W0YBCF/approve"
    }
  }
}
```

---

## 8. GET /tasks/{id}/runs

**Purpose:** List all runs for a task ordered by `started_at` ascending. Read-only.

**State transition:** None.

### Response — 200 OK

```json
{
  "runs": [
    {
      "id": "run_01HZ3KB5XQM2N4P7R9T6W0YBCG",
      "task_id": "task_01HZ3KA2XQM2N4P7R9T6W0YBCF",
      "mode": "analyze",
      "status": "completed",
      "agent": "repo-engineer",
      "skill": "analysis-workflow",
      "parse_status": "ok",
      "failure_reason": null,
      "started_at": "2025-07-14T09:10:00Z",
      "completed_at": "2025-07-14T09:47:00Z"
    },
    {
      "id": "run_01HZ3KC1XQM2N4P7R9T6W0YBCH",
      "task_id": "task_01HZ3KA2XQM2N4P7R9T6W0YBCF",
      "mode": "implement",
      "status": "running",
      "agent": "repo-engineer",
      "skill": "implementation-workflow",
      "parse_status": null,
      "failure_reason": null,
      "started_at": "2025-07-14T10:02:01Z",
      "completed_at": null
    }
  ]
}
```

Note: `context_snapshot` and `raw_output` are excluded from list responses. Use `GET /runs/{id}` for full details.

### Errors

| Status | Code | When |
|---|---|---|
| 404 | `NOT_FOUND` | Task does not exist |

---

## 9. GET /runs/{id}

**Purpose:** Get full details of a run including context snapshot and raw output. Read-only.

**State transition:** None.

### Response — 200 OK

```json
{
  "id": "run_01HZ3KB5XQM2N4P7R9T6W0YBCG",
  "task_id": "task_01HZ3KA2XQM2N4P7R9T6W0YBCF",
  "mode": "analyze",
  "status": "completed",
  "agent": "repo-engineer",
  "skill": "analysis-workflow",
  "context_snapshot": {
    "task_id": "task_01HZ3KA2XQM2N4P7R9T6W0YBCF",
    "intent": "add_feature",
    "source": "github_repo",
    "operation": "analyze_then_approve",
    "description": "Add JWT-based authentication to the storefront API.",
    "workspace_path": "/var/kiro-worker/workspaces/storefront-api",
    "current_status": "analyzing",
    "prior_analysis": null,
    "approved_plan": null,
    "revision_instructions": null
  },
  "raw_output": "{\"schema_version\":\"1\",\"mode\":\"analyze\",\"headline\":\"JWT auth feasible; 4 files need changes\"}",
  "parse_status": "ok",
  "failure_reason": null,
  "started_at": "2025-07-14T09:10:00Z",
  "completed_at": "2025-07-14T09:47:00Z"
}
```

### Errors

| Status | Code | When |
|---|---|---|
| 404 | `NOT_FOUND` | Run does not exist |

---

## 10. GET /runs/{id}/artifact

**Purpose:** Get the parsed, validated artifact for a completed run. Content shape depends on artifact type — see `kiro-output-contract.md`.

**State transition:** None. Read-only.

### Response — 200 OK

```json
{
  "id": "art_01HZ3KC8XQM2N4P7R9T6W0YBCH",
  "run_id": "run_01HZ3KB5XQM2N4P7R9T6W0YBCG",
  "task_id": "task_01HZ3KA2XQM2N4P7R9T6W0YBCF",
  "type": "analysis",
  "schema_version": "1",
  "content": {
    "schema_version": "1",
    "mode": "analyze",
    "headline": "JWT auth is feasible with moderate effort; 4 files need changes",
    "findings": [
      "No existing auth middleware found in src/middleware/",
      "Express 4.18 in use; jsonwebtoken 9.x is compatible",
      "User model exists but has no password field"
    ],
    "affected_areas": [
      "src/models/user.js",
      "src/routes/auth.js (new)",
      "src/middleware/auth.js (new)",
      "src/app.js"
    ],
    "tradeoffs": ["bcrypt adds ~1MB to install size"],
    "risks": ["bcrypt cost factor must be >= 12", "JWT expiry must be set explicitly"],
    "implementation_steps": [
      "Add bcrypt and jsonwebtoken to package.json",
      "Add password field to User model with bcrypt hook",
      "Create POST /auth/register and POST /auth/login",
      "Create JWT middleware",
      "Apply middleware to all non-public routes"
    ],
    "validation_commands": ["npm test", "npm run lint"],
    "questions": [],
    "recommended_next_step": "approve_and_implement"
  },
  "file_path": null,
  "created_at": "2025-07-14T09:47:00Z"
}
```

### Errors

| Status | Code | When |
|---|---|---|
| 404 | `NOT_FOUND` | Run does not exist |
| 404 | `ARTIFACT_NOT_FOUND` | Run exists but has no artifact (still running or parse failed) |

### Error Example

```json
{
  "error": {
    "code": "ARTIFACT_NOT_FOUND",
    "message": "Run has no artifact. The run may still be in progress or failed to parse.",
    "details": { "run_status": "running", "parse_status": null }
  }
}
```

---

## 11. POST /tasks/{id}/revise

**Purpose:** Submit revision instructions for a task in `awaiting_revision`. Immediately triggers a new implementation run.

**State transition:** T13: `awaiting_revision → implementing`

### Request Body

| Field | Type | Required | Description |
|---|---|---|---|
| `instructions` | string | Yes | Free-text revision instructions passed to Kiro CLI as additional context |

### Preconditions

1. Task must exist.
2. Task must be in `awaiting_revision`. Otherwise: 409 `INVALID_STATE_TRANSITION`.

### Response — 200 OK

```json
{
  "id": "task_01HZ3KA2XQM2N4P7R9T6W0YBCF",
  "project_id": "proj_01HZ3K8VXQM2N4P7R9T6W0YBCD",
  "workspace_id": "ws_01HZ3K9FXQM2N4P7R9T6W0YBCE",
  "intent": "add_feature",
  "source": "github_repo",
  "operation": "analyze_then_approve",
  "description": "Add JWT-based authentication to the storefront API.",
  "status": "implementing",
  "approved_at": "2025-07-14T10:02:00Z",
  "created_at": "2025-07-14T09:05:00Z",
  "updated_at": "2025-07-14T11:45:00Z",
  "last_run": {
    "id": "run_01HZ3KD4XQM2N4P7R9T6W0YBCI",
    "mode": "implement",
    "status": "running",
    "started_at": "2025-07-14T11:45:01Z",
    "completed_at": null,
    "failure_reason": null
  }
}
```

### Errors

| Status | Code | When |
|---|---|---|
| 404 | `NOT_FOUND` | Task does not exist |
| 400 | `VALIDATION_ERROR` | `instructions` missing or empty |
| 409 | `INVALID_STATE_TRANSITION` | Task not in `awaiting_revision` |

---

## State Transition Cross-Reference

| Endpoint | Transitions Triggered | Rejection Behavior |
|---|---|---|
| `POST /projects` | None | — |
| `POST /projects/{id}/workspaces` | None (updates `projects.workspace_id`) | 409 if workspace already exists |
| `POST /tasks` | Sets initial `status = created` | — |
| `GET /tasks/{id}` | None | — |
| `POST /tasks/{id}/approve` | T6: `awaiting_approval → implementing` | 409 `INVALID_STATE_FOR_APPROVAL` if wrong state |
| `GET /projects/{id}/active-task` | None | 404 `NO_ACTIVE_TASK` if none |
| `POST /tasks/{id}/runs` | T1: `created → opening`; retry from `failed` | 409 `APPROVAL_REQUIRED` if in `awaiting_approval` |
| `GET /tasks/{id}/runs` | None | — |
| `GET /runs/{id}` | None | — |
| `GET /runs/{id}/artifact` | None | 404 `ARTIFACT_NOT_FOUND` if no artifact |
| `POST /tasks/{id}/revise` | T13: `awaiting_revision → implementing` | 409 `INVALID_STATE_TRANSITION` if wrong state |
