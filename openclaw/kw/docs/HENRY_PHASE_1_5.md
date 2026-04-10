# KW Integration Layer — Project Manager + Kiro Worker

## What this is

The `openclaw/kw/` directory contains the OpenClaw integration layer between the Project Manager (currently Henry) and the kiro-worker backend.

It is NOT:
- Full PM automation
- A fuzzy natural-language routing layer
- A replacement for the worker as source of truth

It IS:
- 8 deterministic skills for explicit invocation from Telegram
- A TypeScript OpenClaw plugin (`kw-worker-tools`) that calls the worker HTTP API directly
- A non-blocking run model where all run-starting skills return immediately

## Architecture

```
Telegram
    │
    │  /kw_github_analyze {...}
    ▼
SKILL.md (command-dispatch: tool)
    │
    │  dispatches to kw_github_analyze tool
    ▼
kw-worker-tools plugin (TypeScript)
    │
    │  POST /projects, POST /projects/{id}/workspaces
    │  POST /tasks, POST /tasks/{id}/runs/start  ← non-blocking
    ▼
kiro-worker (Python/FastAPI, source of truth)
    │
    │  kiro-cli chat --no-interactive --trust-all-tools <prompt>
    ▼
kiro-cli (specialist execution)
    │
    ▼
Structured JSON artifact → stored in worker DB → surfaced via kw_task_status
```

## Non-blocking run model

All run-starting skills return immediately with:
- `task_id` — for tracking
- `run_id` — for tracking
- `task_status` — current active state (analyzing, implementing, validating)
- `message` — acknowledgement

The run executes in the background. Use `/kw_task_status` to poll progress and get the full structured result when complete.

## The 8 skills

| Skill | Type | Worker flow |
|---|---|---|
| `kw_github_analyze` | run-starting | create project + workspace + task → start analyze run (async) |
| `kw_local_folder_analyze` | run-starting | same, source=local_folder |
| `kw_new_project_analyze` | run-starting | same, source=new_project |
| `kw_implement` | run-starting | create new implementation task → start implement run (async) |
| `kw_approve_implement` | run-starting | approve task → start implement run (async) |
| `kw_task_status` | status | get full task status + structured Kiro result |
| `kw_watch_task` | status | watch active task with 10-second progress updates |
| `kw_complete_task` | lifecycle | close task stuck in validating/awaiting_revision |

## File ownership

| File | Lives in | Deploy to workspace? |
|---|---|---|
| `openclaw/kw/skills/*/SKILL.md` | repo | yes — copy to `~/.openclaw/workspace-henry/skills/` |
| `openclaw/kw/plugin/` | repo | yes — `openclaw plugins install -l .` |
| `openclaw/kw/scripts/henry_smoke.py` | repo | optional — dev/debug only |
| `openclaw/kw/docs/` | repo | no — reference only |

## How to deploy

See `INSTALL_KW_WORKSPACE.md` for full setup instructions.

## How to test each skill

```bash
# Start a GitHub analysis (returns immediately)
# In Telegram: /kw_github_analyze {"name":"test","repo_url":"https://github.com/org/repo","description":"Analyze the codebase"}

# Check status (poll until done)
# In Telegram: /kw_task_status {"task_id":"task_01..."}

# Watch with progress updates
# In Telegram: /kw_watch_task {"task_id":"task_01..."}

# Start implementation from completed analysis
# In Telegram: /kw_implement {"task_id":"task_01...","description":"Implement step 1","step_index":0}

# Close a task stuck in validating
# In Telegram: /kw_complete_task {"task_id":"task_01..."}
```

## How this scales

The `kw` namespace is agent-agnostic. A future agent named Smith would:
1. Install the same `kw-worker-tools` plugin
2. Create its own `smith_*` skill wrappers that dispatch to the same `kw_*` tools
3. No worker or plugin changes needed

The Project Manager role is architectural. Henry is just the current instance name.
