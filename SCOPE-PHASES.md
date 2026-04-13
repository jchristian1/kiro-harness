# Scope and Phases

## Current status

**Phases 0–4 are complete and validated end-to-end.**

The system is running in production with:
- `kiro-worker` (Python/FastAPI) as the source of truth
- `kiro-cli` as the specialist execution layer
- OpenClaw (`kw-worker-tools` plugin) as the Project Manager integration layer
- Telegram as the primary user interface
- deterministic `kw_*` skills for task lifecycle, execution, monitoring, and control
- a non-blocking run model — all run-starting skills return immediately with `task_id`, `run_id`, and active status
- worker-backed progress tracking and PM-style monitoring/control flows

The system now supports:
- analyze → implement → validate / complete workflow
- live task progress inspection
- active task / active project visibility
- pending-decision visibility
- task completion for optional-validation cases
- task cancellation for stuck or unwanted runs
- PM-style supervision over bounded Kiro specialist runs

---

## Phase 0 — Contracts ✓

Lock the contracts and explicitly decide what belongs to Kiro vs worker.

Includes:
- `kiro-native-capabilities.md`
- explicit role boundaries between:
  - Project Manager / Project Lead
  - worker/backend
  - Kiro specialist execution

This phase prevented accidental rebuilding of agent config, persistent standards, or code intelligence in the wrong layer.

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
- structured JSON output contract for:
  - analyze
  - implement
  - validate

This phase established bounded specialist execution with parseable outputs.

---

## Phase 3 — Worker → Kiro integration ✓

Integrate the worker with Kiro execution:

- `kiro-cli` invoked as subprocess with `--no-interactive --trust-all-tools`
- streaming stdout with progress updates written to DB
- JSON extraction from ANSI-stripped output
- schema validation for all output modes
- progress persistence on active runs
- process tracking needed for cancellation and monitoring

---

## Phase 4 — Project Manager integration ✓

Build the OpenClaw / Telegram Project Manager layer:

- OpenClaw plugin: `kw-worker-tools`
- deterministic `kw_*` tools and `SKILL.md` wrappers
- Telegram slash-command access
- non-blocking run model via worker-backed async start endpoints
- `kw_task_status` for task inspection
- `kw_watch_task` for PM-style progress monitoring
- `kw_complete_task` for explicit close-out of optional-validation tasks
- `kw_cancel_task` for stopping stuck or unwanted active runs
- active task / project visibility and PM decision views
- improved PM-style result presentation over structured worker artifacts

**Key architectural decisions made:**
- one task = one bounded specialist run
- completed analysis tasks end as `done`
- the Project Manager creates the next task after analysis
- `awaiting_approval` is reserved for action-level blockers only
- `kw` namespace is agent-agnostic and not tied to Henry
- the model remains active as the Project Manager layer; Kiro remains the specialist layer

---

## Phase 5 — Continuity, resume, and manager visibility maturity → IN PROGRESS

The next phase is to strengthen continuity and PM operating maturity.

Scope:
- active-task lookup improvements
- project aliases
- resume unfinished tasks cleanly
- stable workspace reuse
- last run summaries / artifact recall
- better portfolio-level PM visibility
- stronger “what needs my attention?” flows
- cleaner monitoring and supervision behavior across multiple active runs

This phase turns the system from “works per task” into “works reliably over time.”

---

## Phase 6 — Reusable workflow packaging

Package repeatable workflows into reusable manager/specialist patterns.

Scope:
- Project Manager routing skill/policy
- repeated engineering workflows as reusable `kw_*` flows
- common patterns for:
  - analyze → implement
  - implement → validate
  - watch → cancel / complete
- clearer standardized response and decision patterns

This phase reduces per-feature orchestration work and makes the system easier to extend.

---

## Phase 7 — Specialization

Expand beyond a single engineering specialist.

Scope:
- additional Kiro custom agents for:
  - deployment
  - QA
  - security
  - ops
- possible Kiro subagents for delegated or parallel work
- clearer role boundaries across specialist types

This phase generalizes the architecture beyond repo engineering.

---

## Phase 8 — Extension points

Add external-system integration only where it clearly improves the lifecycle.

Scope:
- MCP for external services/tools
- hooks at task/run lifecycle boundaries
- automation only where it is operationally valuable and does not break source-of-truth design

This phase should remain disciplined and architecture-first.

---

## Phase 9 — Professional delivery workflow

Turn the engineering loop into a complete delivery loop.

Scope:
- branch / commit conventions
- PR preparation
- push / PR approvals
- richer validation and reporting
- stronger permissions and safety controls
- cleaner merge-ready handoff artifacts

This phase makes the system suitable for professional software delivery teams.

---

## Phase 10 — Experimental features

Only evaluate experimental Kiro features after the core system is mature and stable.

Scope:
- selective experimental Kiro features
- controlled trials only after the core workflow is reliable

---

## Architecture model

```text
Telegram → Project Manager (OpenClaw agent) → kw-worker-tools plugin → kiro-worker → kiro-cli