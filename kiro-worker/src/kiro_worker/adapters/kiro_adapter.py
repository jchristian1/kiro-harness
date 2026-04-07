"""
Kiro CLI adapter — documented interface only.

Invocation model (kiro chat, documented in `kiro chat --help`):

    kiro chat --mode <agent> <prompt>

Run with cwd=workspace_path so Kiro loads the workspace context automatically:
  - AGENTS.md at the workspace root is always included by Kiro (no flag needed)
  - .kiro/steering/**/*.md is loaded if declared in the agent's resources config
  - .kiro/agents/<agent>.json defines tool permissions, model, and resources

The prompt is the sole mechanism for passing task-specific context (intent,
description, prior analysis, approved plan, revision instructions). It is
constructed by the worker and passed as a positional argument to `kiro chat`.

Flags used:
  --mode <agent>   Selects the custom agent (or built-in mode). Documented.

Flags NOT used (undocumented, do not add):
  --agent, --workspace, --skill, --context, --output-format

Output contract:
  Kiro must respond with a JSON block as the last JSON object in stdout.
  The worker extracts the first valid top-level JSON object from stdout,
  validates it against the schema for the run mode, and stores it as an artifact.
  If no valid JSON is found, the run is marked parse_failed.
"""

import asyncio
import json
import logging
import re
from dataclasses import dataclass

from kiro_worker.config import settings

logger = logging.getLogger(__name__)

ANALYSIS_NEXT_STEPS = {"approve_and_implement", "request_clarification", "no_action_needed"}
IMPLEMENTATION_NEXT_STEPS = {"run_validation", "request_review", "needs_follow_up"}
VALIDATION_NEXT_STEPS = {"mark_done", "request_revision", "retry_validation"}
FILE_CHANGE_ACTIONS = {"created", "modified", "deleted"}

# Skill name → run mode (used for schema validation selection)
_SKILL_TO_MODE = {
    "analysis-workflow": "analyze",
    "implementation-workflow": "implement",
    "validation-workflow": "validate",
}


@dataclass
class KiroInvocationResult:
    exit_code: int
    stdout: str
    stderr: str
    parsed_output: dict | None
    parse_status: str  # "ok", "parse_failed", "schema_invalid"
    failure_reason: str | None


# ---------------------------------------------------------------------------
# Schema validators
# ---------------------------------------------------------------------------

def _validate_analysis(data: dict) -> str | None:
    """Return failure_reason string if invalid, else None."""
    if data.get("schema_version") != "1":
        return "schema_invalid: .schema_version: expected '1'"
    if data.get("mode") != "analyze":
        return f"schema_invalid: .mode: expected 'analyze', got '{data.get('mode')}'"
    for field_name in ("findings", "affected_areas", "implementation_steps"):
        val = data.get(field_name)
        if not isinstance(val, list) or len(val) == 0:
            return f"schema_invalid: .{field_name}: required non-empty array missing"
    rns = data.get("recommended_next_step")
    if rns not in ANALYSIS_NEXT_STEPS:
        return f"schema_invalid: .recommended_next_step: expected {ANALYSIS_NEXT_STEPS}, got '{rns}'"
    return None


def _validate_implementation(data: dict) -> str | None:
    if data.get("schema_version") != "1":
        return "schema_invalid: .schema_version: expected '1'"
    if data.get("mode") != "implement":
        return f"schema_invalid: .mode: expected 'implement', got '{data.get('mode')}'"
    files_changed = data.get("files_changed")
    if not isinstance(files_changed, list) or len(files_changed) == 0:
        return "schema_invalid: .files_changed: required non-empty array missing"
    for i, fc in enumerate(files_changed):
        if not isinstance(fc, dict):
            return f"schema_invalid: .files_changed[{i}]: expected object"
        for req in ("path", "action", "description"):
            if req not in fc:
                return f"schema_invalid: .files_changed[{i}].{req}: required field missing"
        if fc.get("action") not in FILE_CHANGE_ACTIONS:
            return f"schema_invalid: .files_changed[{i}].action: expected {FILE_CHANGE_ACTIONS}, got '{fc.get('action')}'"
    rns = data.get("recommended_next_step")
    if rns not in IMPLEMENTATION_NEXT_STEPS:
        return f"schema_invalid: .recommended_next_step: expected {IMPLEMENTATION_NEXT_STEPS}, got '{rns}'"
    return None


def _validate_validation(data: dict) -> str | None:
    if data.get("schema_version") != "1":
        return "schema_invalid: .schema_version: expected '1'"
    if data.get("mode") != "validate":
        return f"schema_invalid: .mode: expected 'validate', got '{data.get('mode')}'"
    for field_name in ("commands_run", "results"):
        val = data.get(field_name)
        if not isinstance(val, list) or len(val) == 0:
            return f"schema_invalid: .{field_name}: required non-empty array missing"
    if not isinstance(data.get("passed"), bool):
        return "schema_invalid: .passed: expected boolean"
    rns = data.get("recommended_next_step")
    if rns not in VALIDATION_NEXT_STEPS:
        return f"schema_invalid: .recommended_next_step: expected {VALIDATION_NEXT_STEPS}, got '{rns}'"
    if data.get("passed") is False and rns == "mark_done":
        return "schema_invalid: .passed: false and recommended_next_step is 'mark_done': contradictory values"
    return None


_VALIDATORS = {
    "analyze": _validate_analysis,
    "implement": _validate_implementation,
    "validate": _validate_validation,
}


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------

def build_prompt(skill: str, context: dict) -> str:
    """
    Build the prompt text passed to `kiro chat`.

    The prompt carries all task-specific context that Kiro needs for this
    invocation. Persistent context (engineering standards, project overview)
    is supplied by AGENTS.md and .kiro/steering/ in the workspace — not here.

    The prompt instructs Kiro to respond with a single JSON object conforming
    to the output contract for the given skill.
    """
    mode = _SKILL_TO_MODE.get(skill, skill)
    context_json = json.dumps(context, indent=2)

    return (
        f"You are running the {skill} workflow.\n\n"
        f"Task context:\n{context_json}\n\n"
        f"Respond with a single JSON object conforming to the {mode} output schema "
        f"(schema_version=\\\"1\\\", mode=\\\"{mode}\\\"). "
        f"Output only the JSON object — no prose before or after it."
    )


# ---------------------------------------------------------------------------
# JSON extraction
# ---------------------------------------------------------------------------

def _extract_json_from_output(stdout: str) -> dict | None:
    """
    Extract the first top-level JSON object from stdout.

    Kiro may emit log lines or prose before/after the JSON block.
    We scan for the first '{' and attempt to parse from there.
    Returns the parsed dict, or None if no valid JSON object is found.
    """
    stdout = stdout.strip()
    if not stdout:
        return None

    # Find the first '{' and try to parse a JSON object from that position
    start = stdout.find("{")
    if start == -1:
        return None

    # Try progressively shorter substrings from the last '}' backwards
    end = stdout.rfind("}")
    while end >= start:
        candidate = stdout[start:end + 1]
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            end = stdout.rfind("}", start, end)

    return None


# ---------------------------------------------------------------------------
# Main invocation
# ---------------------------------------------------------------------------

async def invoke_kiro(
    agent: str,
    workspace_path: str,
    skill: str,
    context: dict,
    timeout: int = 300,
) -> KiroInvocationResult:
    """
    Invoke Kiro CLI using the documented `kiro chat` interface.

    Command: kiro chat --mode <agent> <prompt>
    CWD:     workspace_path  (Kiro loads AGENTS.md and steering from here)

    The agent name is passed as --mode, which selects the custom agent defined
    in <workspace>/.kiro/agents/<agent>.json. That agent config declares:
      - tool permissions
      - model selection
      - resources (including "file://.kiro/steering/**/*.md" for steering)

    AGENTS.md at the workspace root is always loaded by Kiro automatically.
    Steering files are loaded only if declared in the agent's resources config.
    Neither requires a CLI flag.
    """
    prompt = build_prompt(skill, context)
    cmd = [
        settings.KIRO_CLI_PATH,
        "chat",
        "--mode", agent,
        prompt,
    ]

    logger.info(
        "Invoking Kiro CLI",
        extra={"agent": agent, "skill": skill, "workspace": workspace_path},
    )

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=workspace_path,
        )
        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(), timeout=timeout
            )
        except asyncio.TimeoutError:
            proc.kill()
            return KiroInvocationResult(
                exit_code=-1,
                stdout="",
                stderr="",
                parsed_output=None,
                parse_status="parse_failed",
                failure_reason=f"timeout:{timeout}s: process did not complete",
            )

        stdout = stdout_bytes.decode("utf-8", errors="replace")
        stderr = stderr_bytes.decode("utf-8", errors="replace")
        exit_code = proc.returncode if proc.returncode is not None else 0

        if exit_code != 0:
            stderr_excerpt = stderr[:500].strip()
            return KiroInvocationResult(
                exit_code=exit_code,
                stdout=stdout,
                stderr=stderr,
                parsed_output=None,
                parse_status="parse_failed",
                failure_reason=f"exit_code:{exit_code}: {stderr_excerpt}",
            )

        if not stdout.strip():
            return KiroInvocationResult(
                exit_code=exit_code,
                stdout=stdout,
                stderr=stderr,
                parsed_output=None,
                parse_status="parse_failed",
                failure_reason="parse_failed: empty output",
            )

        parsed = _extract_json_from_output(stdout)
        if parsed is None:
            return KiroInvocationResult(
                exit_code=exit_code,
                stdout=stdout,
                stderr=stderr,
                parsed_output=None,
                parse_status="parse_failed",
                failure_reason="parse_failed: no JSON object found in output",
            )

        # Schema validation
        mode = _SKILL_TO_MODE.get(skill, skill)
        validator = _VALIDATORS.get(mode)
        if validator:
            error = validator(parsed)
            if error:
                return KiroInvocationResult(
                    exit_code=exit_code,
                    stdout=stdout,
                    stderr=stderr,
                    parsed_output=None,
                    parse_status="schema_invalid",
                    failure_reason=error,
                )

        return KiroInvocationResult(
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
            parsed_output=parsed,
            parse_status="ok",
            failure_reason=None,
        )

    except Exception as e:
        return KiroInvocationResult(
            exit_code=-1,
            stdout="",
            stderr="",
            parsed_output=None,
            parse_status="parse_failed",
            failure_reason=f"exit_code:-1: {e}",
        )
