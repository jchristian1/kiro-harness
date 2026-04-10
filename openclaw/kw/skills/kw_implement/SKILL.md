---
name: kw_implement
description: Start a Kiro implementation run from a completed analysis task. Returns immediately with task_id, run_id, and status=implementing. Use kw_task_status to poll progress and get the full structured result.
user-invocable: true
disable-model-invocation: true
command-dispatch: tool
command-tool: kw_implement
command-arg-mode: raw
---

Dispatches to kw_implement. Returns immediately — does not wait for Kiro to finish.

Input: {"task_id": "task_01...", "description": "what to implement", "step_index": 0}

Returns: task_id, run_id, status=implementing. Poll with /kw_task_status to get progress and final result.
