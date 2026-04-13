---
name: kw_resume_project
description: Resume the most recent unfinished task for a project. Retries failed or cancelled work, or reports the PM decision needed before resuming.
user-invocable: true
disable-model-invocation: true
command-dispatch: tool
command-tool: kw_resume_project
command-arg-mode: raw
---

# kw_resume_project

Resume the most recent unfinished task for a project. Automatically retries failed or cancelled work, or tells you what decision is needed for tasks that require PM input.

## Usage

```
/kw_resume_project {"project_id": "proj_..."}
```

## Outcomes

- `↺ retried` — fresh retry task created and run started (for failed or cancelled tasks)
- `⚠ needs_decision` — PM action required before retry is possible
- `✗ blocked` — cannot resume automatically (workspace unavailable, orphaned task)
- `✓ nothing_to_resume` — no unfinished tasks found

## Decision types (needs_decision)

- `approval_required` — use `/kw_approve_implement` to approve
- `revision_instructions_required` — use `/kw_implement` with revised description

## Example output

```
↺ retried — project proj_01KNP7621Q82E0AB19YRVQ903A

new_task_id   : task_01KP...
run_id        : run_01KP...
prior_task_id : task_01KN...
prior_status  : failed
mode          : implement
task_status   : implementing
run_status    : running
workspace     : /home/christian/kiro-workspaces/henry-gh-telegram-2

Resumed project by retrying task task_01KN... as new task task_01KP...
```

## Notes

- Non-blocking — returns immediately
- Use `/kw_task_status` to poll progress after a retry
- Use `/kw_list_unfinished_tasks` to see all unfinished tasks across all projects
- Use `/kw_retry_task` to retry a specific task by id
