# kiro-worker

Backend system for managing Kiro CLI task execution. Owns all project/task/run/artifact state, enforces the task lifecycle state machine, and invokes Kiro CLI as a subprocess.

## Quick Start

```bash
pip install -e ".[dev]"
uvicorn kiro_worker.main:app --host 0.0.0.0 --port 4000
```

See [docs/setup.md](docs/setup.md) for full setup instructions.

## API

11 endpoints. See [docs/api-examples.md](docs/api-examples.md) for curl examples.

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Health check |
| POST | `/projects` | Create project |
| POST | `/projects/{id}/workspaces` | Open/clone workspace |
| GET | `/projects/{id}/active-task` | Get active task |
| POST | `/tasks` | Create task |
| GET | `/tasks/{id}` | Get task status |
| POST | `/tasks/{id}/approve` | Approve task (approval gate) |
| POST | `/tasks/{id}/runs` | Trigger run |
| GET | `/tasks/{id}/runs` | List runs |
| POST | `/tasks/{id}/revise` | Submit revision |
| GET | `/runs/{id}` | Get run details |
| GET | `/runs/{id}/artifact` | Get artifact |

## Architecture

See `.kiro/specs/kiro-worker-architecture-phase0/` for the full Phase 0 design pack.

- **State machine**: 9 states, 14 transitions, approval gate at `awaiting_approval → implementing`
- **Kiro invocation**: synchronous subprocess (Phase 1), structured JSON output contract
- **DB**: SQLite (Phase 1), designed for zero-migration upgrade to PostgreSQL
- **IDs**: ULID-based, prefixed by entity type
