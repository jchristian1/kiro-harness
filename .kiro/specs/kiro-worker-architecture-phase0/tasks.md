# Implementation Plan: kiro-worker-architecture-phase0

## Overview

Phase 0 is a design-contract phase. All tasks produce architecture documents — no code is written. Each document must be concrete, schema-complete, and implementation-ready for Phase 1. All documents must be internally consistent with `architecture.md` and `design.md`. Six documents total: architecture.md, task-model.md, state-machine.md, worker-api.md, kiro-output-contract.md, kiro-native-capabilities.md.

## Tasks

- [x] 1. Create task-model.md
  - Define the full domain model: Project, Workspace, Task, Run, Artifact
  - Include field-level schemas for each entity (id, status, timestamps, foreign keys, enums)
  - Include the Intent/Source/Operation classification model with all enum values
  - Include concrete JSON examples for each entity
  - Include the SQLite table definitions (column names, types, constraints) that Phase 1 will implement
  - Ensure one-active-workspace-per-project constraint is documented
  - Cross-reference architecture.md layer responsibilities and state-machine.md states
  - _Requirements: Phase 0 deliverable — task model contract_

- [x] 2. Create state-machine.md
  - Define all 9 task lifecycle states: created, opening, analyzing, awaiting_approval, implementing, validating, awaiting_revision, done, failed
  - Define every allowed state transition as an explicit table (from → to → trigger → actor)
  - Define which transitions require an approval gate and which are automatic
  - Define resume rules: which states are resumable, what context must be restored, what the worker checks before resuming
  - Define failure rules: which states can transition to failed, what is stored on failure, whether retry is allowed
  - Include a Mermaid state diagram
  - Cross-reference worker-api.md endpoints that trigger each transition
  - _Requirements: Phase 0 deliverable — state machine contract_

- [x] 3. Create worker-api.md
  - Define all 11 API endpoints with HTTP method, path, and purpose
  - For each endpoint: request body schema (field name, type, required/optional, description)
  - For each endpoint: response body schema (success and error shapes)
  - For each endpoint: which state transition it triggers (cross-reference state-machine.md)
  - Include concrete JSON request/response examples for each endpoint
  - Document error codes and error response format
  - Document the approval gate endpoint (POST /tasks/{id}/approve) explicitly
  - Cross-reference task-model.md entity fields used in each request/response
  - _Requirements: Phase 0 deliverable — worker API contract_

- [x] 4. Create kiro-output-contract.md
  - Define the analysis output schema with all fields (mode, headline, findings, affected_areas, tradeoffs, risks, implementation_steps, validation_commands, questions, recommended_next_step)
  - Define the implementation output schema with all fields (mode, headline, files_changed, changes_summary, validation_run, known_issues, follow_ups, recommended_next_step)
  - Define the validation output schema (mode, commands_run, results, pass/fail status, issues_found, recommended_next_step)
  - Add schema_version field to all three schemas
  - Define parse failure behavior: what the worker does when Kiro returns non-JSON or schema-invalid output
  - Include concrete JSON examples for each schema (realistic, not placeholder)
  - Document field-level types, required vs optional, and allowed enum values
  - Cross-reference which worker runs (analyze, implement, validate) produce which schema
  - _Requirements: Phase 0 deliverable — Kiro output contract_

- [x] 5. Create kiro-native-capabilities.md
  - For each Kiro capability (custom agents, steering, AGENTS.md, skills, code intelligence, session persistence, subagents, MCP, hooks, experimental knowledge): document use in v1 / use later / do not depend on yet decision with reason
  - Document what custom code each capability replaces or avoids building
  - Include the Phase 1 repo-engineer custom agent spec (tools, model, shell permissions, and resources — including the explicit steering glob `"file://.kiro/steering/**/*.md"` required to load steering files in custom agents)
  - Include the Phase 1 steering file structure and AGENTS.md template; note that AGENTS.md is always included by Kiro automatically, while steering files must be declared in the agent's resources to take effect
  - Include the Phase 1 skills list (analysis-workflow, implementation-workflow, validation-workflow)
  - Include the summary table: capability / v1 decision / phase / what it replaces
  - Include the "what we build (not Kiro)" table
  - Cross-reference architecture.md layer responsibilities
  - _Requirements: Phase 0 deliverable — Kiro-native capabilities contract_

- [x] 6. Final checkpoint — Review all documents for consistency
  - Verify all state names in state-machine.md match the states referenced in task-model.md and worker-api.md
  - Verify all API endpoints in worker-api.md map to transitions in state-machine.md
  - Verify all entity fields in worker-api.md request/response schemas exist in task-model.md
  - Verify kiro-output-contract.md schemas are referenced correctly in worker-api.md run/artifact responses
  - Verify kiro-native-capabilities.md decisions are consistent with architecture.md layer responsibilities
  - Ensure all six Phase 0 documents (architecture.md + the five above) are internally consistent
  - Ensure all documents are implementation-ready: no vague or TBD sections remain
