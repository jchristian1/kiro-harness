---
name: henry_task_status
description: Get the current status of a task and the headline from its latest artifact.
user-invocable: true
command-dispatch: tool
command-tool: henry_task_status
command-arg-mode: raw
---

Dispatches directly to the henry_task_status tool.

Input: JSON object with task_id.

Example:
/henry_task_status {"task_id": "task_01..."}
