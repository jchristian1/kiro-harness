---
name: kw_update_project_source_url
description: Update a project's source_url in place when the original path has moved or changed. Preserves project identity and task history before workspace reinitialization.
user-invocable: true
disable-model-invocation: true
command-dispatch: tool
command-tool: kw_update_project_source_url
command-arg-mode: raw
---

# kw_update_project_source_url

Update a project's source path or URL in place when the original location has moved or changed.

Preserves project identity and task history. Use this when a local folder moved to a new path, or when a GitHub repo URL changed.

## Usage

```
/kw_update_project_source_url {"project_id": "proj_...", "source_url": "/new/path/to/project"}
```

## Supported source types

- `local_folder` — update to new local path
- `local_repo` — update to new local git repo path
- `github_repo` — update to new GitHub URL

Not supported for `new_project` (managed path is derived from project name, not source_url).

## Typical repair flow

1. `/kw_list_project_continuity` — identify projects with invalid/missing workspace
2. `/kw_update_project_source_url` — update source_url if the path moved
3. `/kw_reinitialize_project_workspace` — rebind workspace to the new path

## Example output

```
✎ source_url updated — henry-local-telegram-1 (proj_01KNP24Y7V07JGDQH0BTXMX2RM)

source           : local_folder
old source_url   : /tmp/henry-local-telegram-1
new source_url   : /home/christian/kiro-workspaces/henry-local-telegram-1
path exists      : ✓ yes

Path exists — run POST /projects/{id}/workspace/reinitialize to rebind the workspace.

Next: run /kw_reinitialize_project_workspace to rebind the workspace.
```

## Notes

- Does not change project name, ID, or task history
- Does not create or modify any workspace record — use `/kw_reinitialize_project_workspace` after
- If the new path does not exist yet, the update still succeeds but workspace recovery will be blocked until the path is created
