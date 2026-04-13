---
name: kw_validate_task
description: Start a validation run for a completed or awaiting-revision implementation task. Returns immediately with a new validation task and run.
user-invocable: true
disable-model-invocation: true
command-dispatch: tool
command-tool: kw_validate_task
command-arg-mode: raw
---

# kw_validate_task

Start a validation run for a completed or awaiting-revision implementation task.

Non-blocking — returns immediately with new task_id and run_id. Use `/kw_task_status` to check progress and see the full validation report when done.

## Usage

```
/kw_validate_task {"task_id": "task_..."}
```

## Allowed source task states

- `done` — implementation completed, ready to validate
- `awaiting_revision` — implementation needs review, validate before deciding
- `validating` — re-validate (retry validation)

## What happens

1. A new task is created on the same project with the same parameters
2. A validation run starts immediately in the background
3. Returns new_task_id, run_id, and status=running

## Example output

```
⟳ Validation started

new_task_id    : task_01KP...
run_id         : run_01KP...
prior_task_id  : task_01KN...
prior_status   : done
task_status    : validating
run_status     : running
workspace      : /home/christian/kiro-workspaces/henry-gh-telegram-2

Validation started. Use kw_task_status to check progress.

Poll progress with:
  /kw_task_status {"task_id":"task_01KP..."}
```

## Validation report (when complete)

When validation finishes, `/kw_task_status` shows:

```
✓ completed

RESULT: All tests pass — implementation is correct

VALIDATION: ✓ passed
COMMANDS RUN:
  • pytest tests/
  • mypy src/

NEXT STEP: Mark as done
```

Or if validation fails:

```
✗ completed with warnings — review needed

VALIDATION: ✗ failed
ISSUES FOUND:
  • test_foo.py::test_bar FAILED — assertion error
  • mypy: 2 type errors in src/main.py

NEXT STEP: Revision needed
```

## Notes

- Non-blocking — returns immediately
- Use `/kw_task_status` to poll progress
- Use `/kw_complete_task` to close the task after passing validation
- Use `/kw_implement` to request revision if validation fails
