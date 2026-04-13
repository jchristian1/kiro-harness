---
name: kw_set_project_alias
description: Assign a friendly alias to a project so it can be referenced by name instead of project_id. Aliases are case-insensitive and globally unique.
user-invocable: true
disable-model-invocation: true
command-dispatch: tool
command-tool: kw_set_project_alias
command-arg-mode: raw
---

# kw_set_project_alias

Assign a friendly alias to a project so it can be referenced by name instead of project_id.

Aliases are case-insensitive and globally unique. Once set, use `/kw_resolve_project` to look up the project by alias.

## Usage

```
/kw_set_project_alias {"project_id": "proj_...", "alias": "fastapi harness"}
```

## Example output

```
✎ alias set — henry-gh-telegram-2 (proj_01KNP7621Q82E0AB19YRVQ903A)

aliases : fastapi harness, telegram bot

Alias 'fastapi harness' added.
```

## Notes

- Aliases are stored lowercase
- Duplicate aliases on the same project are a no-op (idempotent)
- If the alias is taken by another project, returns ALIAS_CONFLICT with the conflicting project name
- Use `/kw_resolve_project` to look up a project by alias
