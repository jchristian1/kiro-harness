---
name: kw_task_status
description: Get the full status and structured result of a task. Shows progress for active runs and the complete Kiro report for completed runs including findings, files changed, validation, blockers, risks, follow-ups, and next step.
user-invocable: true
---

# kw_task_status

Call the `kw_task_status` tool with the provided task_id.

After receiving the tool result, present it as a clean readable report:

For active runs (status: analyzing, implementing, validating):
- Show current status and progress message
- Show last activity time
- Tell the user the run is still in progress

For completed runs (status: done, awaiting_revision):
Present the full structured Kiro report with these sections:

**Status:** [task status]
**Result:** [headline]
**What happened:** [changes_summary]
**Files changed:** [list each file with action and description]
**Validation:** [what ran or what was blocked]
**Known issues:** [any blockers]
**Follow-ups:** [recommended follow-up actions]
**Next step:** [recommended_next_step in plain English]

For analysis results, present:
**Status:** [task status]
**Result:** [headline]
**Key findings:** [list findings]
**Recommended steps:** [list implementation_steps]
**Risks:** [list risks]
**Tradeoffs:** [list tradeoffs]
**Open questions:** [list questions]
**Next step:** [recommended_next_step]

Do not show raw JSON. Present everything in clean readable text. Use the full content from the tool — do not compress into one sentence.
