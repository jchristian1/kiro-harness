---
name: henry_implement
description: Create a new implementation task on an existing project and run it immediately. Use after a completed analysis task when the user approves implementation.
user-invocable: true
disable-model-invocation: true
command-dispatch: tool
command-tool: henry_implement
command-arg-mode: raw
---

Dispatches directly to the henry_implement tool.

Input: JSON object with task_id (from the completed analysis task) and description.

Example:
/henry_implement {"task_id": "task_01...", "description": "Implement the JWT authentication as described in the analysis findings."}
