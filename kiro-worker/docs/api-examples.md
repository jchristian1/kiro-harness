# kiro-worker API Examples

Base URL: `http://localhost:4000`

---

## 1. POST /projects — Create a project

```bash
curl -X POST http://localhost:4000/projects \
  -H "Content-Type: application/json" \
  -d '{
    "name": "storefront-api",
    "source": "github_repo",
    "source_url": "https://github.com/acme/storefront-api"
  }'
```

Response (201):
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

---

## 2. POST /projects/{id}/workspaces — Open workspace

```bash
curl -X POST http://localhost:4000/projects/proj_01HZ3K8VXQM2N4P7R9T6W0YBCD/workspaces \
  -H "Content-Type: application/json" \
  -d '{"git_branch": "main"}'
```

Response (201):
```json
{
  "id": "ws_01HZ3K9FXQM2N4P7R9T6W0YBCE",
  "project_id": "proj_01HZ3K8VXQM2N4P7R9T6W0YBCD",
  "path": "/tmp/kiro-worker/workspaces/storefront-api",
  "git_remote": "https://github.com/acme/storefront-api",
  "git_branch": "main",
  "created_at": "2025-07-14T09:01:00Z",
  "last_accessed_at": "2025-07-14T09:01:00Z"
}
```

---

## 3. POST /tasks — Create a task

```bash
curl -X POST http://localhost:4000/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "project_id": "proj_01HZ3K8VXQM2N4P7R9T6W0YBCD",
    "intent": "add_feature",
    "source": "github_repo",
    "operation": "analyze_then_approve",
    "description": "Add JWT-based authentication to the storefront API."
  }'
```

Response (201):
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
  "updated_at": "2025-07-14T09:05:00Z",
  "last_run": null
}
```

---

## 4. GET /tasks/{id} — Get task status

```bash
curl http://localhost:4000/tasks/task_01HZ3KA2XQM2N4P7R9T6W0YBCF
```

Response (200):
```json
{
  "id": "task_01HZ3KA2XQM2N4P7R9T6W0YBCF",
  "status": "awaiting_approval",
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

---

## 5. POST /tasks/{id}/approve — Approve task

```bash
curl -X POST http://localhost:4000/tasks/task_01HZ3KA2XQM2N4P7R9T6W0YBCF/approve
```

Response (200): Updated task with `status: "implementing"` and `approved_at` set.

Error (409 — wrong state):
```json
{
  "error": {
    "code": "INVALID_STATE_FOR_APPROVAL",
    "message": "Task is not in awaiting_approval state.",
    "details": {"current_status": "implementing"}
  }
}
```

---

## 6. GET /projects/{id}/active-task — Get active task

```bash
curl http://localhost:4000/projects/proj_01HZ3K8VXQM2N4P7R9T6W0YBCD/active-task
```

Response (200): Same shape as GET /tasks/{id}.

Error (404 — no active task):
```json
{
  "error": {
    "code": "NO_ACTIVE_TASK",
    "message": "Project has no active task.",
    "details": {}
  }
}
```

---

## 7. POST /tasks/{id}/runs — Trigger a run

```bash
curl -X POST http://localhost:4000/tasks/task_01HZ3KA2XQM2N4P7R9T6W0YBCF/runs \
  -H "Content-Type: application/json" \
  -d '{"mode": "analyze"}'
```

Response (201):
```json
{
  "id": "run_01HZ3KB5XQM2N4P7R9T6W0YBCG",
  "task_id": "task_01HZ3KA2XQM2N4P7R9T6W0YBCF",
  "mode": "analyze",
  "status": "completed",
  "agent": "repo-engineer",
  "skill": "analysis-workflow",
  "started_at": "2025-07-14T09:10:00Z",
  "completed_at": "2025-07-14T09:47:00Z"
}
```

Error (409 — approval required):
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

## 8. GET /tasks/{id}/runs — List runs

```bash
curl http://localhost:4000/tasks/task_01HZ3KA2XQM2N4P7R9T6W0YBCF/runs
```

Response (200):
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
    }
  ]
}
```

---

## 9. GET /runs/{id} — Get run details

```bash
curl http://localhost:4000/runs/run_01HZ3KB5XQM2N4P7R9T6W0YBCG
```

Response (200): Full run with `context_snapshot` and `raw_output`.

---

## 10. GET /runs/{id}/artifact — Get artifact

```bash
curl http://localhost:4000/runs/run_01HZ3KB5XQM2N4P7R9T6W0YBCG/artifact
```

Response (200):
```json
{
  "id": "art_01HZ3KC8XQM2N4P7R9T6W0YBCH",
  "run_id": "run_01HZ3KB5XQM2N4P7R9T6W0YBCG",
  "task_id": "task_01HZ3KA2XQM2N4P7R9T6W0YBCF",
  "type": "analysis",
  "schema_version": "1",
  "content": { "schema_version": "1", "mode": "analyze", "headline": "..." },
  "file_path": null,
  "created_at": "2025-07-14T09:47:00Z"
}
```

---

## 11. POST /tasks/{id}/revise — Submit revision

```bash
curl -X POST http://localhost:4000/tasks/task_01HZ3KA2XQM2N4P7R9T6W0YBCF/revise \
  -H "Content-Type: application/json" \
  -d '{"instructions": "The login route should return 401 for wrong passwords, not 200."}'
```

Response (200): Updated task with `status: "implementing"`.

---

## Health Check

```bash
curl http://localhost:4000/health
```

Response (200):
```json
{"status": "ok", "version": "1.0.0"}
```
