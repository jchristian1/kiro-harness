---
name: kw_get_project_workspace
description: Get the canonical workspace for a project. Shows which workspace path is active, when it was last used, and whether continuity is preserved for follow-up work.
user-invocable: true
disable-model-invocation: true
command-dispatch: tool
command-tool: kw_get_project_workspace
command-arg-mode: raw
---

# kw_get_project_workspace

Get the canonical workspace for a project — the path Kiro will use for all runs.

Use this before starting follow-up work to confirm which workspace is active and whether continuity is preserved from previous runs.

## Usage

```
/kw_get_project_workspace {"project_id": "proj_..."}
```

## Example output

```
Workspace

workspace_id     : ws_01KNP7621Q82E0AB19YRVQ903A
project_id       : proj_01KNP7621Q82E0AB19YRVQ903A
path             : /home/christian/kiro-workspaces/henry-gh-telegram-2
git_remote       : https://github.com/org/repo.git
git_branch       : main
created_at       : 2026-04-08T10:00:00+00:00
last_accessed_at : 2026-04-13T18:00:00+00:00
```

## Notes

- Read-only — does not create or modify any workspace
- Returns the canonical workspace: prefers the project's pinned workspace if valid, falls back to most recently accessed
- Use `/kw_implement` or `/kw_github_analyze` to start work — workspace reuse is automatic
