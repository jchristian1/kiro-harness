# Requirements Document

## Introduction

This document defines the requirements for Phase 0 of the kiro-worker orchestration system. Phase 0 is a design-contract phase — the deliverable is a set of six architecture documents that define the complete contract surface for Phase 1 implementation. No code is written in Phase 0.

The system is a multi-layer software delivery pipeline: Telegram is the UI, Henry (OpenClaw agent) is the orchestrator, kiro-worker is the backend system of record, and Kiro CLI is the engineering execution layer. The six documents produced in Phase 0 must be concrete, schema-complete, and internally consistent so that Phase 1 implementation can begin without ambiguity.

## Glossary

- **Architecture_Document**: The `architecture.md` file defining system layers, boundaries, approval policy, and Kiro invocation model.
- **Task_Model_Document**: The `task-model.md` file defining the domain model for Project, Workspace, Task, Run, and Artifact.
- **State_Machine_Document**: The `state-machine.md` file defining the task lifecycle, transitions, approval checkpoints, and resume rules.
- **Worker_API_Document**: The `worker-api.md` file defining the 11 HTTP endpoints of the kiro-worker API.
- **Kiro_Output_Contract_Document**: The `kiro-output-contract.md` file defining the structured JSON output schemas Kiro must return.
- **Kiro_Native_Capabilities_Document**: The `kiro-native-capabilities.md` file defining the explicit map of Kiro-native capabilities vs custom-built components.
- **Phase_0_Documents**: The collective set of all six documents above.
- **kiro-worker**: The backend system of record that owns all project/task/run/artifact state, enforces approval policy, and invokes Kiro CLI.
- **Henry**: The OpenClaw orchestrator agent that classifies requests, calls the worker API, and communicates results to the user. Thin by design.
- **Kiro_CLI**: The engineering execution layer invoked as a subprocess by kiro-worker to perform analysis, implementation, and validation.
- **Custom_Agent**: A Kiro agent definition with explicit tool permissions, model selection, resource access, and system prompt. Defined in `.kiro/agents/`.
- **Steering**: The `.kiro/steering/` directory of Markdown files. Automatically loaded in regular Kiro chat sessions. For custom agents, steering files are **not** automatically included — they must be explicitly declared in the agent's `resources` array (e.g., `"file://.kiro/steering/**/*.md"`) to take effect.
- **AGENTS_MD**: The `AGENTS.md` file at the workspace root, always included in every Kiro agent invocation.
- **Skill**: A reusable Kiro workflow instruction package invoked by name.
- **Intent**: The classification dimension describing what the user wants to accomplish (e.g., `add_feature`, `fix_bug`).
- **Source**: The classification dimension describing where the project code lives (e.g., `github_repo`, `local_folder`).
- **Operation**: The classification dimension describing how the work should be executed (e.g., `analyze_then_approve`, `implement_now`).
- **Approval_Gate**: A point in the task lifecycle where the worker halts and waits for explicit user approval before proceeding.
- **Resume**: The act of continuing a previously interrupted task by reconstructing context from the worker DB and issuing a fresh Kiro invocation.
- **System_Of_Record**: The authoritative, persistent store for all task state. kiro-worker DB is the system of record; Kiro session history is not.

---

## Requirements

### Requirement 1: Architecture Document Content

**User Story:** As a Phase 1 implementer, I want a complete architecture document, so that I can understand every layer's role and boundaries without ambiguity.

#### Acceptance Criteria

1. THE Architecture_Document SHALL define the role of every system layer: Telegram, Henry, Henry skill, kiro-worker, Kiro CLI, Kiro custom agents, `.kiro/steering/` + `AGENTS.md`, Kiro skills, and Workspace + Registry.
2. THE Architecture_Document SHALL define what each layer owns and explicitly state what each layer does not own.
3. THE Architecture_Document SHALL define the approval policy, enumerating which actions always require approval and which actions are safe without approval.
4. THE Architecture_Document SHALL define the Kiro invocation model, including all CLI parameters, what Kiro auto-loads, and how the worker handles output.
5. THE Architecture_Document SHALL define the Intent/Source/Operation classification model with all enum values for each dimension.
6. THE Architecture_Document SHALL state that kiro-worker is the single system of record and that Kiro session history is not authoritative.
7. THE Architecture_Document SHALL state that Henry must remain thin: classify, call worker, and communicate results only.
8. THE Architecture_Document SHALL state that Kiro custom agents replace prompt-only roles and that engineering roles must not be defined as prompt strings in the worker.
9. THE Architecture_Document SHALL state that engineering standards belong in `.kiro/steering/` and `AGENTS.md`, not in worker context injection.

---

### Requirement 2: Task Model Document

**User Story:** As a Phase 1 implementer, I want a complete domain model document, so that I can implement the database schema and entity relationships without guessing field names or types.

#### Acceptance Criteria

1. THE Task_Model_Document SHALL define the full domain model including Project, Workspace, Task, Run, and Artifact entities.
2. THE Task_Model_Document SHALL include field-level schemas for each entity, specifying field name, type, required/optional status, and description.
3. THE Task_Model_Document SHALL include the Intent, Source, and Operation classification enums with all allowed values.
4. THE Task_Model_Document SHALL include concrete JSON examples for each entity showing realistic, non-placeholder field values.
5. THE Task_Model_Document SHALL include SQLite CREATE TABLE definitions for each entity, including column names, types, and constraints.
6. THE Task_Model_Document SHALL document the one-active-workspace-per-project constraint and how it is enforced.
7. WHEN the Task_Model_Document defines the Task entity status field, THE Task_Model_Document SHALL use only state names that match the states defined in the State_Machine_Document.

---

### Requirement 3: State Machine Document

**User Story:** As a Phase 1 implementer, I want a complete state machine document, so that I can implement task lifecycle transitions with explicit validation and no ambiguity about allowed paths.

#### Acceptance Criteria

1. THE State_Machine_Document SHALL define all 9 task lifecycle states: `created`, `opening`, `analyzing`, `awaiting_approval`, `implementing`, `validating`, `awaiting_revision`, `done`, and `failed`.
2. THE State_Machine_Document SHALL define every allowed state transition as an explicit table with columns: from-state, to-state, trigger, and actor.
3. THE State_Machine_Document SHALL define which transitions require an Approval_Gate and which are automatic.
4. THE State_Machine_Document SHALL define resume rules: which states are resumable, what context must be restored from the worker DB, and what the worker checks before resuming.
5. THE State_Machine_Document SHALL define failure rules: which states can transition to `failed`, what data is stored on failure, and whether retry is allowed from each failed state.
6. THE State_Machine_Document SHALL include a Mermaid state diagram showing all states and allowed transitions.
7. WHEN the State_Machine_Document references a worker API endpoint as a transition trigger, THE State_Machine_Document SHALL use only endpoint paths that are defined in the Worker_API_Document.

---

### Requirement 4: Worker API Document

**User Story:** As a Phase 1 implementer, I want a complete API contract document, so that I can implement all 11 endpoints with correct request/response schemas and state transition wiring.

#### Acceptance Criteria

1. THE Worker_API_Document SHALL define all 11 API endpoints, each with HTTP method, path, and purpose.
2. THE Worker_API_Document SHALL include a request body schema for each endpoint, specifying field name, type, required/optional status, and description.
3. THE Worker_API_Document SHALL include a response body schema for each endpoint, covering both the success shape and the error shape.
4. THE Worker_API_Document SHALL cross-reference which state transition each endpoint triggers, using state names that match the State_Machine_Document.
5. THE Worker_API_Document SHALL include concrete JSON request and response examples for each endpoint.
6. THE Worker_API_Document SHALL document all error codes and the standard error response format.
7. THE Worker_API_Document SHALL explicitly document the approval gate endpoint `POST /tasks/{id}/approve`, including its preconditions and the state transition it triggers.
8. THE Worker_API_Document SHALL document the four source modes (`new_project`, `github_repo`, `local_repo`, `local_folder`) in the project creation endpoint.

---

### Requirement 5: Kiro Output Contract Document

**User Story:** As a Phase 1 implementer, I want a complete output contract document, so that I can implement the Kiro adapter with correct JSON parsing, schema validation, and failure handling.

#### Acceptance Criteria

1. THE Kiro_Output_Contract_Document SHALL define the analysis output schema with all fields: `mode`, `headline`, `findings`, `affected_areas`, `tradeoffs`, `risks`, `implementation_steps`, `validation_commands`, `questions`, and `recommended_next_step`.
2. THE Kiro_Output_Contract_Document SHALL define the implementation output schema with all fields: `mode`, `headline`, `files_changed`, `changes_summary`, `validation_run`, `known_issues`, `follow_ups`, and `recommended_next_step`.
3. THE Kiro_Output_Contract_Document SHALL define the validation output schema with all fields: `mode`, `commands_run`, `results`, pass/fail status, `issues_found`, and `recommended_next_step`.
4. THE Kiro_Output_Contract_Document SHALL include a `schema_version` field in all three output schemas.
5. THE Kiro_Output_Contract_Document SHALL define parse failure behavior: what the worker does when Kiro returns non-JSON output, and what the worker does when Kiro returns JSON that fails schema validation.
6. THE Kiro_Output_Contract_Document SHALL include concrete JSON examples for each schema using realistic, non-placeholder values.
7. THE Kiro_Output_Contract_Document SHALL document field-level types, required vs optional status, and allowed enum values for every field in all three schemas.

---

### Requirement 6: Kiro Native Capabilities Document

**User Story:** As a Phase 1 implementer, I want an explicit map of Kiro-native capabilities vs custom-built components, so that I do not accidentally rebuild what Kiro already provides and do not depend on capabilities that are not ready.

#### Acceptance Criteria

1. THE Kiro_Native_Capabilities_Document SHALL document a use-in-v1 / use-later / do-not-depend-on decision for each Kiro capability: custom agents, `.kiro/steering/`, `AGENTS.md`, skills, built-in code intelligence, session persistence, subagents, MCP, hooks, and experimental knowledge features.
2. THE Kiro_Native_Capabilities_Document SHALL document what custom code each capability replaces or avoids building.
3. THE Kiro_Native_Capabilities_Document SHALL include the Phase 1 `repo-engineer` custom agent spec with tool list, model, resource access, and shell permissions.
4. THE Kiro_Native_Capabilities_Document SHALL include the Phase 1 steering file structure listing the files to be created under `.kiro/steering/`.
5. THE Kiro_Native_Capabilities_Document SHALL include the Phase 1 `AGENTS.md` template with required sections.
6. THE Kiro_Native_Capabilities_Document SHALL include the Phase 1 skills list: `analysis-workflow`, `implementation-workflow`, and `validation-workflow`, each with its purpose and output schema reference.
7. THE Kiro_Native_Capabilities_Document SHALL include a summary table with columns: capability, v1 decision, phase, and what it replaces.
8. THE Kiro_Native_Capabilities_Document SHALL include a "what we build" table listing every component the worker must build because Kiro does not provide it.

---

### Requirement 7: Cross-Document Consistency

**User Story:** As a Phase 1 implementer, I want all six Phase 0 documents to be internally consistent, so that I do not encounter contradictions between documents when implementing.

#### Acceptance Criteria

1. WHEN any Phase_0_Document references a task state name, THE Phase_0_Document SHALL use only state names that are defined in the State_Machine_Document.
2. WHEN any Phase_0_Document references a worker API endpoint, THE Phase_0_Document SHALL use only endpoint paths that are defined in the Worker_API_Document.
3. WHEN any Phase_0_Document references a domain entity field, THE Phase_0_Document SHALL use only field names that are defined in the Task_Model_Document.
4. WHEN any Phase_0_Document references a Kiro output schema, THE Phase_0_Document SHALL reference only schemas that are defined in the Kiro_Output_Contract_Document.
5. WHEN any Phase_0_Document states a Kiro capability decision (use / defer / avoid), THE Phase_0_Document SHALL state a decision that is consistent with the Kiro_Native_Capabilities_Document.
6. THE Phase_0_Documents SHALL contain no sections marked TBD, TODO, or "to be determined" that would block Phase 1 implementation.

---

### Requirement 8: Henry Intent/Source/Operation Model

**User Story:** As a Henry implementer, I want the Intent/Source/Operation classification model fully specified, so that I can implement request routing without ambiguity.

#### Acceptance Criteria

1. THE Architecture_Document SHALL define the `Intent` enum with values: `new_project`, `add_feature`, `refactor`, `fix_bug`, `analyze_codebase`, `upgrade_dependencies`, and `prepare_pr`.
2. THE Architecture_Document SHALL define the `Source` enum with values: `new_project`, `github_repo`, `local_repo`, and `local_folder`.
3. THE Architecture_Document SHALL define the `Operation` enum with values: `plan_only`, `analyze_then_approve`, `implement_now`, and `implement_and_prepare_pr`, and SHALL specify which operations require an Approval_Gate.
4. THE Architecture_Document SHALL state that `analyze_then_approve` is the default operation mode when the user does not explicitly request otherwise.
5. THE Worker_API_Document SHALL accept `intent`, `source`, and `operation` as fields in the task creation request body.

---

### Requirement 9: Continuity and Resume

**User Story:** As a system operator, I want the resume mechanism fully specified, so that interrupted tasks can be reliably continued without depending on Kiro session history.

#### Acceptance Criteria

1. THE State_Machine_Document SHALL define which task states are resumable and which are terminal.
2. THE State_Machine_Document SHALL define the context object the worker constructs from its DB when resuming a task, including all required fields.
3. THE Architecture_Document SHALL state that resume is performed by constructing context from the worker DB and issuing a fresh Kiro CLI invocation, not by resuming a Kiro session.
4. THE Worker_API_Document SHALL define an endpoint for retrieving the active task for a project, returning the current state and last run summary.
5. WHEN a task is in the `awaiting_approval` state and the user approves, THE State_Machine_Document SHALL define the transition to `implementing` as a resume from the approved analysis context.

---

### Requirement 10: Approval Policy

**User Story:** As a system operator, I want the approval policy fully specified with concrete definitions, so that the worker can enforce approval gates without ambiguity.

#### Acceptance Criteria

1. THE Architecture_Document SHALL enumerate all action categories that always require an Approval_Gate before execution.
2. THE Architecture_Document SHALL enumerate all action categories that are safe to execute without an Approval_Gate.
3. THE Architecture_Document SHALL state that the worker enforces the Approval_Gate, not Henry and not Kiro CLI.
4. THE Worker_API_Document SHALL define the `POST /tasks/{id}/approve` endpoint as the only mechanism for transitioning a task out of `awaiting_approval`.
5. IF a task is in `awaiting_approval` and a Kiro invocation is requested without a prior approval call, THEN THE kiro-worker SHALL reject the request and return an error indicating approval is required.
6. THE Architecture_Document SHALL define "non-trivial implementation" with a concrete, measurable definition that the worker can apply when deciding whether to require approval.

---

### Requirement 11: Kiro-Native Capability Usage

**User Story:** As a Phase 1 implementer, I want explicit guidance on which Kiro capabilities to use immediately, so that I do not rebuild what Kiro already provides.

#### Acceptance Criteria

1. THE Kiro_Native_Capabilities_Document SHALL state that Kiro custom agents are used in Phase 1 and that prompt-only role definitions in the worker are prohibited.
2. THE Kiro_Native_Capabilities_Document SHALL state that `.kiro/steering/` and `AGENTS.md` are used in Phase 1 and that the worker must not inject engineering standards as task context.
3. THE Kiro_Native_Capabilities_Document SHALL state that Kiro skills are used in Phase 1 for `analysis-workflow`, `implementation-workflow`, and `validation-workflow`.
4. THE Kiro_Native_Capabilities_Document SHALL state that Kiro's built-in code intelligence (tree-sitter) is relied upon in Phase 1 and that a custom code-intelligence layer must not be built.
5. THE Kiro_Native_Capabilities_Document SHALL state that Kiro session persistence is not used as the system of record and that the worker DB is authoritative for all task state.
6. THE Kiro_Native_Capabilities_Document SHALL state that Kiro subagents, MCP, hooks, and experimental knowledge features are deferred to later phases with the phase number specified for each.

---

### Requirement 12: Scalability Constraints

**User Story:** As a system architect, I want the Phase 0 documents to not block future phases, so that the architecture can evolve without requiring contract rewrites.

#### Acceptance Criteria

1. THE Task_Model_Document SHALL include a `schema_version` or migration-readiness note stating that the SQLite schema is designed to migrate to Postgres without model changes.
2. THE Task_Model_Document SHALL include an `owner_id` field or note its absence with a documented plan for adding it in a future phase for multi-user support.
3. THE Worker_API_Document SHALL not hard-code assumptions that prevent adding new endpoints in future phases.
4. THE Kiro_Output_Contract_Document SHALL include a `schema_version` field in all output schemas to allow non-breaking schema evolution.
5. THE Architecture_Document SHALL include a scalability notes section documenting which future capabilities (multi-agent, MCP, hooks, PR workflow, multi-user) the architecture does not block.
