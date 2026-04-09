# Henry Worker Tools Plugin

OpenClaw-native tool plugin for Henry Phase 1.5. Exposes 5 deterministic callable tools that call the kiro-worker HTTP API directly.

## Tools

| Tool | Operation |
|---|---|
| henry_local_folder_analyze | Create project from local folder + analyze |
| henry_github_analyze | Clone GitHub repo + analyze |
| henry_new_project_analyze | Create new project from scratch + analyze |
| henry_task_status | Get task status + artifact headline |
| henry_approve_implement | Approve task + trigger implement run |

## Install into Henry workspace

```bash
# From repo root
HENRY_WS=/path/to/henry-workspace

# Copy plugin
cp -r openclaw/henry/plugin $HENRY_WS/plugins/henry-worker-tools

# Copy skills (slash-command wrappers)
cp -r openclaw/henry/skills/* $HENRY_WS/skills/

# Install plugin locally
openclaw plugins install $HENRY_WS/plugins/henry-worker-tools

# Or install from local path
openclaw plugins install ./plugins/henry-worker-tools
```

## Configuration

Set worker URL if not on localhost:4000:

```bash
export KIRO_WORKER_URL=http://your-worker:4000
```

## Test from Telegram

```
/henry_local_folder_analyze {"name": "test-1", "path": "/tmp/e2e-test", "description": "Describe the top-level structure."}

/henry_task_status {"task_id": "task_01..."}

/henry_approve_implement {"task_id": "task_01..."}
```

## Phase 2 upgrade path

- Replace direct HTTP calls with a proper OpenClaw service registration
- Add memory/project registry lookups in the tool execute functions
- Skills stay the same — only the tool implementations change
