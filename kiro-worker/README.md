# kiro-worker

Python/FastAPI backend — source of truth for all project/task/run/artifact state. Enforces the task lifecycle state machine and invokes kiro-cli as a subprocess.

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

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Health check |
| POST | `/projects` | Create project |
| POST | `/projects/{id}/workspaces` | Open/clone workspace |
| GET | `/projects/{id}/active-task` | Get active (non-terminal) task |
| POST | `/tasks` | Create task |
| GET | `/tasks/{id}` | Get task status + progress |
| POST | `/tasks/{id}/runs` | Trigger run (blocking — waits for completion) |
| POST | `/tasks/{id}/runs/start` | Start run (non-blocking — returns immediately with run_id) |
| GET | `/tasks/{id}/runs` | List runs |
| POST | `/tasks/{id}/approve` | Approve task (action-level gate) |
| POST | `/tasks/{id}/revise` | Submit revision instructions |
| POST | `/tasks/{id}/close` | Close task (mark as done from validating/awaiting_revision) |
| GET | `/runs/{id}` | Get run details + progress |
| GET | `/runs/{id}/artifact` | Get full structured Kiro result |

See [docs/api-examples.md](docs/api-examples.md) for curl examples.

## Non-blocking vs blocking runs

- `POST /tasks/{id}/runs` — synchronous, blocks until kiro-cli exits, returns completed status
- `POST /tasks/{id}/runs/start` — async, fires kiro-cli as background task, returns `{task_id, run_id, task_status, run_status: "running"}` immediately

The OpenClaw plugin uses `/runs/start` for all run-starting operations.

## Task lifecycle

```
created → opening → analyzing → done
                              → awaiting_revision
                 → implementing → validating → done
                               → awaiting_revision
                 → failed
```

Key states:
- `analyzing` / `implementing` / `validating` — Kiro is running
- `done` — specialist run complete, Project Manager reads result
- `awaiting_revision` — Kiro needs more input or validation failed
- `failed` — run failed, retry via `POST /tasks/{id}/runs`

## Progress tracking

Active runs write progress to the DB as kiro-cli streams stdout:
- `runs.progress_message` — latest meaningful activity line
- `runs.last_activity_at` — timestamp of last stdout line
- `runs.partial_output` — rolling 2000-char window of recent output

These are returned in `GET /tasks/{id}` → `last_run.progress_message`.

## Architecture

- **State machine**: 9 states, transitions in `domain/state_machine.py`
- **Kiro invocation**: async subprocess with streaming stdout, structured JSON output contract
- **DB**: SQLite with WAL mode (concurrent reads during active writes), designed for PostgreSQL upgrade
- **IDs**: ULID-based, prefixed by entity type (`proj_`, `task_`, `run_`, `art_`)
- **Progress**: streaming stdout → DB writes → API → plugin

See `.kiro/specs/kiro-worker-architecture-phase0/` for full architecture contracts.

## Running tests

```bash
cd kiro-worker
source .venv/bin/activate
pytest tests/ -v
```
