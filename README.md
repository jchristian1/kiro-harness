# kiro-harness

A software delivery orchestration system built on three layers:

- **Telegram** — primary user interface
- **Project Manager** (OpenClaw agent, currently Henry) — user-facing orchestration layer
- **kiro-worker** — Python/FastAPI backend, source of truth for all task/run/artifact state
- **Kiro** — bounded specialist execution layer (analysis, implementation, validation)

## How it works

The Project Manager receives requests from the user via Telegram, creates tasks in the worker, and Kiro executes bounded specialist runs. All state lives in the worker. The Project Manager stays thin.

```
Telegram → Project Manager (OpenClaw) → kiro-worker → Kiro CLI → kiro-worker → Project Manager → Telegram
```

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
│   ├── scripts/          henry_smoke.py — dev/debug bridge
│   └── docs/             Phase docs and install guides
│
├── .kiro/specs/          Architecture specs and contracts
│   └── kiro-worker-architecture-phase0/
│
└── SCOPE-PHASES.md       Roadmap and phase definitions
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
openclaw plugins install -l .
openclaw gateway restart
```

**3. Sync skills to your workspace**
```bash
for skill in kw_local_folder_analyze kw_github_analyze kw_new_project_analyze kw_implement kw_approve_implement kw_task_status kw_complete_task kw_watch_task; do
  mkdir -p ~/.openclaw/workspace-henry/skills/$skill
  cp openclaw/kw/skills/$skill/SKILL.md ~/.openclaw/workspace-henry/skills/$skill/SKILL.md
done
```

## Available skills

| Skill | Type | Description |
|---|---|---|
| `/kw_github_analyze` | run-starting | Start Kiro analysis on a GitHub repo — returns immediately |
| `/kw_local_folder_analyze` | run-starting | Start Kiro analysis on a local folder — returns immediately |
| `/kw_new_project_analyze` | run-starting | Start Kiro analysis on a new project — returns immediately |
| `/kw_implement` | run-starting | Start Kiro implementation from a completed analysis — returns immediately |
| `/kw_approve_implement` | run-starting | Approve a task and start implementation — returns immediately |
| `/kw_task_status` | status | Get full status and structured result of any task |
| `/kw_watch_task` | status | Watch an active task with 10-second progress updates |
| `/kw_complete_task` | lifecycle | Close a task stuck in validating or awaiting_revision |

All run-starting skills return `task_id`, `run_id`, and active status immediately. Use `/kw_task_status` to poll progress and get the full structured result when complete.

## Normal workflow

```
1. /kw_github_analyze {"name":"my-project","repo_url":"https://github.com/org/repo","description":"Analyze the codebase"}
   → returns task_id immediately, status=analyzing

2. /kw_task_status {"task_id":"task_01..."}
   → shows progress while running, full structured report when done

3. /kw_implement {"task_id":"task_01...","description":"Implement step 1","step_index":0}
   → returns task_id immediately, status=implementing

4. /kw_task_status {"task_id":"task_01..."}
   → shows implementation result

5. /kw_complete_task {"task_id":"task_01..."}
   → closes task if validation is not needed
```

## Architecture principles

- **One task = one bounded specialist run** — each task represents one unit of Kiro work
- **Worker is source of truth** — all state lives in the worker DB
- **Project Manager stays thin** — orchestration only, no business logic
- **Non-blocking runs** — all run-starting skills return immediately; Kiro runs in the background
- **kw namespace** — tools and skills use `kw_` prefix, not agent-instance names

## Requirements

- Python 3.11+
- Node 22+
- kiro-cli (`curl -fsSL https://cli.kiro.dev/install | bash`)
- OpenClaw 2026.4+

## Worker API

See `kiro-worker/docs/api-examples.md` for full curl examples.

Base URL: `http://localhost:4000`

Key endpoints:
- `GET /health` — health check
- `POST /projects` — create project
- `POST /projects/{id}/workspaces` — open workspace
- `POST /tasks` — create task
- `POST /tasks/{id}/runs/start` — start run (non-blocking, returns immediately)
- `GET /tasks/{id}` — get task status + progress
- `GET /runs/{id}/artifact` — get full structured Kiro result
- `POST /tasks/{id}/close` — close task

## Spec docs

Full architecture contracts are in `.kiro/specs/kiro-worker-architecture-phase0/`:
- `architecture.md` — system layers and responsibilities
- `state-machine.md` — task lifecycle and transitions
- `worker-api.md` — API contract
- `kiro-output-contract.md` — Kiro structured output schemas
