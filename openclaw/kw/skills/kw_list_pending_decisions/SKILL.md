---
name: kw_list_pending_decisions
description: List all tasks that need Project Manager attention or a decision. Shows what is waiting, why it needs attention, and what the next action should be. Read-only.
user-invocable: true
disable-model-invocation: true
command-dispatch: tool
command-tool: kw_list_pending_decisions
command-arg-mode: raw
---

Dispatches to kw_list_pending_decisions. Returns tasks in awaiting_revision or awaiting_approval states, sorted oldest-first.

Input: {} (no parameters required)

Returns: list of tasks needing PM attention with reason and suggested next action.
