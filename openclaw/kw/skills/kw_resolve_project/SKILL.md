---
name: kw_resolve_project
description: Resolve a project by id, canonical name, or alias. Returns the project_id, canonical name, aliases, and how the query matched.
user-invocable: true
disable-model-invocation: true
command-dispatch: tool
command-tool: kw_resolve_project
command-arg-mode: raw
---

# kw_resolve_project

Resolve a project by id, canonical name, or alias. Returns the project_id, canonical name, aliases, and how the query matched.

Use this to find a project before running other kw commands, or to confirm which project an alias points to.

## Usage

```
/kw_resolve_project {"query": "fastapi harness"}
```

## Lookup order

1. Exact project id
2. Exact canonical name
3. Case-insensitive canonical name
4. Alias (case-insensitive)

## Example output

```
✎ matched by alias — "fastapi harness"

project_id   : proj_01KNP7621Q82E0AB19YRVQ903A
name         : henry-gh-telegram-2
source       : github_repo
aliases      : fastapi harness, telegram bot
workspace_id : ws_01KNP7621Q82E0AB19YRVQ903A
```

## Notes

- Returns NOT_FOUND if no project matches
- Use `/kw_set_project_alias` to assign aliases
