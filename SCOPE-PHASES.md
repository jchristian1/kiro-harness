# Scope and Phases

## Current status

**Phases 0–5.5 are complete and validated end-to-end.**

The system is running in production with:
- `kiro-worker` (Python/FastAPI) as the source of truth
- `kiro-cli` as the specialist execution layer
- OpenClaw (`kw-worker-tools` plugin) as the Project Manager integration layer
- Telegram as the primary user interface
- deterministic `kw_*` skills for the full PM lifecycle
- non-blocking run model — all run-starting skills return immediately with `task_id`, `run_id`, and active status
- worker-backed continuity, recovery, retry, resume, validation, and portfolio hygiene

**Next: Phase 6 — Reusable workflow packaging**

---

## Phase 0 — Contracts ✓

Lock the contracts and explicitly decide what belongs to Kiro vs worker.

Includes:
- `kiro-native-capabilities.md`
- explicit role boundaries between Project Manager, worker/backend, and Kiro specialist execution

---

## Phase 1 — Worker core ✓

Build `kiro-worker` core:
- project / task / run / artifact registry
- workspace lifecycle
- task state machine
- worker API
- `kiro-cli` invocation adapter
- streaming stdout handling
- artifact persistence
- lifecycle transitions for active, completed, revised, and cancelled work

---

## Phase 2 — Kiro custom agent ✓

Create the Kiro specialist contract:
- `kiro-agent-config/repo-engineer.json`
- `kiro-agent-config/AGENTS.md.template`
- structured JSON output contract for analyze, implement, validate

---

## Phase 3 — Worker → Kiro integration ✓

Integrate the worker with Kiro execution:
- `kiro-cli` invoked as subprocess with `--no-interactive --trust-all-tools`
- streaming stdout with progress updates written to DB
- JSON extraction from ANSI-stripped output
- schema validation for all output modes
- process tracking for cancellation and monitoring

---

## Phase 4 — Project Manager integration ✓

Build the OpenClaw / Telegram Project Manager layer:
- OpenClaw plugin: `kw-worker-tools`
- deterministic `kw_*` tools and `SKILL.md` wrappers
- Telegram slash-command access
- non-blocking run model via worker-backed async start endpoints
- `kw_task_status` for task inspection
- `kw_complete_task` for explicit close-out
- `kw_cancel_task` for stopping stuck or unwanted active runs
- active task / project visibility and PM decision views

**Key architectural decisions:**
- one task = one bounded specialist run
- completed analysis tasks end as `done`; PM creates the next task
- `awaiting_approval` is reserved for action-level blockers only
- `kw` namespace is agent-agnostic
- the PM remains the active orchestration layer; Kiro is the specialist layer

---

## Phase 5 — Continuity, recovery, and PM visibility maturity ✓

Strengthened continuity and PM operating maturity across the full project lifecycle.

### Delivered

**Unfinished-task visibility**
- `GET /dashboard/unfinished-tasks` — all failed/awaiting_revision/awaiting_approval/stuck tasks
- `kw_list_unfinished_tasks` — PM-facing view with resumability assessment and recommended next action

**Stable workspace reuse**
- `resolve_or_create_workspace` — reuses canonical workspace, creates only when none exists
- `get_canonical_workspace` — prefers pinned workspace, falls back to most-recently-accessed valid path
- `_get_or_create_workspace_for_path` — duplicate-path-safe workspace creation across all run-starting flows
- `POST /projects/{id}/workspaces` — now returns `reuse_decision` (reused/created)
- `GET /projects/{id}/workspace` — canonical workspace for PM visibility

**Project continuity audit**
- `GET /dashboard/project-continuity` — portfolio-level audit with workspace health (healthy/stale/invalid/missing), unfinished task counts, shared-path warnings, aliases, and recommended PM action
- `kw_list_project_continuity` — PM-facing portfolio view, sorted by urgency
- Archived projects hidden by default; `include_archived=true` to show them

**Workspace recovery**
- `POST /projects/{id}/workspace/reinitialize` — source-specific recovery (rebound/recreated/blocked)
- `kw_reinitialize_project_workspace` — PM-facing recovery with outcome icons and shared-path warnings

**In-place source update**
- `POST /projects/{id}/source-url` — update `source_url` without creating a new project
- `kw_update_project_source_url` — PM-facing source repair with path-exists check

**Shared-path safety**
- `_get_or_create_workspace_for_path` — reuses existing workspace record for a path, never creates duplicates
- `shared_path_warning` in recovery responses and continuity audit
- Cross-project path reuse is allowed but always surfaced explicitly to the PM

**Project aliases**
- `POST /projects/{id}/aliases` — add alias (globally unique, case-insensitive)
- `DELETE /projects/{id}/aliases` — remove alias
- `GET /projects/resolve?query=...` — resolve project by id, name, or alias
- `kw_set_project_alias`, `kw_resolve_project` — PM-facing alias management
- Aliases visible in `kw_list_project_continuity` output

---

## Phase 5.5 — PM workflow acceleration and lifecycle polish ✓

Reduced manual PM stitching for retry, resume, validation, and portfolio hygiene.

### Delivered

**Smart retry and resume**
- `POST /tasks/{id}/retry` — non-blocking retry of failed/cancelled/unfinished task (clones parameters, inherits run mode)
- `POST /projects/{id}/resume` — non-blocking resume of latest unfinished project task (auto-retries or returns explicit decision type)
- `kw_retry_task`, `kw_resume_project` — PM-facing retry/resume with outcome visibility

**Minimal validation workflow**
- `POST /tasks/{id}/validate` — non-blocking validation start (creates fresh task, starts validate run)
- `kw_validate_task` — PM-facing validation start with poll instruction
- Validation outcomes (passed/failed/issues_found/commands_run) surfaced via `kw_task_status`

**Bulk cleanup**
- `POST /cleanup/duplicate-tasks` — close duplicate dead tasks (same project+operation+description, keep newest)
- `POST /cleanup/stale-tasks` — cancel active tasks with no activity for N hours
- `POST /cleanup/dead-projects` — archive test/smoke/debug projects with no active work
- `kw_bulk_cleanup` — single PM tool with three modes, dry_run support, per-item reporting

**Archival portfolio polish**
- Dead projects archived to Meta table (non-destructive, history preserved)
- Archived projects hidden from `GET /dashboard/project-continuity` by default
- `include_archived=true` query param to show archived projects explicitly
- `archived_hidden` count in summary so PM knows how many are hidden

---

## Phase 6 — Reusable workflow packaging

Package repeatable PM-to-Kiro engineering flows into reusable workflow patterns.

The continuity and recovery layer is now stable. Phase 6 builds on top of it by turning common PM actions into standardized, repeatable flows.

### Scope

- reusable workflow sequences, such as:
  - analyze → implement → validate
  - retry → validate → close
  - recover project → retry task → validate
- repeatable engineering patterns exposed as composable `kw_*` flows
- cleaner orchestration above the now-stable continuity and recovery layer
- standardized PM responses and decision patterns for common scenarios
- reduced per-feature orchestration work through reusable workflow packaging

### Goal

Move from “the PM can manually operate the system well” to “the PM can trigger well-defined reusable workflows with consistent behavior and outputs.”

---

## Phase 7 — Specialization

Expand beyond a single engineering specialist.

Scope:
- additional Kiro custom agents (deployment, QA, security, ops)
- possible Kiro subagents for delegated or parallel work
- clearer role boundaries across specialist types

---

## Phase 8 — Extension points

Add external-system integration only where it clearly improves the lifecycle.

Scope:
- MCP for external services/tools
- hooks at task/run lifecycle boundaries
- automation only where operationally valuable and architecture-safe

---

## Phase 9 — Professional delivery workflow

Turn the engineering loop into a complete delivery loop.

Scope:
- branch / commit conventions
- PR preparation and push/approval flows
- richer validation and reporting
- stronger permissions and safety controls
- merge-ready handoff artifacts

---

## Phase 10 — Experimental features

Evaluate experimental Kiro features only after the core system is mature and stable.

---

## Architecture model

```
Telegram → Project Manager (OpenClaw agent) → kw-worker-tools plugin → kiro-worker → kiro-cli
```

**Layer responsibilities:**
- **Telegram** — primary UI, slash commands
- **Project Manager** — user-facing orchestration, thin, no business logic
- **kw-worker-tools plugin** — deterministic tool bridge, calls worker HTTP API
- **kiro-worker** — source of truth, state machine, task/run/artifact registry, workspace management
- **kiro-cli** — bounded specialist execution (analyze, implement, validate)

**Invariants:**
- one task = one bounded specialist run
- worker is always the source of truth
- structured JSON artifacts are part of the software contract between Kiro, the worker, and the PM layer
- non-blocking start-and-track is the standard run model
- `kw` namespace is agent-agnostic
