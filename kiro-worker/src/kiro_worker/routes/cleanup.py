"""
Cleanup routes — bulk PM portfolio hygiene actions.
All actions are non-destructive: close, cancel, or archive (mark inactive via Meta).
No hard deletes. Each action reports exactly what was matched and why.
"""
import json
import logging
import re
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional

from kiro_worker.db.engine import get_db
from kiro_worker.db.models import Task, Project, Run, Meta
from kiro_worker.domain.enums import TaskStatus
from kiro_worker.services import run_service

logger = logging.getLogger(__name__)
router = APIRouter()

# ── helpers ──────────────────────────────────────────────────────────────────

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _elapsed_hours(ts: str | None) -> float | None:
    if not ts:
        return None
    try:
        t = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return (datetime.now(timezone.utc) - t).total_seconds() / 3600
    except Exception:
        return None


def _desc_key(description: str) -> str:
    """Normalise description to a dedup key: lowercase, strip whitespace, first 120 chars."""
    return description.strip().lower()[:120]


# ── schemas ───────────────────────────────────────────────────────────────────

class DuplicateTasksRequest(BaseModel):
    project_id: Optional[str] = None   # scope to one project; None = all projects
    dry_run: bool = False               # if True, report matches without closing


class StaleTasksRequest(BaseModel):
    stale_hours: float = 4.0           # tasks with no activity for this many hours
    dry_run: bool = False


class DeadProjectsRequest(BaseModel):
    name_patterns: list[str] = [       # regex patterns matched against project name
        r"^test",
        r"^smoke",
        r"^debug",
        r"^e2e",
        r"^tmp",
        r"^temp",
    ]
    dry_run: bool = False


# ── endpoints ─────────────────────────────────────────────────────────────────

@router.post("/cleanup/duplicate-tasks")
def bulk_close_duplicate_tasks(body: DuplicateTasksRequest, db: Session = Depends(get_db)):
    """
    Close duplicate dead unfinished tasks.

    Duplicate rule: same project_id + operation + description key (first 120 chars, normalised),
    status in {failed, awaiting_revision, awaiting_approval, opening},
    AND not the most recently updated task in that group.

    The newest task in each duplicate group is kept; all older duplicates are closed (→ done).
    Active tasks (opening/analyzing/implementing/validating) are never touched.
    """
    CLOSEABLE = {"failed", "awaiting_revision", "awaiting_approval", "opening"}

    q = db.query(Task).filter(Task.status.in_(CLOSEABLE))
    if body.project_id:
        q = q.filter(Task.project_id == body.project_id)
    candidates = q.order_by(Task.project_id, Task.operation, Task.updated_at.desc()).all()

    # Group by (project_id, operation, desc_key)
    groups: dict[tuple, list[Task]] = {}
    for task in candidates:
        key = (task.project_id, task.operation, _desc_key(task.description))
        groups.setdefault(key, []).append(task)

    closed: list[dict] = []
    skipped: list[dict] = []

    for key, tasks in groups.items():
        if len(tasks) < 2:
            continue  # not a duplicate group
        # tasks are sorted newest-first (updated_at desc)
        keeper = tasks[0]
        duplicates = tasks[1:]
        for task in duplicates:
            if task.status in ("opening", "analyzing", "implementing", "validating"):
                skipped.append({
                    "task_id": task.id,
                    "reason": f"active state '{task.status}' — not safe to close",
                })
                continue
            if not body.dry_run:
                task.status = TaskStatus.done.value
                task.updated_at = _now()
            closed.append({
                "task_id": task.id,
                "project_id": task.project_id,
                "status_before": task.status if body.dry_run else "done",
                "operation": task.operation,
                "description_key": _desc_key(task.description),
                "kept_task_id": keeper.id,
                "reason": "duplicate of newer task in same project+operation+description group",
            })

    if not body.dry_run and closed:
        db.commit()

    return {
        "action": "bulk_close_duplicate_tasks",
        "dry_run": body.dry_run,
        "criteria": {
            "status_filter": list(CLOSEABLE),
            "duplicate_rule": "same project_id + operation + description[:120] (normalised), keep newest",
            "project_scope": body.project_id or "all projects",
        },
        "closed_count": len(closed),
        "skipped_count": len(skipped),
        "closed": closed,
        "skipped": skipped,
        "message": (
            f"{'[DRY RUN] Would close' if body.dry_run else 'Closed'} {len(closed)} duplicate task(s). "
            f"{len(skipped)} skipped."
        ),
    }


@router.post("/cleanup/stale-tasks")
def bulk_cancel_stale_tasks(body: StaleTasksRequest, db: Session = Depends(get_db)):
    """
    Cancel active tasks with no activity for longer than stale_hours.

    Stale rule: task status in {opening, analyzing, implementing, validating}
    AND last_activity_at (or task.updated_at) is older than stale_hours ago.
    AND the task's last run is still in 'running' status.

    Cancellation: marks run as cancelled, transitions task to awaiting_revision.
    Does NOT kill subprocesses (those may already be dead; this is a DB cleanup).
    """
    ACTIVE = {"opening", "analyzing", "implementing", "validating"}
    cutoff = datetime.now(timezone.utc) - timedelta(hours=body.stale_hours)
    cutoff_str = cutoff.isoformat()

    active_tasks = db.query(Task).filter(Task.status.in_(ACTIVE)).all()

    cancelled: list[dict] = []
    skipped: list[dict] = []

    for task in active_tasks:
        last_run = run_service.get_last_run(db, task.id)

        # Determine last activity timestamp
        last_activity = None
        if last_run:
            last_activity = last_run.last_activity_at or last_run.started_at
        if not last_activity:
            last_activity = task.updated_at

        elapsed = _elapsed_hours(last_activity)
        if elapsed is None or elapsed < body.stale_hours:
            skipped.append({
                "task_id": task.id,
                "task_status": task.status,
                "elapsed_hours": round(elapsed, 1) if elapsed else None,
                "reason": f"not stale (last activity {round(elapsed, 1) if elapsed else '?'}h ago, threshold {body.stale_hours}h)",
            })
            continue

        if not body.dry_run:
            # Mark run as cancelled if it is still running
            if last_run and last_run.status == "running":
                last_run.status = "cancelled"
                last_run.failure_reason = f"Bulk stale cleanup: no activity for {round(elapsed, 1)}h"
                last_run.completed_at = _now()
            # Transition task to awaiting_revision
            task.status = TaskStatus.awaiting_revision.value
            task.updated_at = _now()

        cancelled.append({
            "task_id": task.id,
            "project_id": task.project_id,
            "task_status_before": task.status if body.dry_run else TaskStatus.awaiting_revision.value,
            "run_id": last_run.id if last_run else None,
            "run_status_before": last_run.status if last_run else None,
            "elapsed_hours": round(elapsed, 1),
            "reason": f"no activity for {round(elapsed, 1)}h (threshold: {body.stale_hours}h)",
        })

    if not body.dry_run and cancelled:
        db.commit()

    return {
        "action": "bulk_cancel_stale_tasks",
        "dry_run": body.dry_run,
        "criteria": {
            "status_filter": list(ACTIVE),
            "stale_threshold_hours": body.stale_hours,
            "stale_rule": "last_activity_at (or task.updated_at) older than threshold",
        },
        "cancelled_count": len(cancelled),
        "skipped_count": len(skipped),
        "cancelled": cancelled,
        "skipped": skipped,
        "message": (
            f"{'[DRY RUN] Would cancel' if body.dry_run else 'Cancelled'} {len(cancelled)} stale task(s). "
            f"{len(skipped)} skipped."
        ),
    }


@router.post("/cleanup/dead-projects")
def bulk_archive_dead_projects(body: DeadProjectsRequest, db: Session = Depends(get_db)):
    """
    Archive dead test/smoke/debug projects.

    Dead project rule:
    - project name matches one of the name_patterns (regex, case-insensitive)
    - AND no active tasks (opening/analyzing/implementing/validating)
    - AND no successful completed runs in the last 7 days

    Archive = store 'archived:True' in Meta table under key 'project_archive:{project_id}'.
    Does NOT delete the project or its tasks/runs/artifacts.
    Archived projects are excluded from future continuity audit results.
    """
    ACTIVE = {"opening", "analyzing", "implementing", "validating"}
    recent_cutoff = datetime.now(timezone.utc) - timedelta(days=7)

    compiled = []
    for pat in body.name_patterns:
        try:
            compiled.append(re.compile(pat, re.IGNORECASE))
        except re.error as e:
            logger.warning(f"Invalid pattern '{pat}': {e}")

    all_projects = db.query(Project).all()

    archived: list[dict] = []
    skipped: list[dict] = []

    for project in all_projects:
        # Check name pattern
        if not any(p.search(project.name) for p in compiled):
            continue

        # Check for active tasks
        active_count = db.query(Task).filter(
            Task.project_id == project.id,
            Task.status.in_(ACTIVE),
        ).count()
        if active_count > 0:
            skipped.append({
                "project_id": project.id,
                "project_name": project.name,
                "reason": f"has {active_count} active task(s) — not safe to archive",
            })
            continue

        # Check for recent successful runs
        recent_success = (
            db.query(Run)
            .join(Task, Run.task_id == Task.id)
            .filter(
                Task.project_id == project.id,
                Run.status == "completed",
                Run.completed_at >= recent_cutoff.isoformat(),
            )
            .first()
        )
        if recent_success:
            skipped.append({
                "project_id": project.id,
                "project_name": project.name,
                "reason": f"has recent successful run {recent_success.id} — not safe to archive",
            })
            continue

        # Check if already archived
        archive_key = f"project_archive:{project.id}"
        existing = db.query(Meta).filter(Meta.key == archive_key).first()
        if existing:
            skipped.append({
                "project_id": project.id,
                "project_name": project.name,
                "reason": "already archived",
            })
            continue

        if not body.dry_run:
            meta = Meta(key=archive_key, value=json.dumps({
                "archived": True,
                "archived_at": _now(),
                "reason": "bulk dead-project cleanup",
                "matched_pattern": next((p.pattern for p in compiled if p.search(project.name)), None),
            }))
            db.add(meta)

        archived.append({
            "project_id": project.id,
            "project_name": project.name,
            "source": project.source,
            "matched_pattern": next((p.pattern for p in compiled if p.search(project.name)), None),
            "reason": "name matches dead-project pattern, no active tasks, no recent successful runs",
        })

    if not body.dry_run and archived:
        db.commit()

    return {
        "action": "bulk_archive_dead_projects",
        "dry_run": body.dry_run,
        "criteria": {
            "name_patterns": body.name_patterns,
            "active_task_check": "no active tasks allowed",
            "recent_success_check": "no completed runs in last 7 days",
        },
        "archived_count": len(archived),
        "skipped_count": len(skipped),
        "archived": archived,
        "skipped": skipped,
        "message": (
            f"{'[DRY RUN] Would archive' if body.dry_run else 'Archived'} {len(archived)} dead project(s). "
            f"{len(skipped)} skipped."
        ),
    }
