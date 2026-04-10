---
name: kw_complete_task
description: Close a task and mark it as done. Use when the task is in validating or awaiting_revision and the Project Manager decides no further action is needed — for example when validation is optional or intentionally skipped.
user-invocable: true
disable-model-invocation: true
command-dispatch: tool
command-tool: kw_complete_task
command-arg-mode: raw
---

Dispatches to kw_complete_task. Closes the task and marks it as done.

Input: {"task_id": "task_01..."}

Returns: task_id, new status=done.
