---
user-invocable: true
disable-model-invocation: true
command-dispatch: tool
command-tool: kw_bulk_cleanup
command-arg-mode: raw
---

# kw_bulk_cleanup

Bulk PM portfolio hygiene. Three modes for cleaning up stale, duplicate, or dead work.

Always use `dry_run: true` first to preview what will be affected.

## Modes

### duplicate_tasks
Close duplicate dead unfinished tasks.

Rule: same project + operation + description (first 120 chars, normalised) → keep newest, close older duplicates.
Targets: failed, awaiting_revision, awaiting_approval, opening.
Never touches active tasks.

```
/kw_bulk_cleanup {"mode": "duplicate_tasks", "dry_run": true}
/kw_bulk_cleanup {"mode": "duplicate_tasks", "dry_run": false}
/kw_bulk_cleanup {"mode": "duplicate_tasks", "project_id": "proj_...", "dry_run": false}
```

### stale_tasks
Cancel active tasks with no activity for N hours (default: 4h).

Rule: task in {opening, analyzing, implementing, validating} with last_activity_at older than threshold.
Marks run as cancelled, transitions task to awaiting_revision.
Does NOT kill subprocesses — DB cleanup only.

```
/kw_bulk_cleanup {"mode": "stale_tasks", "dry_run": true}
/kw_bulk_cleanup {"mode": "stale_tasks", "stale_hours": 8, "dry_run": false}
```

### dead_projects
Archive test/smoke/debug projects with no active work and no recent successful runs.

Rule: name matches pattern (test*, smoke*, debug*, e2e*, tmp*, temp*) + no active tasks + no completed runs in last 7 days.
Archive = stored in Meta table. Non-destructive — project history is preserved.

```
/kw_bulk_cleanup {"mode": "dead_projects", "dry_run": true}
/kw_bulk_cleanup {"mode": "dead_projects", "dry_run": false}
```

## Example output (dry_run)

```
[DRY RUN] Duplicate dead task cleanup

message : [DRY RUN] Would close 8 duplicate task(s). 0 skipped.

Criteria:
  status_filter: failed, awaiting_revision, awaiting_approval, opening
  duplicate_rule: same project_id + operation + description[:120] (normalised), keep newest
  project_scope: all projects

Would Closed (8):
  ✗ task_01KNPANY4VB0D234B79W36ZMK1 — duplicate of newer task in same project+operation+description group
    kept: task_01KNQYSASNSF1VVCJ3KGVX95AN
  ...
```

## Notes

- Always use `dry_run: true` first
- Bulk actions are non-destructive: close, cancel, or archive only
- No hard deletes
- Each action reports exactly what was matched and why
