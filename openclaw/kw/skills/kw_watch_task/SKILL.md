---
name: kw_watch_task
description: Watch an active task and provide progress updates every 10 seconds until it completes. Use after starting a run with kw_github_analyze, kw_implement, or similar skills.
user-invocable: true
---

# kw_watch_task

You are the Project Manager supervising a specialist run.

When this skill is invoked with a task_id:

1. Call `kw_task_status` with the task_id immediately to get the current state.

2. If the task is still running (status: analyzing, implementing, validating):
   - Report a short progress update to the user, for example:
     - "Still running — [progress_message if available]."
     - "Analysis in progress — last activity [last_activity_at]."
     - "Implementation underway — [progress_message]."
   - Wait 10 seconds, then call `kw_task_status` again.
   - Repeat until the task reaches a terminal state (done, failed, awaiting_revision).
   - Do not repeat identical updates if nothing changed — only report when there is meaningful new progress.

3. When the task completes, present the full structured final report:
   - For implementation: Result, What happened, Files changed, Validation, Known issues, Follow-ups, Next step
   - For analysis: Result, Key findings, Recommended steps, Risks, Tradeoffs, Next step

4. If the task fails, report the failure reason clearly.

Keep progress updates short and useful:
- "Still running — reviewing the route structure."
- "Now editing article update logic."
- "Validation is underway."
- "No new milestone yet, still active."

This is test/observation mode. The 10-second interval is intentional for observing behavior.
