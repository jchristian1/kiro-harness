"""
Kiro CLI adapter — documented interface only.

Invocation model (kiro-cli chat, documented in `kiro-cli chat --help`):

    kiro-cli chat --agent <agent> --no-interactive <prompt>

Run with cwd=workspace_path so kiro-cli loads the workspace context automatically.

Flags used:
  --agent <agent>    Selects the agent/context profile.
  --no-interactive   Runs headlessly without waiting for user input.

Output contract:
  kiro-cli must respond with a JSON block in stdout.
  The worker extracts the first valid top-level JSON object from stdout,
  validates it against the schema for the run mode, and stores it as an artifact.
  If no valid JSON is found, the run is marked parse_failed.
"""

import asyncio
import json
import logging
import re
from dataclasses import dataclass
from typing import Callable, Awaitable

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
    Build the prompt text passed to `kiro-cli chat`.

    The prompt carries all task-specific context and the exact output schema
    that kiro-cli must conform to.
    """
    mode = _SKILL_TO_MODE.get(skill, skill)
    context_json = json.dumps(context, indent=2)

    if mode == "analyze":
        schema_instruction = (
            "You MUST respond with ONLY a single JSON object — no prose, no markdown, no explanation before or after it.\n\n"
            "The JSON object MUST have exactly these fields:\n"
            "{\n"
            '  "schema_version": "1",\n'
            '  "mode": "analyze",\n'
            '  "headline": "<one sentence summary, max 200 chars>",\n'
            '  "findings": ["<finding 1>", "<finding 2>"],\n'
            '  "affected_areas": ["<file or module path>"],\n'
            '  "tradeoffs": [],\n'
            '  "risks": [],\n'
            '  "implementation_steps": ["<step 1>", "<step 2>"],\n'
            '  "validation_commands": [],\n'
            '  "questions": [],\n'
            '  "recommended_next_step": "approve_and_implement"\n'
            "}\n\n"
            'recommended_next_step must be one of: "approve_and_implement", "request_clarification", "no_action_needed"\n'
            "findings and implementation_steps must be non-empty arrays.\n"
        )
    elif mode == "implement":
        schema_instruction = (
            "You are implementing the changes described in the task context above.\n\n"
            "Step 1: Use your tools to make the required code changes (read files, write files, run commands as needed).\n"
            "Step 2: After completing all changes, output a single JSON object summarizing what you did.\n\n"
            "The final JSON object MUST have exactly these fields:\n"
            "{\n"
            '  "schema_version": "1",\n'
            '  "mode": "implement",\n'
            '  "headline": "<one sentence summary of what was implemented>",\n'
            '  "files_changed": [{"path": "<relative path>", "action": "created|modified|deleted", "description": "<what changed>"}],\n'
            '  "changes_summary": "<prose summary of all changes made>",\n'
            '  "validation_run": null,\n'
            '  "known_issues": [],\n'
            '  "follow_ups": [],\n'
            '  "recommended_next_step": "run_validation"\n'
            "}\n\n"
            'recommended_next_step must be one of: "run_validation", "request_review", "needs_follow_up"\n'
            "files_changed must be a non-empty array listing every file you created, modified, or deleted.\n"
            "Output the JSON object as your LAST message after completing all tool calls.\n"
        )
    elif mode == "validate":
        schema_instruction = (
            "You MUST respond with ONLY a single JSON object — no prose, no markdown, no explanation before or after it.\n\n"
            "The JSON object MUST have exactly these fields:\n"
            "{\n"
            '  "schema_version": "1",\n'
            '  "mode": "validate",\n'
            '  "commands_run": ["<command>"],\n'
            '  "results": [{"command": "<cmd>", "exit_code": 0, "passed": true, "output_excerpt": "<last 500 chars>"}],\n'
            '  "passed": true,\n'
            '  "issues_found": [],\n'
            '  "recommended_next_step": "mark_done"\n'
            "}\n\n"
            'recommended_next_step must be one of: "mark_done", "request_revision", "retry_validation"\n'
            "commands_run and results must be non-empty arrays.\n"
        )
    else:
        schema_instruction = (
            f"Respond with a single JSON object with schema_version='1' and mode='{mode}'.\n"
        )

    return (
        f"Task context:\n{context_json}\n\n"
        f"{schema_instruction}"
    )


# ---------------------------------------------------------------------------
# JSON extraction
# ---------------------------------------------------------------------------

def _strip_ansi(text: str) -> str:
    """Remove ANSI escape sequences from text."""
    ansi_escape = re.compile(r'\x1b(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    return ansi_escape.sub("", text)


def _extract_json_from_output(stdout: str) -> dict | None:
    """
    Extract the kiro output contract JSON object from stdout.

    Kiro emits the JSON as its last message, preceded by tool call logs and
    code diffs that may contain many { } characters. Strategy:
    1. Strip ANSI escape codes
    2. Find the last occurrence of '"schema_version"' — that's inside the real JSON
    3. Scan backward from there to find the opening {
    4. Scan forward from there to find the matching closing }
    Returns the parsed dict, or None if no valid JSON object is found.
    """
    stdout = _strip_ansi(stdout).strip()
    if not stdout:
        return None

    # Find the last occurrence of the schema_version key — unique to our contract JSON
    marker = '"schema_version"'
    marker_pos = stdout.rfind(marker)
    if marker_pos == -1:
        return None

    # Scan backward from marker to find the opening {
    start = stdout.rfind("{", 0, marker_pos)
    if start == -1:
        return None

    # Scan forward from start to find the matching closing }
    # Use a brace counter to handle nested objects
    depth = 0
    end = -1
    for i in range(start, len(stdout)):
        if stdout[i] == "{":
            depth += 1
        elif stdout[i] == "}":
            depth -= 1
            if depth == 0:
                end = i
                break

    if end == -1:
        return None

    candidate = stdout[start:end + 1]
    try:
        parsed = json.loads(candidate)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    return None


# ---------------------------------------------------------------------------
# Main invocation
# ---------------------------------------------------------------------------

def _extract_progress_message(line: str) -> str | None:
    """
    Extract a human-readable progress message from a kiro-cli stdout line.
    Returns None if the line is not meaningful for progress reporting.
    """
    line = line.strip()
    if not line or line.startswith("{"):
        return None
    # Strip ANSI escape codes
    ansi_escape = re.compile(r'\x1b\[[0-9;]*[mGKHF]|\x1b\[\?[0-9]+[lh]|\x1b\[[\d;]*[A-Za-z]')
    clean = ansi_escape.sub("", line).strip()
    if not clean or len(clean) < 3:
        return None
    # Skip pure tool-call metadata lines
    if clean.startswith("↱") or clean.startswith("⋮") or clean.startswith("-"):
        return None
    # Meaningful patterns
    if any(kw in clean.lower() for kw in (
        "reading", "writing", "creating", "modifying", "deleting",
        "running", "executing", "scanning", "analyzing", "generating",
        "applying", "checking", "installing", "cloning", "fetching",
        "✓", "✗", "batch", "operation", "completed", "failed",
    )):
        return clean[:200]
    # Lines starting with > are kiro-cli agent messages
    if clean.startswith(">"):
        msg = clean[1:].strip()
        if msg and len(msg) > 5:
            return msg[:200]
    return None


async def invoke_kiro(
    agent: str,
    workspace_path: str,
    skill: str,
    context: dict,
    timeout: int = 300,
    on_progress: Callable[[str, str], Awaitable[None]] | None = None,
) -> KiroInvocationResult:
    """
    Invoke kiro-cli using the documented `kiro-cli chat` interface.

    Command: kiro-cli chat --no-interactive --trust-all-tools <prompt>
    CWD:     workspace_path

    --no-interactive runs headlessly without waiting for user input.
    --trust-all-tools auto-approves tool use (required with --no-interactive).

    on_progress: optional async callback(message, partial_output) called as stdout
    lines arrive. Used to write progress updates to the DB during long runs.
    """
    prompt = build_prompt(skill, context)
    # Implement runs need more time — they do real work before producing output
    effective_timeout = timeout * 2 if skill == "implementation-workflow" else timeout
    cmd = [
        settings.KIRO_CLI_PATH,
        "chat",
        "--no-interactive",
        "--trust-all-tools",
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

        stdout_chunks: list[str] = []
        stderr_chunks: list[str] = []

        async def read_stdout():
            assert proc.stdout is not None
            while True:
                line_bytes = await proc.stdout.readline()
                if not line_bytes:
                    break
                line = line_bytes.decode("utf-8", errors="replace")
                stdout_chunks.append(line)
                if on_progress:
                    msg = _extract_progress_message(line)
                    if msg:
                        partial = "".join(stdout_chunks)[-2000:]
                        try:
                            await on_progress(msg, partial)
                        except Exception:
                            pass  # progress updates are best-effort

        async def read_stderr():
            assert proc.stderr is not None
            data = await proc.stderr.read()
            stderr_chunks.append(data.decode("utf-8", errors="replace"))

        try:
            await asyncio.wait_for(
                asyncio.gather(read_stdout(), read_stderr(), proc.wait()),
                timeout=effective_timeout,
            )
        except asyncio.TimeoutError:
            proc.kill()
            return KiroInvocationResult(
                exit_code=-1,
                stdout="".join(stdout_chunks),
                stderr="".join(stderr_chunks),
                parsed_output=None,
                parse_status="parse_failed",
                failure_reason=f"timeout:{effective_timeout}s: process did not complete",
            )

        stdout = "".join(stdout_chunks)
        stderr = "".join(stderr_chunks)
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
