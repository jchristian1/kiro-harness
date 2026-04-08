# Integration Test Plan — Real Kiro CLI

This document describes how to manually verify the Kiro adapter against a real
installed `kiro-cli` in a real local_folder workspace. These tests are NOT part of
the automated test suite (which mocks the subprocess). Run them manually when
validating a new kiro-cli version or adapter change.

## Prerequisites

- `kiro-cli` installed (`kiro-cli --version` works). Install: `curl -fsSL https://cli.kiro.dev/install | bash`
- A local folder with some code (any project)
- kiro-worker running locally (`uvicorn kiro_worker.main:app --port 4000`)
- `KIRO_CLI_PATH` in `.env` points to `kiro-cli` (e.g., `/home/<user>/.local/bin/kiro-cli`)

## Step 1 — Verify the CLI interface

```bash
kiro-cli --version
kiro-cli chat --help
```

Confirm `kiro-cli chat --agent <agent> --no-interactive <prompt>` is the correct invocation.
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

This will block until kiro-cli completes (up to `KIRO_CLI_TIMEOUT` seconds).

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

## Step 6 — Verify parse failure handling

Trigger a run with a bad agent name to force a failure. The worker should:
- Record `parse_status = "parse_failed"` on the run
- Transition the task to `failed`
- Return a meaningful `failure_reason`

```bash
curl -s http://localhost:4000/tasks/<task_id>/runs | jq '.[0].failure_reason'
```

## What the adapter relies on (documented behavior only)

| Behavior | Source |
|---|---|
| `kiro-cli chat --agent <agent> --no-interactive <prompt>` invocation | `kiro-cli chat --help` |
| `--agent` selects the context profile/agent | `kiro-cli chat --help` |
| `--no-interactive` runs headlessly without user input | `kiro-cli chat --help` |
| JSON extracted from stdout (may have surrounding prose) | Observed kiro-cli behavior |
| Prompt is the sole task-context injection mechanism | This adapter's design |

## What the adapter does NOT rely on

- `--mode` flag (that is the Kiro IDE launcher's flag, not kiro-cli)
- `--workspace`, `--skill`, `--context`, `--output-format` flags (do not exist)
- Kiro session history or session resume
- The Kiro IDE launcher at `/usr/bin/kiro` (wrong binary)
