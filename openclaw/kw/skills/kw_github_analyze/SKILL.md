---
name: kw_github_analyze
description: Start a Kiro analysis on a GitHub repo. Returns immediately with task_id, run_id, and status=analyzing. Use kw_task_status to poll progress and get the full structured result.
user-invocable: true
disable-model-invocation: true
command-dispatch: tool
command-tool: kw_github_analyze
command-arg-mode: raw
---

Dispatches to kw_github_analyze. Returns immediately — does not wait for Kiro to finish.

Input: {"name": "project-name", "repo_url": "https://github.com/org/repo", "description": "what to analyze"}

Returns: task_id, run_id, status=analyzing. Poll with /kw_task_status to get progress and final result.
