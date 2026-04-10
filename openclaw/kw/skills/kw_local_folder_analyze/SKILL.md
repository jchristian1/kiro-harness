---
name: kw_local_folder_analyze
description: Start a Kiro analysis on a local folder. Returns immediately with task_id, run_id, and status=analyzing. Use kw_task_status to poll progress and get the full structured result.
user-invocable: true
disable-model-invocation: true
command-dispatch: tool
command-tool: kw_local_folder_analyze
command-arg-mode: raw
---

Dispatches to kw_local_folder_analyze. Returns immediately — does not wait for Kiro to finish.

Input: {"name": "project-name", "path": "/absolute/path", "description": "what to analyze"}

Returns: task_id, run_id, status=analyzing. Poll with /kw_task_status to get progress and final result.
