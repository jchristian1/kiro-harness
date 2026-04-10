# kiro-output-contract.md — Kiro Output Contract

## Purpose

This document defines the structured JSON output schemas that Kiro CLI must return to kiro-worker. It is the contract that the Kiro adapter implementation must follow exactly.

**Critical principle:** Kiro must always return structured JSON. Prose-only output is treated as a parse failure. The worker captures stdout, attempts JSON parse, validates against the schema for the run mode, and stores the result as an artifact. If parse or validation fails, the run is marked failed and the task transitions to `failed`.

**Cross-references:**
- Run modes and artifact types → `task-model.md` § Run Mode, Artifact Type
- Parse failure → task state transition → `state-machine.md` § Failure Rules
- Artifact storage and retrieval → `worker-api.md` § `GET /runs/{id}/artifact`
- Worker invocation model → `architecture.md` § Kiro Invocation Model

---

## Schema-to-Run Mapping

Each run mode produces exactly one artifact type with one output schema.

| Run mode (`runs.mode`) | Artifact type (`artifacts.type`) | Output schema |
|---|---|---|
| `analyze` | `analysis` | Analysis Output Schema |
| `implement` | `implementation` | Implementation Output Schema |
| `validate` | `validation` | Validation Output Schema |

The `mode` field in the JSON output must match the run mode. A mismatch is a schema validation failure.

---

## Analysis Output Schema

Produced by: `analyze` runs (skill: `analysis-workflow`)
Stored as: artifact type `analysis`

### Field Reference

| Field | Type | Required | Allowed values / format | Description |
|---|---|---|---|---|
| `schema_version` | string | Yes | `"1"` | Schema version. Must be `"1"` for this contract. |
| `mode` | string | Yes | `"analyze"` | Must be exactly `"analyze"`. |
| `headline` | string | Yes | Free text, ≤ 200 chars | One-sentence summary of the analysis conclusion. |
| `findings` | array of string | Yes | Non-empty array | Concrete observations about the codebase relevant to the task. Each entry is one finding. |
| `affected_areas` | array of string | Yes | Non-empty array | File paths or module names that will be touched by the implementation. |
| `tradeoffs` | array of string | Yes | May be empty array | Design or dependency tradeoffs the implementer should be aware of. |
| `risks` | array of string | Yes | May be empty array | Security, correctness, or stability risks that must be addressed. |
| `implementation_steps` | array of string | Yes | Non-empty array | Ordered list of concrete steps Kiro will take during implementation. |
| `validation_commands` | array of string | Yes | May be empty array | Shell commands to run after implementation to verify correctness (e.g., `npm test`). |
| `questions` | array of string | Yes | May be empty array | Clarifying questions for the user, if any. Empty array if none. |
| `recommended_next_step` | string | Yes | `"approve_and_implement"`, `"request_clarification"`, `"no_action_needed"` | Worker uses this to determine the next state transition. |

### `recommended_next_step` Enum Values

| Value | Meaning | Worker behavior |
|---|---|---|
| `approve_and_implement` | Analysis is complete; implementation is ready to proceed | Worker transitions task to `done`. The Project Manager reads the artifact and creates a new `implement_now` task when the user approves. |
| `request_clarification` | Kiro has questions that must be answered before implementation can proceed | Worker transitions task to `awaiting_revision`; Project Manager surfaces the `questions` array to the user |
| `no_action_needed` | Analysis found nothing to implement (e.g., feature already exists) | Worker transitions task to `done` |

### JSON Example

```json
{
  "schema_version": "1",
  "mode": "analyze",
  "headline": "JWT auth is feasible with moderate effort; 4 files need changes, no breaking API surface",
  "findings": [
    "No existing auth middleware found in src/middleware/",
    "Express 4.18 is in use; jsonwebtoken 9.x is compatible",
    "User model exists in src/models/user.js but has no password field",
    "All current routes are unprotected; no route-level auth guards exist",
    "bcrypt is not in package.json; must be added as a dependency"
  ],
  "affected_areas": [
    "src/models/user.js",
    "src/routes/auth.js (new file)",
    "src/middleware/auth.js (new file)",
    "src/app.js"
  ],
  "tradeoffs": [
    "Adding bcrypt increases install size by ~1MB and adds a native compilation step",
    "Stateless JWT means no server-side session revocation without a token blocklist",
    "Storing JWT secret in environment variable requires deployment config change"
  ],
  "risks": [
    "Password hashing must use bcrypt with cost factor >= 12 to meet security baseline",
    "Token expiry must be set explicitly; omitting it creates non-expiring tokens",
    "JWT secret must be at least 32 bytes; short secrets are brute-forceable"
  ],
  "implementation_steps": [
    "Add bcrypt and jsonwebtoken to package.json dependencies",
    "Add password field to User model with pre-save bcrypt hashing hook",
    "Create POST /auth/register route: validate input, hash password, create user, return token",
    "Create POST /auth/login route: find user, compare password, return token",
    "Create src/middleware/auth.js: extract Bearer token, verify with jsonwebtoken, attach user to req",
    "Apply auth middleware to all non-public routes in src/app.js"
  ],
  "validation_commands": [
    "npm test",
    "npm run lint"
  ],
  "questions": [],
  "recommended_next_step": "approve_and_implement"
}
```

---

## Implementation Output Schema

Produced by: `implement` runs (skill: `implementation-workflow`)
Stored as: artifact type `implementation`

### Field Reference

| Field | Type | Required | Allowed values / format | Description |
|---|---|---|---|---|
| `schema_version` | string | Yes | `"1"` | Schema version. Must be `"1"` for this contract. |
| `mode` | string | Yes | `"implement"` | Must be exactly `"implement"`. |
| `headline` | string | Yes | Free text, ≤ 200 chars | One-sentence summary of what was implemented. |
| `files_changed` | array of FileChange | Yes | Non-empty array | List of files created, modified, or deleted. See FileChange schema below. |
| `changes_summary` | string | Yes | Free text | Human-readable prose summary of all changes made. Used by the Project Manager to communicate results to the user. |
| `validation_run` | ValidationRun or null | Yes | Object or null | Result of any validation commands Kiro ran inline during implementation. Null if no validation was run. |
| `known_issues` | array of string | Yes | May be empty array | Issues Kiro was unable to resolve during implementation. Empty array if none. |
| `follow_ups` | array of string | Yes | May be empty array | Recommended follow-up actions for the user or next run (e.g., "add integration tests for the login route"). |
| `recommended_next_step` | string | Yes | `"run_validation"`, `"request_review"`, `"needs_follow_up"` | Worker uses this to determine the next state transition. |

### FileChange Schema

Each entry in `files_changed` is an object:

| Field | Type | Required | Allowed values | Description |
|---|---|---|---|---|
| `path` | string | Yes | Relative file path | Path relative to workspace root. |
| `action` | string | Yes | `"created"`, `"modified"`, `"deleted"` | What happened to the file. |
| `description` | string | Yes | Free text | One-sentence description of what changed in this file. |

### ValidationRun Schema (inline)

The `validation_run` field, when not null, is an object:

| Field | Type | Required | Description |
|---|---|---|---|
| `commands` | array of string | Yes | Commands that were run. |
| `passed` | boolean | Yes | True if all commands exited 0. |
| `output_excerpt` | string | Yes | Last 500 chars of combined stdout/stderr, for context. |

### `recommended_next_step` Enum Values

| Value | Meaning | Worker behavior |
|---|---|---|
| `run_validation` | Implementation complete; ready for validation run | Worker transitions task to `validating` and triggers a `validate` run |
| `request_review` | Implementation complete but human review is recommended before validation | Worker transitions task to `awaiting_revision` with a note |
| `needs_follow_up` | Implementation is partial; `known_issues` or `follow_ups` require attention | Worker transitions task to `awaiting_revision` |

### JSON Example

```json
{
  "schema_version": "1",
  "mode": "implement",
  "headline": "JWT authentication implemented: register, login, and protected route middleware added",
  "files_changed": [
    {
      "path": "src/models/user.js",
      "action": "modified",
      "description": "Added password field with bcrypt pre-save hook and comparePassword instance method"
    },
    {
      "path": "src/routes/auth.js",
      "action": "created",
      "description": "New file: POST /auth/register and POST /auth/login routes with input validation"
    },
    {
      "path": "src/middleware/auth.js",
      "action": "created",
      "description": "New file: Bearer token extraction, JWT verification, and req.user attachment"
    },
    {
      "path": "src/app.js",
      "action": "modified",
      "description": "Mounted /auth routes and applied auth middleware to all routes except /auth/*"
    },
    {
      "path": "package.json",
      "action": "modified",
      "description": "Added bcrypt@5.1.1 and jsonwebtoken@9.0.2 to dependencies"
    }
  ],
  "changes_summary": "Added JWT-based authentication to the storefront API. Users can now register at POST /auth/register and log in at POST /auth/login to receive a signed JWT. All non-auth routes are protected by the new auth middleware, which validates Bearer tokens and attaches the decoded user to req.user. Passwords are hashed with bcrypt (cost factor 12). Token expiry is set to 24h via JWT_EXPIRY environment variable (default: 24h).",
  "validation_run": {
    "commands": ["npm test"],
    "passed": true,
    "output_excerpt": "  23 passing (1.4s)\n  0 failing\n\nnpm test exited with code 0"
  },
  "known_issues": [],
  "follow_ups": [
    "Add integration tests for POST /auth/register and POST /auth/login",
    "Add token refresh endpoint (POST /auth/refresh) if session longevity is required",
    "Set JWT_SECRET and JWT_EXPIRY in production environment config"
  ],
  "recommended_next_step": "run_validation"
}
```

---

## Validation Output Schema

Produced by: `validate` runs (skill: `validation-workflow`)
Stored as: artifact type `validation`

### Field Reference

| Field | Type | Required | Allowed values / format | Description |
|---|---|---|---|---|
| `schema_version` | string | Yes | `"1"` | Schema version. Must be `"1"` for this contract. |
| `mode` | string | Yes | `"validate"` | Must be exactly `"validate"`. |
| `commands_run` | array of string | Yes | Non-empty array | Shell commands that were executed during validation. |
| `results` | array of CommandResult | Yes | Non-empty array | Per-command results. One entry per command in `commands_run`, in the same order. |
| `passed` | boolean | Yes | `true` or `false` | True if all commands exited 0 and no issues were found. False otherwise. |
| `issues_found` | array of string | Yes | May be empty array | Specific issues identified during validation. Empty array if `passed` is true. |
| `recommended_next_step` | string | Yes | `"mark_done"`, `"request_revision"`, `"retry_validation"` | Worker uses this to determine the next state transition. |

### CommandResult Schema

Each entry in `results` is an object:

| Field | Type | Required | Allowed values | Description |
|---|---|---|---|---|
| `command` | string | Yes | Shell command string | The command that was run. |
| `exit_code` | integer | Yes | Any integer | Exit code returned by the command. 0 = success. |
| `passed` | boolean | Yes | `true` or `false` | True if exit_code is 0. |
| `output_excerpt` | string | Yes | Free text | Last 500 chars of combined stdout/stderr from this command. |

### `recommended_next_step` Enum Values

| Value | Meaning | Worker behavior |
|---|---|---|
| `mark_done` | All validation passed; task is complete | Worker transitions task to `done` (T10) |
| `request_revision` | Validation found issues that require implementation changes | Worker transitions task to `awaiting_revision` (T11) |
| `retry_validation` | Validation was inconclusive (e.g., flaky test, environment issue); retry recommended | Worker transitions task to `awaiting_revision` with a note to re-run validation |

### Worker behavior on `passed` vs `recommended_next_step`

The worker uses `passed` as the primary signal for the T10/T11 transition decision:

| `passed` | `recommended_next_step` | Worker action |
|---|---|---|
| `true` | `mark_done` | Transition to `done` (T10) |
| `true` | `retry_validation` | Transition to `done` (T10) — `passed=true` takes precedence |
| `false` | `request_revision` | Transition to `awaiting_revision` (T11) |
| `false` | `retry_validation` | Transition to `awaiting_revision` (T11) with retry note |
| `false` | `mark_done` | Schema validation failure — `passed=false` and `mark_done` is contradictory; worker treats as `schema_invalid` |

### JSON Example — Passing Validation

```json
{
  "schema_version": "1",
  "mode": "validate",
  "commands_run": [
    "npm test",
    "npm run lint"
  ],
  "results": [
    {
      "command": "npm test",
      "exit_code": 0,
      "passed": true,
      "output_excerpt": "  23 passing (1.4s)\n  0 failing\n\nnpm test exited with code 0"
    },
    {
      "command": "npm run lint",
      "exit_code": 0,
      "passed": true,
      "output_excerpt": "\n> storefront-api@1.4.0 lint\n> eslint src/\n\nnpm run lint exited with code 0"
    }
  ],
  "passed": true,
  "issues_found": [],
  "recommended_next_step": "mark_done"
}
```

### JSON Example — Failing Validation

```json
{
  "schema_version": "1",
  "mode": "validate",
  "commands_run": [
    "npm test",
    "npm run lint"
  ],
  "results": [
    {
      "command": "npm test",
      "exit_code": 1,
      "passed": false,
      "output_excerpt": "  22 passing (1.3s)\n  1 failing\n\n  1) POST /auth/login\n       returns 401 for wrong password:\n       AssertionError: expected 200 to equal 401\n\nnpm test exited with code 1"
    },
    {
      "command": "npm run lint",
      "exit_code": 0,
      "passed": true,
      "output_excerpt": "\n> storefront-api@1.4.0 lint\n> eslint src/\n\nnpm run lint exited with code 0"
    }
  ],
  "passed": false,
  "issues_found": [
    "POST /auth/login returns HTTP 200 instead of 401 when password is incorrect",
    "Test: 'POST /auth/login returns 401 for wrong password' is failing"
  ],
  "recommended_next_step": "request_revision"
}
```

---

## Parse Failure Behavior

### Overview

The worker processes Kiro CLI stdout in three stages:

1. **ANSI stripping** — remove ANSI escape sequences from raw stdout before any parsing
2. **JSON extraction** — locate the output contract JSON using `"schema_version"` as an anchor marker: scan backward from the last occurrence to find the opening `{`, then scan forward with brace counting to find the matching closing `}`. This handles the common case where Kiro emits tool call logs and code diffs before the final JSON.
3. **Schema validation** — validate the parsed object against the schema for the run mode

If any stage fails, the run is marked failed and the task transitions to `failed`. No artifact is created for a failed run.

### Stage 1: Non-JSON Output

**Trigger:** After ANSI stripping, no `"schema_version"` marker is found in stdout, or the JSON object surrounding it cannot be extracted, or the extracted candidate fails `json.loads()`.

**Worker actions:**
1. Set `runs.status = 'parse_failed'`
2. Set `runs.parse_status = 'parse_failed'`
3. Set `runs.failure_reason = 'parse_failed: {error_message}'` where `{error_message}` is the JSON.parse error (e.g., `parse_failed: Unexpected token < in JSON at position 0`)
4. Set `runs.raw_output` to the raw stdout (truncated to 64KB if necessary)
5. Set `runs.completed_at` to the current UTC timestamp
6. Transition task to `failed`
7. Do NOT create an artifact record

**Example failure_reason values:**
- `parse_failed: Unexpected token < in JSON at position 0` — Kiro returned an HTML error page
- `parse_failed: Unexpected end of JSON input` — Kiro output was truncated
- `parse_failed: SyntaxError: Unexpected token I in JSON at position 0` — Kiro returned prose starting with "I"
- `parse_failed: empty output` — Kiro produced no stdout

### Stage 2: Schema-Invalid JSON

**Trigger:** Kiro CLI stdout is valid JSON but fails schema validation for the expected run mode schema.

**Worker actions:**
1. Set `runs.status = 'parse_failed'`
2. Set `runs.parse_status = 'schema_invalid'`
3. Set `runs.failure_reason = 'schema_invalid: {field_path}: {validation_error}'` where `{field_path}` is the JSON path of the first failing field and `{validation_error}` is the validation message
4. Set `runs.raw_output` to the raw stdout
5. Set `runs.completed_at` to the current UTC timestamp
6. Transition task to `failed`
7. Do NOT create an artifact record

**Example failure_reason values:**
- `schema_invalid: .mode: expected 'analyze', got 'analysis'` — wrong mode value
- `schema_invalid: .findings: required field missing` — required array not present
- `schema_invalid: .recommended_next_step: expected 'approve_and_implement'|'request_clarification'|'no_action_needed', got 'proceed'` — invalid enum value
- `schema_invalid: .passed: expected boolean, got string` — wrong type
- `schema_invalid: .files_changed[0].action: expected 'created'|'modified'|'deleted', got 'updated'` — invalid enum in nested object
- `schema_invalid: .passed: false and recommended_next_step is 'mark_done': contradictory values` — semantic validation failure

### Contradictory Field Validation

The worker performs one semantic cross-field check beyond structural schema validation:

| Check | Condition | Failure reason |
|---|---|---|
| Validation contradiction | `passed = false` AND `recommended_next_step = 'mark_done'` | `schema_invalid: .passed: false and recommended_next_step is 'mark_done': contradictory values` |

### Retry After Parse Failure

A task in `failed` due to a parse failure may be retried via `POST /tasks/{id}/runs` with the same mode. The worker re-invokes Kiro CLI with the same context. The previous failed run record is preserved; a new run record is created for the retry.

Parse failures are typically caused by:
- Kiro agent producing prose instead of JSON (fix: update agent system prompt or skill instructions)
- Kiro agent using an outdated schema (fix: update skill to reference current schema version)
- Subprocess environment issue causing error output on stdout (fix: check worker logs for subprocess errors)

---

## Schema Version

All three schemas include `schema_version: "1"`. This field enables non-breaking schema evolution:

- The worker stores `schema_version` on the artifact record (`artifacts.schema_version`) for migration compatibility checks
- When a new schema version is introduced, the worker can handle both old and new versions during a transition period
- Kiro skills must be updated to produce the current schema version when the schema changes
- The worker rejects artifacts with an unrecognized `schema_version` as `schema_invalid`

**Current version:** `"1"` for all three schemas.

---

## Field Summary Tables

### Analysis Schema — All Fields

| Field | Type | Required | Notes |
|---|---|---|---|
| `schema_version` | string | Yes | Always `"1"` |
| `mode` | string | Yes | Always `"analyze"` |
| `headline` | string | Yes | ≤ 200 chars |
| `findings` | string[] | Yes | Non-empty |
| `affected_areas` | string[] | Yes | Non-empty |
| `tradeoffs` | string[] | Yes | May be empty |
| `risks` | string[] | Yes | May be empty |
| `implementation_steps` | string[] | Yes | Non-empty |
| `validation_commands` | string[] | Yes | May be empty |
| `questions` | string[] | Yes | May be empty |
| `recommended_next_step` | string enum | Yes | `approve_and_implement` \| `request_clarification` \| `no_action_needed` |

### Implementation Schema — All Fields

| Field | Type | Required | Notes |
|---|---|---|---|
| `schema_version` | string | Yes | Always `"1"` |
| `mode` | string | Yes | Always `"implement"` |
| `headline` | string | Yes | ≤ 200 chars |
| `files_changed` | FileChange[] | Yes | Non-empty |
| `files_changed[].path` | string | Yes | Relative path |
| `files_changed[].action` | string enum | Yes | `created` \| `modified` \| `deleted` |
| `files_changed[].description` | string | Yes | One sentence |
| `changes_summary` | string | Yes | Prose summary |
| `validation_run` | ValidationRun \| null | Yes | Null if no inline validation |
| `validation_run.commands` | string[] | Yes (if not null) | Commands run |
| `validation_run.passed` | boolean | Yes (if not null) | All commands passed |
| `validation_run.output_excerpt` | string | Yes (if not null) | Last 500 chars |
| `known_issues` | string[] | Yes | May be empty |
| `follow_ups` | string[] | Yes | May be empty |
| `recommended_next_step` | string enum | Yes | `run_validation` \| `request_review` \| `needs_follow_up` |

### Validation Schema — All Fields

| Field | Type | Required | Notes |
|---|---|---|---|
| `schema_version` | string | Yes | Always `"1"` |
| `mode` | string | Yes | Always `"validate"` |
| `commands_run` | string[] | Yes | Non-empty |
| `results` | CommandResult[] | Yes | Non-empty; same length as `commands_run` |
| `results[].command` | string | Yes | Command string |
| `results[].exit_code` | integer | Yes | 0 = success |
| `results[].passed` | boolean | Yes | True if exit_code = 0 |
| `results[].output_excerpt` | string | Yes | Last 500 chars |
| `passed` | boolean | Yes | True if all commands passed |
| `issues_found` | string[] | Yes | Non-empty if `passed = false`; empty if `passed = true` |
| `recommended_next_step` | string enum | Yes | `mark_done` \| `request_revision` \| `retry_validation` |
