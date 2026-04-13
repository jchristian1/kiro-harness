# kiro-worker

Python/FastAPI backend — source of truth for all project/task/run/artifact/workspace state. Enforces the task lifecycle state machine and invokes kiro-cli as a subprocess.

## Quick Start

```bash
# Use the permanent start script (fixes .pth file automatically)
cd kiro-harness
./kiro-worker/start.sh
```

Or manually:
```bash
cd kiro-worker
source .venv/bin/activate
uvicorn kiro_worker.main:app --host 0.0.0.0 --port 4000
```

See [docs/setup.md](docs/setup.md) for full setup instructions.

## API

### Projects

| Method | Path | Purpose |
|---|---|---|
| POST | `/projects` | Create project |
| GET | `/projects/resolve?query=...` | Resolve project by id, name, or alias |
| POST | `/projects/{id}/workspaces` | Open/reuse workspace (returns reuse_decision) |
| GET | `/projects/{id}/workspace` | Get canonical workspace |
| POST | `/projects/{id}/workspace/reinitialize` | Recover broken/missing workspace |
| POST | `/projects/{id}/source-url` | Update source_url in place |
| POST | `/projects/{id}/aliases` | Add alias |
| DELETE | `/projects/{id}/aliases` | Remove alias |
| GET | `/projects/{id}/active-task` | Get active (non-terminal) task |
| POST | `/projects/{id}/resume` | Resume latest unfinished task (non-blocking) |

### Tasks

| Method | Path | Purpose |
|---|---|---|
| POST | `/tasks` | Create task (auto-resolves workspace) |
| GET | `/tasks/{id}` | Get task status + progress |
| POST | `/tasks/{id}/runs/start` | Start run (non-blocking — returns immediately) |
| POST | `/tasks/{id}/runs` | Trigger run (blocking — waits for completion) |
| GET | `/tasks/{id}/runs` | List runs |
| POST | `/tasks/{id}/approve` | Approve task (action-level gate) |
| POST | `/tasks/{id}/revise` | Submit revision instructions |
| POST | `/tasks/{id}/cancel` | Cancel active run |
| POST | `/tasks/{id}/close` | Close task (→ done) |
| POST | `/tasks/{id}/retry` | Retry failed/cancelled task (non-blocking) |
| POST | `/tasks/{id}/validate` | Start validation run (non-blocking) |

### Runs and artifacts

| Method | Path | Purpose |
|---|---|---|
| GET | `/runs/{id}` | Get run details + progress |
| GET | `/runs/{id}/artifact` | Get full structured Kiro result |

### Dashboard (read-only)

| Method | Path | Purpose |
|---|---|---|
| GET | `/dashboard/active-tasks` | All currently running tasks |
| GET | `/dashboard/active-projects` | Projects with active tasks |
| GET | `/dashboard/pending-decisions` | Tasks waiting for PM action |
| GET | `/dashboard/unfinished-tasks` | Failed/stuck tasks with resumability assessment |
| GET | `/dashboard/project-continuity` | Portfolio audit (workspace health, unfinished work, aliases, shared-path warnings) |

`/dashboard/project-continuity` accepts `?include_archived=true` to show archived projects (hidden by default).

### Cleanup

| Method | Path | Purpose |
|---|---|---|
| POST | `/cleanup/duplicate-tasks` | Bulk close duplicate dead tasks |
| POST | `/cleanup/stale-tasks` | Bulk cancel stale active tasks |
| POST | `/cleanup/dead-projects` | Bulk archive dead test/debug projects |

All cleanup endpoints accept `dry_run: true` for safe preview.

See [docs/api-examples.md](docs/api-examples.md) for curl examples.

## Non-blocking vs blocking runs

- `POST /tasks/{id}/runs` — synchronous, blocks until kiro-cli exits
- `POST /tasks/{id}/runs/start` — async, fires kiro-cli as background task, returns `{task_id, run_id, task_status, run_status: "running"}` immediately

The OpenClaw plugin uses `/runs/start` for all run-starting operations.

## Task lifecycle

```
created → opening → analyzing  → done
                              → awaiting_revision
                              → awaiting_approval → implementing → validating → done
                 → implementing → validating → done
                               → awaiting_revision
                 → validating  → done
                               → awaiting_revision
                 → failed
```

Key states:
- `analyzing` / `implementing` / `validating` — Kiro is running
- `done` — specialist run complete, PM reads result
- `awaiting_revision` — Kiro needs more input, run was cancelled, or validation failed
- `awaiting_approval` — action-level gate (PM must approve before implementation)
- `failed` — run failed; retry via `POST /tasks/{id}/retry`

## Workspace model

- Each project has a canonical workspace (pinned via `project.workspace_id`)
- `resolve_or_create_workspace` reuses the canonical workspace; creates only when none exists
- `_get_or_create_workspace_for_path` prevents duplicate workspace path records
- Workspace recovery: `POST /projects/{id}/workspace/reinitialize` handles local_folder, github_repo, and new_project sources
- Workspaces persist at `WORKSPACE_SAFE_ROOT` (default: `/home/christian/kiro-workspaces`)

## Project aliases

Aliases are stored in the Meta table (`project_aliases:{project_id}` → JSON array). Globally unique, case-insensitive. Resolve via `GET /projects/resolve?query=alias`.

## Project archival

Dead projects are archived via `POST /cleanup/dead-projects`. Archive metadata stored in Meta table (`project_archive:{project_id}`). Non-destructive — project history preserved. Archived projects hidden from `/dashboard/project-continuity` by default.

## Progress tracking

Active runs write progress to the DB as kiro-cli streams stdout:
- `runs.progress_message` — latest meaningful activity line
- `runs.last_activity_at` — timestamp of last stdout line
- `runs.partial_output` — rolling 2000-char window of recent output

## Architecture

- **State machine**: `domain/state_machine.py` — 9 states, explicit allowed transitions
- **Kiro invocation**: async subprocess with streaming stdout, structured JSON output contract
- **DB**: SQLite with WAL mode; designed for PostgreSQL upgrade
- **IDs**: ULID-based, prefixed by entity type (`proj_`, `task_`, `run_`, `art_`, `ws_`)
- **Aliases/archive**: stored in Meta table (key-value store for lightweight metadata)

See `.kiro/specs/kiro-worker-architecture-phase0/` for full architecture contracts.

## Running tests

```bash
cd kiro-worker
source .venv/bin/activate
pytest tests/ -v
```
