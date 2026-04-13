---
user-invocable: true
disable-model-invocation: true
command-dispatch: tool
command-tool: kw_list_project_continuity
command-arg-mode: raw
---

# kw_list_project_continuity

Portfolio-level project continuity audit. Shows workspace health, unfinished task counts, active task counts, and a recommended action for every project.

Use this after a restart or context switch to quickly see which projects are healthy, which have unfinished work, and which need re-initialization.

## Usage

```
/kw_list_project_continuity
```

No arguments required.

## Workspace status values

- `✓ healthy` — canonical workspace exists and path is valid
- `~ stale` — workspace is valid but has not been accessed in >7 days
- `✗ invalid` — workspace record exists but the path is gone from disk
- `✗ missing` — no workspace record exists for the project

## Output is sorted by urgency

1. invalid / missing workspace (needs re-initialization)
2. unfinished tasks with stale workspace
3. unfinished tasks (ready to resume)
4. stale but idle
5. active (work in progress)
6. healthy and idle

## Example output

```
5 projects — 1 invalid, 2 unfinished, 1 stale, 1 healthy

✗ henry-gh-telegram-2 (proj_01KNP7621Q82E0AB19YRVQ903A)
  workspace : invalid — /home/christian/kiro-workspaces/henry-gh-telegram-2
  unfinished: 9 tasks
  latest    : task_01KNQYSASNSF1VVCJ3KGVX95AN
  last seen : 30h 16m ago
  action    : Workspace path is gone — re-initialize or update source_url

✓ henry-local-telegram-1 (proj_01KNP24Y7V07JGDQH0BTXMX2RM)
  workspace : healthy — /home/christian/kiro-workspaces/henry-local-telegram-1
  unfinished: 1 task
  latest    : task_01KNP24Y94BCAY5FPW4QJBVHB4
  last seen : 47h 53m ago
  action    : Resume or close unfinished tasks via /kw_list_unfinished_tasks
```

## Notes

- Read-only — does not change any state
- Use `/kw_list_unfinished_tasks` to drill into specific unfinished tasks
- Use `/kw_get_project_workspace` to inspect a specific project's workspace
- Use `/kw_local_folder_analyze` or `/kw_github_analyze` to re-initialize a broken project
