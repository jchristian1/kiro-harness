---
name: henry_local_folder_analyze
description: Open a local folder as a workspace and run a Kiro analysis. Returns structured artifact with tracing IDs.
user-invocable: true
command-dispatch: tool
command-tool: henry_local_folder_analyze
command-arg-mode: raw
---

Dispatches directly to the henry_local_folder_analyze tool.

Input: JSON object with name, path, description.

Example:
/henry_local_folder_analyze {"name": "my-project", "path": "/tmp/e2e-test", "description": "Describe the top-level structure."}
