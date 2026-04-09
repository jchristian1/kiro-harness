---
name: henry_approve_implement
description: Approve a task in awaiting_approval state and trigger the implementation run.
user-invocable: true
command-dispatch: tool
command-tool: henry_approve_implement
command-arg-mode: raw
---

Dispatches directly to the henry_approve_implement tool.

Input: JSON object with task_id.

Example:
/henry_approve_implement {"task_id": "task_01..."}
