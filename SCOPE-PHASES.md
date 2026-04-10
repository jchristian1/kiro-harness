# Scope and Phases

## Current status

**Phases 0–4 are complete and validated end-to-end.**

The system is running in production with:
- kiro-worker (Python/FastAPI) as source of truth
- kiro-cli as the specialist execution layer
- OpenClaw (kw-worker-tools plugin) as the Project Manager integration layer
- Telegram as the primary user interface
- 8 deterministic kw skills for all operations
- Non-blocking run model — all run-starting skills return immediately

---

## Phase 0 — Contracts ✓

Lock the contracts and explicitly decide what belongs to Kiro vs worker. Includes `kiro-native-capabilities.md` so we do not accidentally rebuild agent config, persistent standards, or code intelligence.

## Phase 1 — Worker core ✓

Build kiro-worker core:
- project/task/run/artifact registry
- workspace lifecycle
- task state machine (9 states)
- worker API (14 endpoints)
- kiro-cli invocation adapter with streaming stdout

## Phase 2 — Kiro custom agent ✓

- `kiro-agent-config/repo-engineer.json` — custom agent config
- `kiro-agent-config/AGENTS.md.template` — workspace context template
- Structured JSON output contract for analyze/implement/validate

## Phase 3 — Worker → Kiro integration ✓

- kiro-cli invoked as subprocess with `--no-interactive --trust-all-tools`
- Streaming stdout with progress updates written to DB
- JSON extraction from ANSI-stripped output
- Schema validation for all three output modes

## Phase 4 — Project Manager integration ✓

- OpenClaw plugin (`kw-worker-tools`) with 7 registered tools
- 8 SKILL.md files for Telegram slash commands
- Non-blocking run model via `/tasks/{id}/runs/start`
- Progress polling via `kw_task_status`
- PM-style completion presentation via `kw_watch_task`
- Task lifecycle management via `kw_complete_task`

**Key architectural decisions made:**
- One task = one bounded specialist run
- Completed analysis tasks end as `done` — Project Manager creates next task
- `awaiting_approval` reserved for action-level blockers only
- `kw` namespace is agent-agnostic (not tied to Henry)

---

## Phase 5 — Continuity and resume maturity

- active-task lookup
- project aliases
- resume unfinished tasks
- stable workspace reuse
- last run summaries/artifacts

## Phase 6 — Reusable workflow packaging

- Project Manager skill for routing and policy
- targeted Kiro skills for repeated engineering workflows

## Phase 7 — Specialization

- extra Kiro custom agents (deployment, QA, security, ops)
- possibly Kiro subagents for delegated or parallel work

## Phase 8 — Extension points

- MCP for external services/tools
- hooks where automation at lifecycle/tool boundaries is clearly valuable

## Phase 9 — Professional delivery workflow

- branch/commit conventions
- PR preparation
- push/PR approvals
- richer validation/reporting
- stronger permissions and safety controls

## Phase 10 — Experimental features

Only evaluate experimental Kiro features after the core system is working.

---

## Architecture model

```
Telegram → Project Manager (OpenClaw agent) → kw-worker-tools plugin → kiro-worker → kiro-cli
```

- **Project Manager** = user-facing orchestration layer (currently Henry, but agent-agnostic)
- **kiro-worker** = source of truth for all state
- **Kiro** = bounded specialist execution layer
- **kw namespace** = current plugin/tool/skill namespace (scalable to future agents)
