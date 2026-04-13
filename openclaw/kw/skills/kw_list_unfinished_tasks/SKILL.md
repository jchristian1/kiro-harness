---
name: kw_list_unfinished_tasks
description: List all tasks that were started but not completed and are not currently active. Shows failed, awaiting_revision, awaiting_approval, and stuck/orphaned opening tasks with resumability and recommended next action.
user-invocable: true
disable-model-invocation: true
command-dispatch: tool
command-tool: kw_list_unfinished_tasks
command-arg-mode: raw
---

# kw_list_unfinished_tasks

List all tasks that were started but not completed and are not currently active.

This skill surfaces tasks in states: `failed`, `awaiting_revision`, `awaiting_approval`, and `opening` (stuck/orphaned). It is the primary continuity tool — use it after a restart or context switch to see what needs attention.

Each result includes:
- task and run status
- how long the task has been unfinished
- the last artifact headline (if any)
- a resumability assessment (yes/no + confidence)
- a recommended next action

## Usage

```
/kw_list_unfinished_tasks
```

No arguments required.

## Example output

```
⚠ 2 unfinished tasks

task_id    : task_01KNQYSASNSF1VVCJ3KGVX95AN
project    : henry-gh-telegram-2
status     : awaiting_revision / run cancelled (implement)
elapsed    : 30h 16m
resumable  : yes (high confidence)
note       : Run was cancelled — ready to retry
next action: Retry via /kw_implement with a revised description, or close via /kw_complete_task
description: Implement step 2: replace the hand-rolled validators with Pydantic models

task_id    : task_01KNP24Y94BCAY5FPW4QJBVHB4
project    : henry-local-telegram-1
status     : failed / run error (implement)
elapsed    : 47h 53m
resumable  : yes (high confidence)
next action: Retry the implement run via /kw_implement
description: Describe the top-level structure
```

## Notes

- Read-only — does not change any state
- Sorted oldest-unresolved first (most urgent at top)
- Use `/kw_task_status` for full detail on a specific task
- Use `/kw_cancel_task` to stop an active stuck task first, then it will appear here
