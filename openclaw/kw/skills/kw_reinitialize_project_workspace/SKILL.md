---
name: kw_reinitialize_project_workspace
description: Recover a project's canonical workspace when it is missing or invalid. Rebinds local sources, reclones GitHub repos, or recreates managed new-project workspaces when possible.
user-invocable: true
disable-model-invocation: true
command-dispatch: tool
command-tool: kw_reinitialize_project_workspace
command-arg-mode: raw
---

# kw_reinitialize_project_workspace

Recover a project's canonical workspace when it is missing or invalid.

Use this after `/kw_list_project_continuity` identifies a project as `invalid` or `missing`. The worker inspects the project source and attempts the smallest safe recovery.

## Usage

```
/kw_reinitialize_project_workspace {"project_id": "proj_..."}
```

## Outcomes

- `✓ already_healthy` — workspace is valid, no action taken
- `↺ rebound` — source path still exists on disk; new workspace record created and pinned
- `✦ recreated` — workspace directory recreated (new_project) or repo re-cloned (github_repo)
- `✗ blocked` — recovery not possible without manual action (source path gone, clone failed, etc.)

## Source-specific behaviour

- `local_folder` / `local_repo`: rebinds to `source_url` if the path still exists on disk. Blocked if the path is gone.
- `github_repo`: re-clones from `source_url` into the managed workspace path if needed.
- `new_project`: recreates the managed directory under the configured workspace root.

## Example output

```
↺ rebound — henry-local-telegram-1 (proj_01KNP24Y7V07JGDQH0BTXMX2RM)

source           : local_folder
outcome          : rebound
workspace_id     : ws_01KP44B9W3RET5AJ09FMKA280H
workspace_path   : /home/christian/kiro-workspaces/henry-local-telegram-1
previous_ws_id   : ws_01KNP24Y8D720XQ1R4A5NWFXGF
reason           : Source path exists on disk — new workspace record created and pinned

Workspace rebound to existing source path: /home/christian/kiro-workspaces/henry-local-telegram-1

Follow-up tasks can now reuse this workspace via /kw_implement or /kw_github_analyze.
```

## Notes

- Does not delete old workspace records — history is preserved
- After recovery, `/kw_list_project_continuity` will show the project as `healthy`
- For `blocked` outcomes, the PM must fix the source path or create a new project
