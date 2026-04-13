---
name: kw_list_active_projects
description: List all projects that currently have active specialist work in progress. Shows which projects are in motion and where activity is concentrated. Read-only.
user-invocable: true
disable-model-invocation: true
command-dispatch: tool
command-tool: kw_list_active_projects
command-arg-mode: raw
---

Dispatches to kw_list_active_projects. Returns all projects with at least one active task.

Input: {} (no parameters required)

Returns: list of active projects with task count, current status, and last activity.
