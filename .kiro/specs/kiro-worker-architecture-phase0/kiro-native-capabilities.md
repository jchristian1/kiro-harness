# kiro-native-capabilities.md — What Kiro Provides vs What We Build

## Purpose

This document is the explicit, auditable map of Kiro's native capabilities and how this architecture uses them. Its job is to prevent two failure modes:

1. **Rebuilding what Kiro already provides** — wasted effort, duplicated complexity
2. **Depending on Kiro capabilities that are not ready or not appropriate for v1** — fragile architecture

Every Kiro capability is listed with a clear decision: **use in v1 / use later / do not depend on yet**, with the reason and what custom code it replaces or avoids.

---

## Capability Map

### 1. Custom Agents

**What Kiro provides:**
Configurable agent definitions with explicit tool permissions, model selection, resource access scope, and system prompt. Defined as JSON in `.kiro/agents/`. Loaded by Kiro CLI at invocation time.

| Field | Decision | Reason |
|---|---|---|
| Use in v1 | **Yes** | Replaces prompt-only role system entirely |
| Phase 1 agent | `repo-engineer` | Single agent sufficient for Phase 1 and Phase 2 |
| Config location | `.kiro/agents/repo-engineer.json` in each workspace | Version-controlled alongside the code |

**What this replaces / avoids:**
- A prompt-only role system where role descriptions are injected as text strings in every worker invocation
- Ad-hoc tool permission management (custom agents make permissions explicit and enforced)
- Per-invocation model selection logic in the worker

**What we still build:**
- The worker's Kiro adapter still constructs the task-specific context (task description, intent, prior analysis, approved plan) and passes it to the CLI invocation. Custom agents handle role config; the worker handles task context.

**Phase 1 `repo-engineer` agent spec:**

```json
{
  "name": "repo-engineer",
  "description": "General-purpose engineering agent for analysis, implementation, and validation of repo tasks",
  "model": "claude-sonnet-4-5",
  "tools": [
    "read",
    "write",
    "shell",
    "search_files",
    "get_diagnostics"
  ],
  "toolsSettings": {
    "shell": {
      "allowedCommands": ["npm *", "yarn *", "pnpm *", "python *", "pytest *", "cargo *", "go *", "git status", "git diff"],
      "deniedCommands": ["git push *", "git commit *", "rm -rf *"]
    }
  },
  "resources": [
    "file://.kiro/steering/**/*.md"
  ]
}
```

**Key notes:**
- `AGENTS.md` is always included by Kiro automatically — no entry needed in `resources`.
- `"file://.kiro/steering/**/*.md"` is required in `resources` because steering files are **not** auto-loaded for custom agents. Without this line, all steering files are silently absent.
- Tool names follow Kiro CLI built-in naming (`read`, `write`, `shell`).

---

### 2. Steering (`.kiro/steering/`)

**What Kiro provides:**
A directory of steering files in Markdown format. In regular chat sessions, these are loaded automatically. **For custom agents, steering files are NOT automatically included** — they must be explicitly declared in the agent's `resources` configuration.

| Field | Decision | Reason |
|---|---|---|
| Use in v1 | **Yes** | Eliminates re-explaining engineering standards on every invocation |
| Location | `.kiro/steering/` in each managed workspace | Must be declared in agent resources to take effect |
| Phase 1 files | `coding-standards.md`, `testing-conventions.md`, `architecture-decisions.md` | Minimum viable standards set |
| How to load | Add `"file://.kiro/steering/**/*.md"` to agent `resources` | Required — omitting this means steering is silently absent |

**What this replaces / avoids:**
- Injecting project conventions, coding standards, and architecture decisions into every Kiro prompt via the worker adapter
- Inconsistent context (different invocations including different subsets of standards)
- Token cost of re-explaining standards on every call

**What we still build:**
- The worker still injects task-specific context (task description, intent, prior analysis, approved plan). Steering handles persistent standards; the worker handles ephemeral task context.
- The worker does not manage steering file content — that is a workspace setup concern.

**Phase 1 steering file structure:**

```
.kiro/steering/
  coding-standards.md      # Language conventions, formatting, naming
  testing-conventions.md   # Test framework, coverage expectations, test naming
  architecture-decisions.md # Key ADRs, what not to change, layer boundaries
```

---

### 3. AGENTS.md

**What Kiro provides:**
A special file at the workspace root that is always included in every Kiro agent invocation. Intended for workspace-level context that every agent needs regardless of role or task.

| Field | Decision | Reason |
|---|---|---|
| Use in v1 | **Yes** | Always-present workspace context without injection overhead |
| Location | `AGENTS.md` at workspace root | Auto-loaded by Kiro CLI |
| Content | Project overview, tech stack, key constraints, what not to do | High-value, always-relevant context |

**What this replaces / avoids:**
- Injecting project overview and tech stack into every Kiro invocation
- Risk of forgetting to include critical context in a specific invocation
- Duplication of project context across multiple steering files

**Relationship to steering:**
- `AGENTS.md` = **always included automatically** by Kiro, regardless of agent config — no resource declaration needed
- `.kiro/steering/` = **not auto-loaded for custom agents** — must be explicitly declared in the agent's `resources` array
- `AGENTS.md` is the zero-config baseline; steering files are the opt-in standards layer

**Phase 1 `AGENTS.md` template:**

```markdown
# Project: [project name]

## What this is
[1-2 sentence project description]

## Tech stack
[Language, framework, key dependencies]

## Key constraints
- [Constraint 1: e.g., "Do not modify the public API surface without approval"]
- [Constraint 2: e.g., "All DB changes must include a migration"]
- [Constraint 3: e.g., "Tests must pass before any implementation is considered done"]

## What not to do
- Do not push to main directly
- Do not delete files without explicit instruction
- Do not install new dependencies without listing them in the implementation output
```

---

### 4. Skills

**What Kiro provides:**
Reusable, portable workflow instruction packages. A skill defines a sequence of steps or instructions for a specific type of work. Skills are invoked by name and can be shared across projects.

| Field | Decision | Reason |
|---|---|---|
| Use in v1 | **Yes** | Replaces ad-hoc prompt construction in the worker adapter |
| Phase 1 skills | `analysis-workflow`, `implementation-workflow`, `validation-workflow` | One skill per task operation type |
| Location | `.kiro/skills/` in workspace or shared skill registry | Version-controlled, reusable |

**What this replaces / avoids:**
- Ad-hoc prompt strings constructed in the worker adapter for each operation type
- Duplicated workflow instructions across multiple worker code paths
- Non-version-controlled prompt logic embedded in application code
- The `command-dispatch: tool` pattern in Project Manager skills allows clean invocation of `kw-worker-tools` plugin tools without ad-hoc HTTP client code

**What we still build:**
- The worker adapter still selects which skill to invoke based on the task operation (analyze → `analysis-workflow`, implement → `implementation-workflow`, validate → `validation-workflow`)
- The worker still passes task-specific context alongside the skill invocation
- Project Manager skills use the `command-dispatch: tool` pattern to invoke `kw-worker-tools` plugin tools

**Phase 1 skill definitions (summary):**

| Skill | Purpose | Output schema |
|---|---|---|
| `analysis-workflow` | Inspect repo, understand architecture, identify affected areas, propose implementation path | `analysis` output contract |
| `implementation-workflow` | Execute bounded changes per approved plan, run validation commands | `implementation` output contract |
| `validation-workflow` | Run validation commands, check output, summarize pass/fail | `validation` output contract |

---

### 5. Built-in Code Intelligence (tree-sitter)

**What Kiro provides:**
Built-in code intelligence using tree-sitter for syntax-aware code parsing, symbol lookup, and structural analysis. Available to all Kiro agents without additional configuration.

| Field | Decision | Reason |
|---|---|---|
| Use in v1 | **Yes — rely on it, do not replicate** | Building a custom code-intelligence layer in v1 is unnecessary complexity |
| Custom layer | **Do not build** | tree-sitter covers Phase 1 needs; custom layer adds maintenance burden with no benefit |
| LSP integration | Optional, not required in v1 | Add if specific language-server features are needed in Phase 3+ |

**What this replaces / avoids:**
- A custom code-intelligence layer in the worker or adapter
- Custom AST parsing logic
- Custom symbol extraction or dependency analysis

**What we still build:**
- Nothing. The worker passes the workspace path to Kiro CLI; Kiro's built-in intelligence handles code analysis. The worker does not need to pre-process or analyze code before invoking Kiro.

---

### 6. Session Persistence / Resume

**What Kiro provides:**
Kiro can persist session state and resume interrupted sessions at the Kiro level.

| Field | Decision | Reason |
|---|---|---|
| Use in v1 | **No — worker handles resume** | kiro-worker is the system of record; Kiro session history is not authoritative |
| Depend on Kiro session history | **Never** | Session history is ephemeral from the worker's perspective; worker DB is authoritative |
| Resume mechanism | Worker reconstructs context from DB and passes it to a fresh Kiro invocation | Reliable, auditable, not dependent on Kiro session state |

**What this replaces / avoids:**
- Nothing in v1. The worker's resume mechanism is the correct approach.

**Why not use Kiro session persistence:**
- The worker DB is the system of record. If Kiro session history and worker DB diverge, the worker DB wins.
- Kiro session history is not designed to be queried by external systems.
- Resume via fresh invocation with reconstructed context is more reliable and auditable than resuming a Kiro session.

**Resume contract:**
When the worker resumes a task, it constructs a context object from its DB:

```json
{
  "task_id": "...",
  "intent": "add_feature",
  "description": "Add JWT authentication to the API",
  "prior_analysis": { ... },
  "approved_plan": { ... },
  "resume_from": "awaiting_approval",
  "resume_reason": "User approved after interruption"
}
```

This context is passed to a fresh Kiro CLI invocation. Kiro has no memory of the previous session; the worker provides all necessary context.

---

### 7. Subagents

**What Kiro provides:**
The ability to spawn specialized sub-agents for parallel or delegated work within a Kiro session.

| Field | Decision | Reason |
|---|---|---|
| Use in v1 | **No** | Single `repo-engineer` agent is sufficient for Phase 1 and Phase 2 |
| Use later | **Yes — Phase 9** | When multi-role team is needed (repo-analyst, backend-engineer, frontend-engineer, test-engineer, pr-writer) |
| Architecture impact | Worker must be able to handle multi-agent output in Phase 9 | Output contract should be designed to accommodate this |

**What this replaces / avoids (when used):**
- Sequential single-agent execution for tasks that can be parallelized
- Monolithic agent doing analysis + implementation + validation in one pass

**Phase 9 plan:**
Worker routes to the appropriate custom agent based on task type. Subagents handle specialized subtasks. Output contract is extended to handle multi-agent results. The Project Manager does not need to know which agents were used.

---

### 8. MCP (Model Context Protocol)

**What Kiro provides:**
MCP integration for connecting external tools and services to Kiro agents. Configured per agent or workspace.

| Field | Decision | Reason |
|---|---|---|
| Use in v1 | **Yes — OpenClaw plugin** | The `kw-worker-tools` plugin (id: `kw-worker-tools`) exposes 7 tools to the Project Manager agent using the `kw_` prefix |
| Use for external services | **Later — Phase 5+** | When external services (GitHub API, issue trackers, CI systems) need to be integrated |
| Architecture impact | MCP servers would be added to custom agent config when justified |

**OpenClaw plugin (`kw-worker-tools`):**

The Project Manager agent uses the `kw-worker-tools` OpenClaw plugin to call kiro-worker. The plugin exposes 7 tools:

| Tool | Purpose |
|---|---|
| `kw_local_folder_analyze` | Analyze a local folder project |
| `kw_github_analyze` | Analyze a GitHub repo |
| `kw_new_project_analyze` | Analyze a new project |
| `kw_task_status` | Get current task status and last run summary |
| `kw_approve_implement` | Approve analysis and start implementation |
| `kw_implement` | Start an implementation task directly |
| `kw_complete_task` | Close a task (validating/awaiting_revision/failed → done) |

Skills in the Project Manager agent use the `command-dispatch: tool` pattern to invoke these tools.

**What this replaces / avoids:**
- Custom HTTP client code in the Project Manager for worker API calls
- Ad-hoc tool implementations for common worker operations

**Phase 5+ plan:**
Add MCP server configs to relevant custom agents for external service integration (GitHub API, issue trackers, CI). Worker does not need to change; Kiro handles the external tool calls and includes results in structured output.

---

### 9. Hooks

**What Kiro provides:**
Lifecycle hooks for automating actions at specific points in the Kiro workflow (e.g., before/after tool use, on session start/end).

| Field | Decision | Reason |
|---|---|---|
| Use in v1 | **No** | No lifecycle automation needed in Phase 1 |
| Use later | **Yes — Phase 7** | For approval-driven delivery loop automation, pre/post implementation checks |
| Architecture impact | Hooks would be defined in workspace `.kiro/hooks/` when added |

**What this replaces / avoids (when used):**
- Custom pre/post processing logic in the worker adapter
- Manual validation steps that could be automated

---

### 10. Experimental Knowledge Features

**What Kiro provides:**
Experimental features for knowledge graph construction, codebase indexing, and semantic search over code.

| Field | Decision | Reason |
|---|---|---|
| Use in v1 | **No** | Experimental; not stable enough to depend on |
| Use later | **Evaluate in Phase 6+** | When planning/spec layer needs semantic codebase understanding |
| Architecture impact | If adopted, would replace custom codebase indexing in the worker |

---

## Summary Table

| Capability | v1 Decision | Phase | What it replaces |
|---|---|---|---|
| Custom agents | **Use** | 1 | Prompt-only role system |
| `.kiro/steering/` | **Use** | 1 | Re-prompting engineering standards (must declare in agent resources) |
| `AGENTS.md` | **Use** | 1 | Injecting project context on every call |
| Skills | **Use** | 1 | Ad-hoc prompt construction in worker adapter |
| Code intelligence (tree-sitter) | **Rely on** | 1 | Custom code-intelligence layer |
| Session persistence | **Do not depend on** | Never | Worker DB is authoritative |
| Subagents | **Use later** | 9 | Sequential single-agent execution |
| MCP | **Use — OpenClaw plugin** | 1 | Project Manager uses `kw-worker-tools` plugin (7 tools, `kw_` prefix) to call worker; external service MCP deferred to Phase 5+ |
| Hooks | **Use later** | 7 | Manual pre/post processing in worker |
| Experimental knowledge | **Evaluate later** | 6+ | Custom codebase indexing |

---

## What We Build (Not Kiro)

This is the definitive list of what the worker and surrounding system must build because Kiro does not provide it:

| Component | Owner | Why we build it |
|---|---|---|
| Project/task/run/artifact persistence | kiro-worker DB | Kiro has no persistent task model |
| Task state machine | kiro-worker | Kiro has no concept of task lifecycle or approval gates |
| Approval enforcement | kiro-worker | Kiro executes; it does not gate on external approval |
| Workspace manager (4 source modes) | kiro-worker | Kiro operates within a workspace; it does not manage workspace creation |
| Kiro CLI adapter (subprocess + parse) | kiro-worker | Worker must invoke Kiro and handle its output |
| Worker HTTP API | kiro-worker | The Project Manager needs a stable API to call; Kiro does not provide this |
| Audit log | kiro-worker | Every state transition and invocation must be recorded |
| Project Manager skills (routing + workflow policy) | Project Manager / OpenClaw agent | Kiro does not handle user-facing orchestration |
| Project Manager tools (kw-worker-tools plugin) | OpenClaw plugin (`kw-worker-tools`) | 7 tools with `kw_` prefix; skills use `command-dispatch: tool` pattern |
| Resume context reconstruction | kiro-worker | Worker reconstructs context from DB; does not rely on Kiro session |
