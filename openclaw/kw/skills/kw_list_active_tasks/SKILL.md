---
name: kw_list_active_tasks
description: List all currently active tasks across all projects. Shows what Kiro is doing right now — task status, run status, progress, and elapsed time. Read-only.
user-invocable: true
disable-model-invocation: true
command-dispatch: tool
command-tool: kw_list_active_tasks
command-arg-mode: raw
---

Dispatches to kw_list_active_tasks. Returns all tasks in active states (opening, analyzing, implementing, validating).

Input: {} (no parameters required)

Returns: list of active tasks with project name, status, run mode, progress, and elapsed time.
