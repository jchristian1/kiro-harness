---
name: kw_retry_task
description: Retry a failed, cancelled, or unfinished task by creating a fresh task with the same parameters and immediately starting a new run.
user-invocable: true
disable-model-invocation: true
command-dispatch: tool
command-tool: kw_retry_task
command-arg-mode: raw
---

# kw_retry_task

Retry a failed, cancelled, or unfinished task by creating a fresh task with the same parameters and immediately starting a non-blocking run.

## Usage

```
/kw_retry_task {"task_id": "task_..."}
```

## Allowed source states

- `failed` — run errored or parse failed
- `awaiting_revision` — run was cancelled or needs follow-up
- `awaiting_approval` — task is blocked on approval gate

## What happens

1. A new task is created with the same project, workspace, intent, source, operation, and description
2. The run mode is inherited from the prior task's last run (or defaults to `analyze`)
3. The run starts immediately in the background
4. Returns new_task_id, run_id, and status=running

This is a fresh retry — not magical continuation. The new task starts clean with the same parameters.

## Example output

```
↺ retry started — implement run

new_task_id    : task_01KP...
run_id         : run_01KP...
prior_task_id  : task_01KN...
prior_status   : failed
task_status    : implementing
run_status     : running
workspace      : /home/christian/kiro-workspaces/henry-gh-telegram-2
retry_type     : fresh_task

Implementation retry started as new task. Use kw_task_status to check progress.
```

## Notes

- Non-blocking — returns immediately
- Use `/kw_task_status` to poll progress
- Use `/kw_resume_project` to retry the latest unfinished task for a project without knowing the task_id
