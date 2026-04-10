---
name: kw_approve_implement
description: Approve a task and start the implementation run. Returns immediately with task_id, run_id, and status=implementing. Use kw_task_status to poll progress.
user-invocable: true
disable-model-invocation: true
command-dispatch: tool
command-tool: kw_approve_implement
command-arg-mode: raw
---

Dispatches to kw_approve_implement. Returns immediately — does not wait for Kiro to finish.

Input: {"task_id": "task_01..."}

Returns: task_id, run_id, status=implementing. Poll with /kw_task_status to get progress and final result.
