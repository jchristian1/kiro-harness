# Integration Test Plan — Real Kiro CLI

This document describes how to manually verify the Kiro adapter against a real
installed Kiro CLI in a real local_folder workspace. These tests are NOT part of
the automated test suite (which mocks the subprocess). Run them manually when
validating a new Kiro CLI version or adapter change.

## Prerequisites

- Kiro CLI installed and on PATH (`kiro --version` works)
- A local folder with some code (any project)
- kiro-worker running locally (`uvicorn kiro_worker.main:app --port 4000`)
- The workspace has `.kiro/agents/repo-engineer.json` (copy from `kiro-agent-config/`)
- The workspace has `AGENTS.md` at its root (copy from `kiro-agent-config/AGENTS.md.template` and fill in)

## Step 1 — Verify the CLI interface

```bash
kiro --version
kiro chat --help
```

Confirm `kiro chat --mode <agent> <prompt>` is the correct invocation.
If the flags have changed, update `kiro_adapter.py` accordingly.

## Step 2 — Create a project and workspace

```bash
curl -s -X POST http://localhost:4000/projects \
  -H "Content-Type: application/json" \
  -d '{"name":"integration-test","source":"local_folder","source_url":"/path/to/your/project"}' \
  | jq .
```

Note the `id` field. Then open the workspace:

```bash
curl -s -X POST http://localhost:4000/projects/<project_id>/workspaces \
  -H "Content-Type: application/json" \
  -d '{}' \
  | jq .
```

## Step 3 — Create a task

```bash
curl -s -X POST http://localhost:4000/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "project_id": "<project_id>",
    "intent": "analyze_codebase",
    "source": "local_folder",
    "operation": "plan_only",
    "description": "Describe the top-level structure of this codebase."
  }' | jq .
```

Note the task `id`.

## Step 4 — Trigger an analysis run

```bash
curl -s -X POST http://localhost:4000/tasks/<task_id>/runs \
  -H "Content-Type: application/json" \
  -d '{"mode":"analyze"}' \
  | jq .
```

This will block until Kiro completes (up to `KIRO_CLI_TIMEOUT` seconds).

## Step 5 — Verify the result

```bash
curl -s http://localhost:4000/tasks/<task_id> | jq .status
# Expected: "done" (plan_only) or "awaiting_approval" (analyze_then_approve)

curl -s http://localhost:4000/tasks/<task_id>/runs | jq .
# Check parse_status = "ok"

# Get the artifact
RUN_ID=$(curl -s http://localhost:4000/tasks/<task_id>/runs | jq -r '.runs[0].id')
curl -s http://localhost:4000/runs/$RUN_ID/artifact | jq .content.headline
```

## Step 6 — Verify context loading (AGENTS.md and steering)

Check that Kiro's response reflects the project context from AGENTS.md:
- The analysis should mention the tech stack or constraints from AGENTS.md
- If `.kiro/steering/` files are present and declared in the agent's resources,
  their content should influence the analysis

If context is missing, verify:
1. `AGENTS.md` exists at the workspace root (always loaded by Kiro automatically)
2. `.kiro/agents/repo-engineer.json` exists in the workspace with
   `"resources": ["file://.kiro/steering/**/*.md"]`
3. `.kiro/steering/*.md` files exist if steering is expected

## Step 7 — Verify parse failure handling

Temporarily rename `.kiro/agents/repo-engineer.json` so the agent doesn't exist,
then trigger a run. The worker should:
- Record `parse_status = "parse_failed"` or `status = "error"` on the run
- Transition the task to `failed`
- Return a meaningful `failure_reason`

```bash
curl -s http://localhost:4000/tasks/<task_id>/runs | jq '.[0].failure_reason'
```

## What the adapter relies on (documented behavior only)

| Behavior | Source |
|---|---|
| `kiro chat --mode <agent> <prompt>` invocation | `kiro chat --help` |
| CWD = workspace path loads AGENTS.md automatically | Kiro documentation |
| `--mode` selects custom agent from `.kiro/agents/<agent>.json` | `kiro chat --help` |
| Steering loaded when declared in agent `resources` | Kiro custom agent docs |
| Prompt is the sole task-context injection mechanism | This adapter's design |
| JSON extracted from stdout (may have surrounding prose) | Observed Kiro behavior |

## What the adapter does NOT rely on

- `--workspace` flag (undocumented)
- `--skill` flag (undocumented)
- `--context` flag (undocumented)
- `--output-format` flag (undocumented)
- `--agent` flag (undocumented; use `--mode` instead)
- `--no-interactive` flag (does not exist in `kiro chat --help`)
- Kiro session history or session resume
