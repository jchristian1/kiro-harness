"""
Tests for the Kiro CLI adapter.

Invocation contract under test:
  kiro chat --mode <agent> <prompt>
  cwd = workspace_path

All subprocess calls are mocked — no real Kiro CLI is invoked here.
See docs/integration-test-plan.md for the real-CLI integration test plan.
"""

import asyncio
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from kiro_worker.adapters.kiro_adapter import (
    invoke_kiro,
    build_prompt,
    _extract_json_from_output,
    KiroInvocationResult,
)


# ---------------------------------------------------------------------------
# Fixtures — valid output payloads
# ---------------------------------------------------------------------------

VALID_ANALYSIS = {
    "schema_version": "1",
    "mode": "analyze",
    "headline": "Test",
    "findings": ["f1"],
    "affected_areas": ["src/"],
    "tradeoffs": [],
    "risks": [],
    "implementation_steps": ["step 1"],
    "validation_commands": [],
    "questions": [],
    "recommended_next_step": "approve_and_implement",
}

VALID_IMPLEMENTATION = {
    "schema_version": "1",
    "mode": "implement",
    "headline": "Implemented",
    "files_changed": [{"path": "src/a.py", "action": "modified", "description": "Changed"}],
    "changes_summary": "Done",
    "validation_run": None,
    "known_issues": [],
    "follow_ups": [],
    "recommended_next_step": "run_validation",
}

VALID_VALIDATION = {
    "schema_version": "1",
    "mode": "validate",
    "commands_run": ["pytest"],
    "results": [{"command": "pytest", "exit_code": 0, "passed": True, "output_excerpt": "ok"}],
    "passed": True,
    "issues_found": [],
    "recommended_next_step": "mark_done",
}


def _make_mock_proc(stdout: str, stderr: str = "", returncode: int = 0):
    proc = AsyncMock()
    proc.communicate = AsyncMock(return_value=(stdout.encode(), stderr.encode()))
    proc.returncode = returncode
    proc.kill = MagicMock()
    return proc


# ---------------------------------------------------------------------------
# Invocation contract: command shape and cwd
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_invocation_uses_kiro_chat_subcommand():
    """Adapter must call `kiro chat --mode <agent> <prompt>` — no undocumented flags."""
    proc = _make_mock_proc(json.dumps(VALID_ANALYSIS))
    with patch("asyncio.create_subprocess_exec", return_value=proc) as mock_exec:
        await invoke_kiro("repo-engineer", "/ws", "analysis-workflow", {})

    args = mock_exec.call_args
    cmd = list(args[0])  # positional args to create_subprocess_exec
    # Must be: kiro chat --mode repo-engineer <prompt>
    assert cmd[1] == "chat", f"Expected 'chat' subcommand, got {cmd[1]!r}"
    assert "--mode" in cmd
    mode_idx = cmd.index("--mode")
    assert cmd[mode_idx + 1] == "repo-engineer"
    # Must NOT contain undocumented flags
    for bad_flag in ("--workspace", "--skill", "--context", "--output-format", "--agent"):
        assert bad_flag not in cmd, f"Undocumented flag {bad_flag!r} found in command"


@pytest.mark.asyncio
async def test_invocation_cwd_is_workspace_path():
    """Adapter must set cwd=workspace_path so Kiro loads AGENTS.md and steering from there."""
    proc = _make_mock_proc(json.dumps(VALID_ANALYSIS))
    with patch("asyncio.create_subprocess_exec", return_value=proc) as mock_exec:
        await invoke_kiro("repo-engineer", "/my/workspace", "analysis-workflow", {})

    kwargs = mock_exec.call_args[1]
    assert kwargs.get("cwd") == "/my/workspace", (
        f"Expected cwd='/my/workspace', got {kwargs.get('cwd')!r}"
    )


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------

def test_build_prompt_contains_skill_name():
    prompt = build_prompt("analysis-workflow", {"task_id": "t1"})
    assert "analysis-workflow" in prompt


def test_build_prompt_contains_context_json():
    ctx = {"task_id": "t1", "intent": "add_feature"}
    prompt = build_prompt("analysis-workflow", ctx)
    assert "add_feature" in prompt
    assert "t1" in prompt


def test_build_prompt_contains_mode_in_output_instruction():
    prompt = build_prompt("analysis-workflow", {})
    assert "analyze" in prompt  # mode derived from skill


def test_build_prompt_implementation_workflow():
    prompt = build_prompt("implementation-workflow", {})
    assert "implement" in prompt


def test_build_prompt_validation_workflow():
    prompt = build_prompt("validation-workflow", {})
    assert "validate" in prompt


# ---------------------------------------------------------------------------
# JSON extraction from mixed output
# ---------------------------------------------------------------------------

def test_extract_json_clean():
    out = json.dumps(VALID_ANALYSIS)
    result = _extract_json_from_output(out)
    assert result == VALID_ANALYSIS


def test_extract_json_with_prose_before():
    out = "Analyzing the codebase...\nDone.\n" + json.dumps(VALID_ANALYSIS)
    result = _extract_json_from_output(out)
    assert result == VALID_ANALYSIS


def test_extract_json_with_prose_after():
    out = json.dumps(VALID_ANALYSIS) + "\nAll done."
    result = _extract_json_from_output(out)
    assert result == VALID_ANALYSIS


def test_extract_json_with_prose_both_sides():
    out = "Starting...\n" + json.dumps(VALID_ANALYSIS) + "\nFinished."
    result = _extract_json_from_output(out)
    assert result == VALID_ANALYSIS


def test_extract_json_empty_string():
    assert _extract_json_from_output("") is None


def test_extract_json_no_json():
    assert _extract_json_from_output("I analyzed the codebase and found issues.") is None


def test_extract_json_only_prose():
    assert _extract_json_from_output("No JSON here at all.") is None


# ---------------------------------------------------------------------------
# Successful parse — all three schemas
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_valid_analysis_output():
    proc = _make_mock_proc(json.dumps(VALID_ANALYSIS))
    with patch("asyncio.create_subprocess_exec", return_value=proc):
        result = await invoke_kiro("repo-engineer", "/ws", "analysis-workflow", {})
    assert result.parse_status == "ok"
    assert result.parsed_output == VALID_ANALYSIS
    assert result.failure_reason is None


@pytest.mark.asyncio
async def test_valid_analysis_output_with_surrounding_prose():
    """Adapter must extract JSON even when Kiro emits prose around it."""
    stdout = "Thinking...\n" + json.dumps(VALID_ANALYSIS) + "\nDone."
    proc = _make_mock_proc(stdout)
    with patch("asyncio.create_subprocess_exec", return_value=proc):
        result = await invoke_kiro("repo-engineer", "/ws", "analysis-workflow", {})
    assert result.parse_status == "ok"
    assert result.parsed_output == VALID_ANALYSIS


@pytest.mark.asyncio
async def test_valid_implementation_output():
    proc = _make_mock_proc(json.dumps(VALID_IMPLEMENTATION))
    with patch("asyncio.create_subprocess_exec", return_value=proc):
        result = await invoke_kiro("repo-engineer", "/ws", "implementation-workflow", {})
    assert result.parse_status == "ok"
    assert result.parsed_output == VALID_IMPLEMENTATION


@pytest.mark.asyncio
async def test_valid_validation_output():
    proc = _make_mock_proc(json.dumps(VALID_VALIDATION))
    with patch("asyncio.create_subprocess_exec", return_value=proc):
        result = await invoke_kiro("repo-engineer", "/ws", "validation-workflow", {})
    assert result.parse_status == "ok"
    assert result.parsed_output == VALID_VALIDATION


# ---------------------------------------------------------------------------
# Parse failures
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_parse_failure_prose_output():
    proc = _make_mock_proc("I analyzed the codebase and found some issues.")
    with patch("asyncio.create_subprocess_exec", return_value=proc):
        result = await invoke_kiro("repo-engineer", "/ws", "analysis-workflow", {})
    assert result.parse_status == "parse_failed"
    assert result.parsed_output is None
    assert "parse_failed" in result.failure_reason


@pytest.mark.asyncio
async def test_parse_failure_empty_output():
    proc = _make_mock_proc("")
    with patch("asyncio.create_subprocess_exec", return_value=proc):
        result = await invoke_kiro("repo-engineer", "/ws", "analysis-workflow", {})
    assert result.parse_status == "parse_failed"
    assert "empty output" in result.failure_reason


# ---------------------------------------------------------------------------
# Schema validation failures
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_schema_invalid_wrong_mode():
    bad = {**VALID_ANALYSIS, "mode": "analysis"}  # wrong mode value
    proc = _make_mock_proc(json.dumps(bad))
    with patch("asyncio.create_subprocess_exec", return_value=proc):
        result = await invoke_kiro("repo-engineer", "/ws", "analysis-workflow", {})
    assert result.parse_status == "schema_invalid"
    assert "mode" in result.failure_reason


@pytest.mark.asyncio
async def test_schema_invalid_missing_findings():
    bad = {k: v for k, v in VALID_ANALYSIS.items() if k != "findings"}
    proc = _make_mock_proc(json.dumps(bad))
    with patch("asyncio.create_subprocess_exec", return_value=proc):
        result = await invoke_kiro("repo-engineer", "/ws", "analysis-workflow", {})
    assert result.parse_status == "schema_invalid"
    assert "findings" in result.failure_reason


@pytest.mark.asyncio
async def test_schema_invalid_bad_recommended_next_step():
    bad = {**VALID_ANALYSIS, "recommended_next_step": "proceed"}
    proc = _make_mock_proc(json.dumps(bad))
    with patch("asyncio.create_subprocess_exec", return_value=proc):
        result = await invoke_kiro("repo-engineer", "/ws", "analysis-workflow", {})
    assert result.parse_status == "schema_invalid"
    assert "recommended_next_step" in result.failure_reason


@pytest.mark.asyncio
async def test_schema_invalid_contradictory_fields():
    bad = {**VALID_VALIDATION, "passed": False, "recommended_next_step": "mark_done"}
    proc = _make_mock_proc(json.dumps(bad))
    with patch("asyncio.create_subprocess_exec", return_value=proc):
        result = await invoke_kiro("repo-engineer", "/ws", "validation-workflow", {})
    assert result.parse_status == "schema_invalid"
    assert "contradictory" in result.failure_reason


# ---------------------------------------------------------------------------
# Subprocess error handling
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_timeout_handling():
    async def slow_communicate():
        await asyncio.sleep(999)
        return b"", b""

    proc = AsyncMock()
    proc.communicate = slow_communicate
    proc.kill = MagicMock()
    proc.returncode = None

    with patch("asyncio.create_subprocess_exec", return_value=proc):
        result = await invoke_kiro("repo-engineer", "/ws", "analysis-workflow", {}, timeout=1)
    assert result.exit_code == -1
    assert "timeout" in result.failure_reason
    assert result.parsed_output is None


@pytest.mark.asyncio
async def test_nonzero_exit_code():
    proc = _make_mock_proc("", stderr="Command not found", returncode=127)
    with patch("asyncio.create_subprocess_exec", return_value=proc):
        result = await invoke_kiro("repo-engineer", "/ws", "analysis-workflow", {})
    assert result.exit_code == 127
    assert "exit_code:127" in result.failure_reason
    assert result.parsed_output is None
