# Installing Henry Phase 1.5 into an OpenClaw Workspace

## Prerequisites

- OpenClaw installed and running
- kiro-worker running on `http://localhost:4000` (or set `KIRO_WORKER_URL`)
- kiro-cli installed (`kiro-cli --version` works)
- Python 3.11+ on PATH

## Step 1 — Copy files into the Henry workspace

The Henry workspace is the OpenClaw workspace where Henry runs. Copy these files:

```bash
# Set your Henry workspace path
HENRY_WS=/path/to/henry-workspace

# Create directories
mkdir -p $HENRY_WS/skills/henry_new_project_analyze
mkdir -p $HENRY_WS/skills/henry_github_analyze
mkdir -p $HENRY_WS/skills/henry_local_folder_analyze
mkdir -p $HENRY_WS/skills/henry_approve_implement
mkdir -p $HENRY_WS/skills/henry_task_status
mkdir -p $HENRY_WS/scripts

# Copy skills
cp openclaw/henry/skills/henry_new_project_analyze/SKILL.md $HENRY_WS/skills/henry_new_project_analyze/
cp openclaw/henry/skills/henry_github_analyze/SKILL.md $HENRY_WS/skills/henry_github_analyze/
cp openclaw/henry/skills/henry_local_folder_analyze/SKILL.md $HENRY_WS/skills/henry_local_folder_analyze/
cp openclaw/henry/skills/henry_approve_implement/SKILL.md $HENRY_WS/skills/henry_approve_implement/
cp openclaw/henry/skills/henry_task_status/SKILL.md $HENRY_WS/skills/henry_task_status/

# Copy bridge script
cp openclaw/henry/scripts/henry_smoke.py $HENRY_WS/scripts/
```

## Step 2 — Configure worker URL (optional)

If kiro-worker is not on `http://localhost:4000`, set the env var:

```bash
export KIRO_WORKER_URL=http://your-worker-host:4000
```

Add this to your OpenClaw agent environment config if needed.

## Step 3 — Verify skills loaded

Start a new OpenClaw session and run:

```
openclaw skills list
```

You should see all 5 `henry_*` skills listed.

## Step 4 — Test the bridge directly

Before testing via OpenClaw, verify the bridge works standalone:

```bash
# Health check
curl http://localhost:4000/health

# Test local folder analyze
python $HENRY_WS/scripts/henry_smoke.py local_folder_analyze \
  '{"name": "henry-smoke-test", "path": "/tmp/e2e-test", "description": "Describe the top-level structure."}'
```

Expected output:
```json
{
  "ok": true,
  "project_id": "proj_...",
  "task_id": "task_...",
  "run_id": "run_...",
  "run_status": "completed",
  "artifact_headline": "...",
  "findings_count": 5,
  "recommended_next_step": "no_action_needed"
}
```

## Step 5 — Test via OpenClaw slash commands

In an OpenClaw Henry session:

```
/henry_local_folder_analyze {"name": "henry-test", "path": "/tmp/e2e-test", "description": "Describe the top-level structure."}
```

```
/henry_task_status {"task_id": "task_01..."}
```

## Placeholders to replace

| Placeholder | Replace with |
|---|---|
| `/path/to/henry-workspace` | Absolute path to your OpenClaw Henry workspace |
| `/tmp/e2e-test` | Any local folder with code |
| `https://github.com/your-org/your-repo` | A real GitHub repo URL |
| `task_01...` | A real task ID from a previous run |

## Updating skills

Skills in `<workspace>/skills/` take precedence over all other locations. To update:

```bash
cp openclaw/henry/skills/<skill>/SKILL.md $HENRY_WS/skills/<skill>/
```

Restart the OpenClaw session to pick up changes (`/new` in chat or gateway restart).
