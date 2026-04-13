# kw-worker-tools

OpenClaw plugin that bridges the Project Manager (Telegram) to the kiro-worker backend. Exposes deterministic `kw_*` tools that call the worker HTTP API directly.

**Plugin id:** `kw-worker-tools`
**Namespace:** `kw` (agent-agnostic)

## Install

```bash
cd openclaw/kw/plugin
openclaw plugins install .
```

## Tools

### Run-starting (non-blocking)

| Tool | Endpoint | Description |
|---|---|---|
| `kw_local_folder_analyze` | POST /tasks + /runs/start | Analyze a local folder |
| `kw_github_analyze` | POST /tasks + /runs/start | Analyze a GitHub repo |
| `kw_new_project_analyze` | POST /tasks + /runs/start | Analyze a new project |
| `kw_implement` | POST /tasks + /runs/start | Implement from a completed analysis |
| `kw_approve_implement` | POST /tasks/approve | Approve and start implementation |
| `kw_validate_task` | POST /tasks/{id}/validate | Start a validation run |
| `kw_retry_task` | POST /tasks/{id}/retry | Retry a failed/cancelled task |
| `kw_resume_project` | POST /projects/{id}/resume | Resume latest unfinished project task |

All run-starting tools return `task_id`, `run_id`, and `run_status: "running"` immediately.

### Status and inspection

| Tool | Endpoint | Description |
|---|---|---|
| `kw_task_status` | GET /tasks/{id} + /runs/{id}/artifact | Full task status and structured Kiro result |
| `kw_get_project_workspace` | GET /projects/{id}/workspace | Canonical workspace for a project |
| `kw_resolve_project` | GET /projects/resolve | Resolve project by id, name, or alias |

### Lifecycle controls

| Tool | Endpoint | Description |
|---|---|---|
| `kw_complete_task` | POST /tasks/{id}/close | Close a task (→ done) |
| `kw_cancel_task` | POST /tasks/{id}/cancel | Cancel an active run |
| `kw_set_project_alias` | POST /projects/{id}/aliases | Add a friendly alias |
| `kw_update_project_source_url` | POST /projects/{id}/source-url | Update source path in place |
| `kw_reinitialize_project_workspace` | POST /projects/{id}/workspace/reinitialize | Recover broken workspace |

### Portfolio visibility

| Tool | Endpoint | Description |
|---|---|---|
| `kw_list_active_tasks` | GET /dashboard/active-tasks | All currently running tasks |
| `kw_list_active_projects` | GET /dashboard/active-projects | Projects with active tasks |
| `kw_list_pending_decisions` | GET /dashboard/pending-decisions | Tasks waiting for PM action |
| `kw_list_unfinished_tasks` | GET /dashboard/unfinished-tasks | Failed/stuck tasks with resumability |
| `kw_list_project_continuity` | GET /dashboard/project-continuity | Portfolio audit |

### Bulk cleanup

| Tool | Endpoint | Description |
|---|---|---|
| `kw_bulk_cleanup` | POST /cleanup/* | Bulk close/cancel/archive (three modes) |

## Configuration

Worker URL defaults to `http://localhost:4000`. Override via plugin config:

```json
{
  "plugins": {
    "entries": {
      "kw-worker-tools": {
        "config": {
          "workerUrl": "http://your-worker:4000"
        }
      }
    }
  }
}
```

## Skills

Each tool has a corresponding `SKILL.md` in `../skills/` that wraps it as a Telegram slash command. Deploy skills to your workspace:

```bash
cd kiro-harness
for skill in openclaw/kw/skills/*/; do
  name=$(basename $skill)
  mkdir -p ~/.openclaw/workspace-henry/skills/$name
  cp $skill/SKILL.md ~/.openclaw/workspace-henry/skills/$name/SKILL.md
done
```

## Architecture notes

- Tools call the worker HTTP API directly — no business logic in the plugin
- All run-starting tools use `/runs/start` (non-blocking) not `/runs` (blocking)
- `kw_task_status` fetches the artifact separately and formats the full structured Kiro report
- The `kw` namespace is agent-agnostic — not tied to any specific OpenClaw agent instance
