---
name: henry_github_analyze
description: Clone a GitHub repo, open its workspace, and run a Kiro analysis. Returns structured artifact with tracing IDs.
user-invocable: true
command-dispatch: tool
command-tool: henry_github_analyze
command-arg-mode: raw
---

Dispatches directly to the henry_github_analyze tool.

Input: JSON object with name, repo_url, description.

Example:
/henry_github_analyze {"name": "my-project", "repo_url": "https://github.com/org/repo", "description": "Describe the top-level structure."}
