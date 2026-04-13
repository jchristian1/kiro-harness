# kiro-harness

A software delivery orchestration system built on three layers:

- **Telegram** — primary user interface
- **Project Manager** (OpenClaw agent) — user-facing orchestration layer
- **kiro-worker** — Python/FastAPI backend, source of truth for all task/run/artifact state
- **Kiro** — bounded specialist execution layer (analysis, implementation, validation)

**Current status: Phases 0–5.5 complete. Next: Phase 6.**

## How it works

The Project Manager receives requests from the user via Telegram, creates tasks in the worker, and Kiro executes bounded specialist runs. All state lives in the worker. The Project Manager stays thin.

```
Telegram → Project Manager (OpenClaw) → kw-worker-tools plugin → kiro-worker → kiro-cli
```

Structured JSON artifacts are part of the software contract between Kiro, the worker, and the PM layer — not just chat formatting.

## Repository structure

```
kiro-harness/
├── kiro-worker/          Python/FastAPI backend — source of truth
│   ├── src/              Worker source code
│   ├── docs/             API examples, setup guide, integration test plan
│   ├── alembic/          DB migrations
│   ├── tests/            Test suite
│   ├── start.sh          Permanent start script (fixes .pth file before starting)
│   └── README.md         Worker-specific docs
│
├── openclaw/kw/          OpenClaw integration layer (kw namespace)
│   ├── plugin/           TypeScript OpenClaw plugin (kw-worker-tools)
│   ├── skills/           SKILL.md files for Telegram slash commands
│   └── docs/             Phase docs and install guides
│
├── .kiro/specs/          Architecture specs and contracts
│   └── kiro-worker-architecture-phase0/
│
├── SCOPE-PHASES.md       Roadmap and phase definitions
└── README.md             This file
```

## Quick start

**1. Start the worker**
```bash
cd kiro-harness
./kiro-worker/start.sh
```

**2. Install the OpenClaw plugin**
```bash
cd openclaw/kw/plugin
openclaw plugins install .
```

**3. Sync skills to your workspace**
```bash
cd kiro-harness
for skill in openclaw/kw/skills/*/; do
  name=$(basename $skill)
  mkdir -p ~/.openclaw/workspace-henry/skills/$name
  cp $skill/SKILL.md ~/.openclaw/workspace-henry/skills/$name/SKILL.md
done
```

## Available skills

### Run-starting (non-blocking — return immediately with task_id + run_id)

| Skill | Description |
|---|---|
| `/kw_github_analyze` | Start Kiro analysis on a GitHub repo |
| `/kw_local_folder_analyze` | Start Kiro analysis on a local folder |
| `/kw_new_project_analyze` | Start Kiro analysis on a new project |
| `/kw_implement` | Start Kiro implementation from a completed analysis |
| `/kw_approve_implement` | Approve a task and start implementation |
| `/kw_validate_task` | Start a validation run for a completed implementation task |
| `/kw_retry_task` | Retry a failed/cancelled/unfinished task with the same parameters |
| `/kw_resume_project` | Resume the most recent unfinished task for a project |

### Status and inspection

| Skill | Description |
|---|---|
| `/kw_task_status` | Get full status and structured result of any task |
| `/kw_get_project_workspace` | Get the canonical workspace for a project |
| `/kw_resolve_project` | Resolve a project by id, name, or alias |

### Lifecycle controls

| Skill | Description |
|---|---|
| `/kw_complete_task` | Close a task (validating/awaiting_revision → done) |
| `/kw_cancel_task` | Cancel an active stuck or unwanted run |
| `/kw_set_project_alias` | Assign a friendly alias to a project |
| `/kw_update_project_source_url` | Update a project's source path in place |
| `/kw_reinitialize_project_workspace` | Recover a broken/missing project workspace |

### Portfolio visibility

| Skill | Description |
|---|---|
| `/kw_list_active_tasks` | All currently running tasks |
| `/kw_list_active_projects` | All projects with active tasks |
| `/kw_list_pending_decisions` | Tasks waiting for PM action |
| `/kw_list_unfinished_tasks` | Failed/cancelled/stuck tasks with resumability assessment |
| `/kw_list_project_continuity` | Portfolio-level audit: workspace health, unfinished work, shared-path warnings, aliases |

### Bulk cleanup

| Skill | Description |
|---|---|
| `/kw_bulk_cleanup` | Bulk close duplicate tasks, cancel stale runs, or archive dead projects |

## Normal workflow

```
1. /kw_github_analyze {"name":"my-project","repo_url":"https://github.com/org/repo","description":"Analyze the codebase"}
   → returns task_id immediately, status=analyzing

2. /kw_task_status {"task_id":"task_01..."}
   → shows progress while running, full structured report when done

3. /kw_implement {"task_id":"task_01...","description":"Implement step 1"}
   → returns task_id immediately, status=implementing

4. /kw_task_status {"task_id":"task_01..."}
   → shows implementation result

5. /kw_validate_task {"task_id":"task_01..."}
   → starts validation run, returns immediately

6. /kw_task_status {"task_id":"task_01..."}
   → shows validation result (passed/failed/issues)

7. /kw_complete_task {"task_id":"task_01..."}
   → closes task
```

## Continuity and recovery

The system has a full continuity and recovery layer:

```
/kw_list_project_continuity          — see all projects: health, unfinished work, aliases
/kw_list_unfinished_tasks            — see all unfinished tasks with resume recommendations
/kw_resume_project {"project_id":…}  — auto-retry latest unfinished task for a project
/kw_retry_task {"task_id":…}         — retry a specific failed/cancelled task
/kw_reinitialize_project_workspace   — recover a broken workspace
/kw_update_project_source_url        — repair a moved source path
```

## Portfolio hygiene

```
/kw_bulk_cleanup {"mode":"duplicate_tasks","dry_run":true}   — preview duplicate task cleanup
/kw_bulk_cleanup {"mode":"stale_tasks","stale_hours":4}      — cancel stale active tasks
/kw_bulk_cleanup {"mode":"dead_projects","dry_run":false}    — archive dead test projects
```

Archived projects are hidden from `/kw_list_project_continuity` by default. Use `include_archived: true` to show them.

## Architecture principles

- **One task = one bounded specialist run** — each task represents one unit of Kiro work
- **Worker is source of truth** — all state lives in the worker DB
- **Project Manager stays thin** — orchestration only, no business logic
- **Non-blocking runs** — all run-starting skills return immediately; Kiro runs in the background
- **Structured artifacts are the contract** — Kiro outputs structured JSON; the worker parses, stores, and exposes it
- **kw namespace** — tools and skills use `kw_` prefix, agent-agnostic

## Requirements

- Python 3.11+
- Node 22+
- kiro-cli (`curl -fsSL https://cli.kiro.dev/install | bash`)
- OpenClaw 2026.4+

## Worker API

See `kiro-worker/docs/api-examples.md` for full curl examples.

Base URL: `http://localhost:4000`

Key endpoints:
- `GET /health`
- `POST /projects`, `GET /projects/resolve`
- `POST /projects/{id}/workspaces`, `GET /projects/{id}/workspace`
- `POST /projects/{id}/workspace/reinitialize`, `POST /projects/{id}/source-url`
- `POST /projects/{id}/aliases`, `POST /projects/{id}/resume`
- `POST /tasks`, `GET /tasks/{id}`
- `POST /tasks/{id}/runs/start` — non-blocking run start
- `POST /tasks/{id}/cancel`, `POST /tasks/{id}/close`
- `POST /tasks/{id}/retry`, `POST /tasks/{id}/validate`
- `GET /runs/{id}/artifact`
- `GET /dashboard/project-continuity`, `GET /dashboard/unfinished-tasks`
- `POST /cleanup/duplicate-tasks`, `POST /cleanup/stale-tasks`, `POST /cleanup/dead-projects`

## Spec docs

Full architecture contracts are in `.kiro/specs/kiro-worker-architecture-phase0/`.
