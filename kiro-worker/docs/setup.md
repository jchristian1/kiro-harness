# kiro-worker Setup Guide

## Prerequisites

- Python 3.11+
- git (for github_repo and local_repo workspace sources)
- `kiro-cli` installed and accessible (for production use): `curl -fsSL https://cli.kiro.dev/install | bash`

## Installation

```bash
# Clone the repository
git clone <repo-url>
cd kiro-worker

# Create a virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install with dev dependencies
pip install -e ".[dev]"
```

## Configuration

Copy `.env.example` to `.env` and adjust values:

```bash
cp .env.example .env
```

Key settings:

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./kiro_worker.db` | SQLite DB path (or Postgres URL for production) |
| `WORKSPACE_SAFE_ROOT` | `/tmp/kiro-worker/workspaces` | All managed workspace paths must be under this root |
| `KIRO_CLI_PATH` | `kiro-cli` | Path to the kiro-cli binary (install via `curl -fsSL https://cli.kiro.dev/install | bash`) |
| `KIRO_DEFAULT_AGENT` | `repo-engineer` | Default Kiro custom agent name |
| `KIRO_CLI_TIMEOUT` | `300` | Seconds before Kiro CLI subprocess is killed |
| `LOG_LEVEL` | `INFO` | Logging level (DEBUG, INFO, WARNING, ERROR) |
| `HOST` | `0.0.0.0` | Server bind host |
| `PORT` | `4000` | Server bind port |

## Running the Server

```bash
uvicorn kiro_worker.main:app --host 0.0.0.0 --port 4000
```

Or with auto-reload for development:

```bash
uvicorn kiro_worker.main:app --host 0.0.0.0 --port 4000 --reload
```

The server bootstraps the SQLite database on startup (creates tables if they don't exist).

## Running Migrations

```bash
alembic upgrade head
```

To create a new migration:

```bash
alembic revision -m "description_of_change"
```

## Running Tests

```bash
pytest tests/ -v
```

Run a specific test file:

```bash
pytest tests/test_state_machine.py -v
```

## Architecture Notes (Phase 1 Decisions)

### Kiro CLI Invocation Model

The adapter invokes kiro-cli using the `kiro-cli chat` subcommand:

```
kiro-cli chat --agent <agent> --no-interactive <prompt>
```

Run with `cwd=workspace_path`.

- `--agent <agent>` selects the context profile/agent
- `--no-interactive` runs headlessly without waiting for user input, required for subprocess invocation
- The prompt carries all task-specific context (intent, description, prior analysis, etc.)
- The adapter extracts the first JSON object from stdout (kiro-cli may emit prose around it)

Note: `KIRO_CLI_PATH` in `.env` must point to the `kiro-cli` binary (not the Kiro IDE launcher at `/usr/bin/kiro`). Install kiro-cli with:

```bash
curl -fsSL https://cli.kiro.dev/install | bash
```

### Synchronous Kiro Invocation

Phase 1 uses synchronous (blocking) HTTP requests for Kiro CLI invocation. The HTTP request to `POST /tasks/{id}/runs`, `POST /tasks/{id}/approve`, and `POST /tasks/{id}/revise` blocks until Kiro completes or times out. This is a known Phase 1 simplification. Phase 2+ will introduce an async job queue.

### ULID-based IDs

IDs use the ULID format (Universally Unique Lexicographically Sortable Identifier) prefixed with entity type (e.g., `proj_`, `ws_`, `task_`, `run_`, `art_`). ULIDs are sortable by creation time and UUID-compatible.

### SQLite in Phase 1

The default database is SQLite. The schema is designed for zero-migration upgrade to PostgreSQL: all IDs are TEXT (ULIDs), JSON fields are stored as TEXT, and no SQLite-specific types are used.

### Worker as System of Record

The worker DB is the authoritative source of truth for all task state. Kiro CLI is invoked as a stateless subprocess — it receives full context on every invocation and does not maintain session state.

### Workspace Safety

All managed workspace paths (new_project, github_repo) must be under `WORKSPACE_SAFE_ROOT`. Local paths (local_repo, local_folder) are opened in-place and are not required to be under the safe root.
