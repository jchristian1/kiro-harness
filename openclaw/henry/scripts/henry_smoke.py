#!/usr/bin/env python3
"""
henry_smoke.py — Thin bridge between OpenClaw Henry skills and kiro-worker.

Usage:
    python henry_smoke.py <operation> '<json_input>'

Operations:
    new_project_analyze   Create project + workspace + task, trigger analyze run
    github_analyze        Same flow for a GitHub repo source
    local_folder_analyze  Same flow for a local folder source
    approve_implement     Approve a task and trigger implement run
    task_status           Get current status of a task + latest artifact headline

The bridge is intentionally thin. It calls the worker HTTP API and returns
normalized JSON. No business logic lives here — the worker is the source of truth.

Worker base URL is read from KIRO_WORKER_URL env var (default: http://localhost:4000).
"""

import json
import sys
import os
import urllib.request
import urllib.error

WORKER_URL = os.environ.get("KIRO_WORKER_URL", "http://localhost:4000")


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def _request(method: str, path: str, body: dict | None = None) -> dict:
    url = f"{WORKER_URL}{path}"
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body_bytes = e.read()
        try:
            err = json.loads(body_bytes)
        except Exception:
            err = {"raw": body_bytes.decode(errors="replace")}
        return {"_http_error": e.code, **err}


def _post(path: str, body: dict) -> dict:
    return _request("POST", path, body)


def _get(path: str) -> dict:
    return _request("GET", path)


# ---------------------------------------------------------------------------
# Operations
# ---------------------------------------------------------------------------

def _analyze_flow(name: str, source: str, source_url: str, description: str) -> dict:
    """
    Internal helper: create project + workspace + task, trigger analyze run.
    source must be one of: new_project, github_repo, local_repo, local_folder.
    """
    # 1. Create project
    proj = _post("/projects", {"name": name, "source": source, "source_url": source_url})
    if "_http_error" in proj:
        err = proj.get("error", {})
        return {"ok": False, "step": "create_project", "failure_reason": err.get("message", "create project failed"), "error_code": err.get("code")}
    project_id = proj["id"]

    # 2. Open workspace
    ws = _post(f"/projects/{project_id}/workspaces", {})
    if "_http_error" in ws:
        err = ws.get("error", {})
        return {"ok": False, "step": "open_workspace", "failure_reason": err.get("message", "open workspace failed"), "error_code": err.get("code")}

    # 3. Create task
    task = _post("/tasks", {
        "project_id": project_id,
        "intent": "analyze_codebase",
        "source": source,
        "operation": "analyze_then_approve",
        "description": description,
    })
    if "_http_error" in task:
        err = task.get("error", {})
        return {"ok": False, "step": "create_task", "failure_reason": err.get("message", "create task failed"), "error_code": err.get("code")}
    task_id = task["id"]

    # 4. Trigger analyze run (blocks until complete)
    run = _post(f"/tasks/{task_id}/runs", {"mode": "analyze"})
    if "_http_error" in run:
        err = run.get("error", {})
        return {"ok": False, "step": "trigger_run", "failure_reason": err.get("message", "trigger run failed"), "error_code": err.get("code")}

    return _format_run_result(project_id, task_id, run)


def new_project_analyze(inp: dict) -> dict:
    """
    Input:
        name        str   project name (must be unique)
        source_url  str   path where the new workspace will be created (must be under WORKSPACE_SAFE_ROOT)
        description str   task description
    Source is always new_project. For existing folders use local_folder_analyze;
    for GitHub repos use github_analyze.
    """
    return _analyze_flow(inp["name"], "new_project", inp["source_url"], inp["description"])


def github_analyze(inp: dict) -> dict:
    """
    Input:
        name        str   project name
        repo_url    str   GitHub repo HTTPS URL
        description str   task description
    """
    return _analyze_flow(inp["name"], "github_repo", inp["repo_url"], inp["description"])


def local_folder_analyze(inp: dict) -> dict:
    """
    Input:
        name        str   project name
        path        str   absolute local folder path
        description str   task description
    """
    return _analyze_flow(inp["name"], "local_folder", inp["path"], inp["description"])


def approve_implement(inp: dict) -> dict:
    """
    Input:
        task_id  str   task to approve and implement
    """
    task_id = inp["task_id"]

    # 1. Approve
    approved = _post(f"/tasks/{task_id}/approve", {})
    if "_http_error" in approved:
        # Normalize: extract worker error code/message into stable top-level fields
        err = approved.get("error", {})
        return {
            "ok": False,
            "task_id": task_id,
            "step": "approve",
            "failure_reason": err.get("message", approved.get("raw", "approve failed")),
            "error_code": err.get("code"),
        }

    # 2. Trigger implement run (blocks until complete)
    run = _post(f"/tasks/{task_id}/runs", {"mode": "implement"})
    if "_http_error" in run:
        err = run.get("error", {})
        return {
            "ok": False,
            "task_id": task_id,
            "step": "trigger_run",
            "failure_reason": err.get("message", run.get("raw", "trigger run failed")),
            "error_code": err.get("code"),
        }

    return _format_run_result(None, task_id, run)


def task_status(inp: dict) -> dict:
    """
    Input:
        task_id  str   task to check
    """
    task_id = inp["task_id"]
    task = _get(f"/tasks/{task_id}")
    if "_http_error" in task:
        err = task.get("error", {})
        return {"ok": False, "task_id": task_id, "step": "get_task", "failure_reason": err.get("message", "get task failed"), "error_code": err.get("code")}

    result = {
        "ok": True,
        "task_id": task_id,
        "status": task["status"],
        "last_run": task.get("last_run"),
        "artifact_headline": None,
    }

    # Fetch artifact headline if last run completed
    last_run = task.get("last_run")
    if last_run and last_run.get("status") == "completed":
        run_id = last_run["id"]
        artifact = _get(f"/runs/{run_id}/artifact")
        if "_http_error" not in artifact:
            result["artifact_headline"] = artifact.get("content", {}).get("headline")

    return result


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------

def _format_run_result(project_id: str | None, task_id: str, run: dict) -> dict:
    result = {
        "ok": run.get("status") == "completed",
        "task_id": task_id,
        "run_id": run.get("id"),
        "run_status": run.get("status"),
        "artifact_headline": None,
        "findings_count": None,
        "recommended_next_step": None,
    }
    if project_id:
        result["project_id"] = project_id

    if run.get("status") == "completed":
        run_id = run["id"]
        artifact = _get(f"/runs/{run_id}/artifact")
        if "_http_error" not in artifact:
            content = artifact.get("content", {})
            result["artifact_headline"] = content.get("headline")
            result["findings_count"] = len(content.get("findings", []))
            result["recommended_next_step"] = content.get("recommended_next_step")
    else:
        result["failure_reason"] = run.get("failure_reason")

    return result


def _format_summary(result: dict) -> str:
    """
    Produce a human-readable summary with all chaining IDs explicitly shown.
    Printed after the JSON block so Telegram replies expose the IDs.
    """
    lines = []
    ok = result.get("ok")
    status_icon = "✓" if ok else "✗"

    # Analyze / implement results
    if "run_status" in result:
        lines.append(f"{status_icon} run_status: {result.get('run_status')}")
        if result.get("artifact_headline"):
            lines.append(f"  headline: {result['artifact_headline']}")
        if result.get("recommended_next_step"):
            lines.append(f"  next_step: {result['recommended_next_step']}")
        if result.get("findings_count") is not None:
            lines.append(f"  findings: {result['findings_count']}")
        lines.append("")
        lines.append("IDs for follow-up commands:")
        if result.get("project_id"):
            lines.append(f"  project_id : {result['project_id']}")
        if result.get("task_id"):
            lines.append(f"  task_id    : {result['task_id']}")
        if result.get("run_id"):
            lines.append(f"  run_id     : {result['run_id']}")

    # task_status results
    elif "status" in result and "task_id" in result:
        lines.append(f"{status_icon} task status: {result.get('status')}")
        if result.get("artifact_headline"):
            lines.append(f"  headline: {result['artifact_headline']}")
        last_run = result.get("last_run") or {}
        lines.append("")
        lines.append("IDs for follow-up commands:")
        lines.append(f"  task_id    : {result['task_id']}")
        if last_run.get("id"):
            lines.append(f"  run_id     : {last_run['id']}")
        if last_run.get("mode"):
            lines.append(f"  run_mode   : {last_run['mode']}")
        if last_run.get("status"):
            lines.append(f"  run_status : {last_run['status']}")

    # Error results
    elif not ok:
        lines.append(f"✗ failed at step: {result.get('step', 'unknown')}")
        if result.get("failure_reason"):
            lines.append(f"  reason: {result['failure_reason']}")
        if result.get("error_code"):
            lines.append(f"  code: {result['error_code']}")
        if result.get("task_id"):
            lines.append(f"  task_id: {result['task_id']}")

    return "\n".join(lines)

OPERATIONS = {
    "new_project_analyze": new_project_analyze,
    "github_analyze": github_analyze,
    "local_folder_analyze": local_folder_analyze,
    "approve_implement": approve_implement,
    "task_status": task_status,
}


def main():
    if len(sys.argv) < 3:
        print(json.dumps({
            "ok": False,
            "error": "Usage: henry_smoke.py <operation> '<json_input>'",
            "operations": list(OPERATIONS.keys()),
        }))
        sys.exit(1)

    operation = sys.argv[1]
    if operation not in OPERATIONS:
        print(json.dumps({
            "ok": False,
            "error": f"Unknown operation: {operation}",
            "operations": list(OPERATIONS.keys()),
        }))
        sys.exit(1)

    try:
        inp = json.loads(sys.argv[2])
    except json.JSONDecodeError as e:
        print(json.dumps({"ok": False, "error": f"Invalid JSON input: {e}"}))
        sys.exit(1)

    result = OPERATIONS[operation](inp)
    print(json.dumps(result, indent=2))
    summary = _format_summary(result)
    if summary:
        print()
        print(summary)
    sys.exit(0 if result.get("ok") else 1)


if __name__ == "__main__":
    main()
