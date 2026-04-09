# Henry Phase 1.5 — Deterministic Smoke-Test Layer

## What this is

Phase 1.5 is the smallest correct integration layer between OpenClaw Henry and kiro-worker.

It is NOT:
- Full Henry automation
- Phase 2 (broad routing, memory, project registry)
- A fuzzy natural-language PM layer

It IS:
- 5 deterministic skills for explicit invocation
- A thin Python bridge that calls the worker HTTP API
- A smoke-test harness for the full loop: Henry → skill → bridge → worker → Kiro → worker → Henry reply

## Why deterministic

Phase 1.5 uses explicit slash-command invocation only. No fuzzy routing. No model-driven skill selection. Each skill maps to exactly one worker flow. This makes the integration:

- Easy to debug (one code path per skill)
- Easy to test (fixed inputs, fixed outputs)
- Easy to upgrade (replace bridge with plugin in Phase 2 without changing skill contracts)

## Architecture

```
OpenClaw Henry
    │
    │  /henry_local_folder_analyze {...}
    ▼
SKILL.md (user-invocable, disable-model-invocation)
    │
    │  exec: python henry_smoke.py local_folder_analyze '{...}'
    ▼
henry_smoke.py (thin bridge)
    │
    │  POST /projects, POST /projects/{id}/workspaces
    │  POST /tasks, POST /tasks/{id}/runs
    │  GET /runs/{id}/artifact
    ▼
kiro-worker (Python/FastAPI, source of truth)
    │
    │  kiro-cli chat --no-interactive --trust-all-tools <prompt>
    ▼
kiro-cli (engineering execution)
    │
    ▼
Structured JSON artifact → back up the chain → Henry reply
```

## The 5 skills

| Skill | Operation | Worker flow |
|---|---|---|
| henry_new_project_analyze | new_project_analyze | create project + workspace + task → analyze run |
| henry_github_analyze | github_analyze | same, source=github_repo |
| henry_local_folder_analyze | local_folder_analyze | same, source=local_folder |
| henry_approve_implement | approve_implement | approve task → implement run |
| henry_task_status | task_status | read task status + artifact headline |

## File ownership

| File | Lives in | Copied to Henry workspace? |
|---|---|---|
| `openclaw/henry/skills/*/SKILL.md` | repo | yes — copy to `<workspace>/skills/` |
| `openclaw/henry/scripts/henry_smoke.py` | repo | yes — copy to `<workspace>/scripts/` |
| `openclaw/henry/docs/` | repo | no — reference only |

## How to test each skill

See `INSTALL_HENRY_WORKSPACE.md` for setup. Then:

### 1. henry_local_folder_analyze

```bash
python openclaw/henry/scripts/henry_smoke.py local_folder_analyze \
  '{"name": "test-local", "path": "/tmp/e2e-test", "description": "Describe the top-level structure."}'
```

Expected: `ok: true`, `artifact_headline` populated, `findings_count > 0`

### 2. henry_new_project_analyze

```bash
python openclaw/henry/scripts/henry_smoke.py new_project_analyze \
  '{"name": "test-new", "source": "local_folder", "source_url": "/tmp/e2e-test", "description": "Describe the top-level structure."}'
```

### 3. henry_github_analyze

```bash
python openclaw/henry/scripts/henry_smoke.py github_analyze \
  '{"name": "test-github", "repo_url": "https://github.com/your-org/your-repo", "description": "Describe the top-level structure."}'
```

Note: requires git and network access. Worker must have WORKSPACE_SAFE_ROOT configured.

### 4. henry_task_status

```bash
python openclaw/henry/scripts/henry_smoke.py task_status \
  '{"task_id": "task_01..."}'
```

Use a task_id from a previous run.

### 5. henry_approve_implement

```bash
python openclaw/henry/scripts/henry_smoke.py approve_implement \
  '{"task_id": "task_01..."}'
```

Task must be in `awaiting_approval` state. Use `analyze_then_approve` operation when creating the task.

## How this scales into Phase 2

Phase 2 replaces the bridge with a real OpenClaw plugin:
- `henry_smoke.py` → OpenClaw plugin with proper tool registration
- `disable-model-invocation: true` → removed, Henry routes intelligently
- Skills gain memory/project registry lookups
- Henry gains PM behavior (clarification, approval relay, summary formatting)

The skill contracts (input/output JSON shape) stay the same. Only the transport layer changes.
