---
name: kw_cancel_task
description: Stop an active specialist run. Use when a task is stuck, wrong, or no longer wanted. Kills the active kiro-cli process, marks the run as cancelled, and transitions the task to awaiting_revision.
user-invocable: true
disable-model-invocation: true
command-dispatch: tool
command-tool: kw_cancel_task
command-arg-mode: raw
---

Dispatches to kw_cancel_task. Stops the active run and marks the task as awaiting_revision.

Input: {"task_id": "task_01...", "reason": "optional reason"}

Returns: task_id, run_id, previous and new status for both task and run.

After cancellation, use /kw_complete_task to close the task, or /kw_implement to retry.
