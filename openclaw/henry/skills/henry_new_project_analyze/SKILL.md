---
name: henry_new_project_analyze
description: Create a brand-new project from scratch, open its workspace, and run a Kiro analysis.
user-invocable: true
command-dispatch: tool
command-tool: henry_new_project_analyze
command-arg-mode: raw
---

Dispatches directly to the henry_new_project_analyze tool.

Input: JSON object with name, source_url, description.

Example:
/henry_new_project_analyze {"name": "my-project", "source_url": "/tmp/new-workspace", "description": "Bootstrap a new Python API."}
