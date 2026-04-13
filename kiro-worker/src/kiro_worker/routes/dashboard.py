"""
Dashboard routes — read-only manager-visibility endpoints.
These provide portfolio-level views across all projects and tasks.
No state changes, no run triggers.
"""
import json
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import text

from kiro_worker.db.engine import get_db
from kiro_worker.db.models import Task, Project, Run, Artifact, Meta

logger = logging.getLogger(__name__)
router = APIRouter()

# Active task states — Kiro is currently doing work
ACTIVE_TASK_STATES = {"opening", "analyzing", "implementing", "validating"}

# Pending decision states — PM needs to act
PENDING_DECISION_STATES = {"awaiting_revision", "awaiting_approval"}

# Unfinished states — work was started but not completed, not currently active
UNFINISHED_TASK_STATES = {"failed", "awaiting_revision", "awaiting_approval", "opening"}

# Reason and next action for each pending state
PENDING_REASONS = {
    "awaiting_revision": ("Kiro needs revised direction or the run was cancelled", "Provide revision instructions via /kw_implement, or close via /kw_complete_task"),
    "awaiting_approval": ("Task is blocked on an action-level approval gate", "Approve via /kw_approve_implement or close via /kw_complete_task"),
}

# Resume recommendations per state/run combination
def _resume_recommendation(task_status: str, run_status: str | None, run_mode: str | None) -> dict:
    """Return a resumability assessment and recommended next action."""
    if task_status == "failed":
        if run_status in ("error", "parse_failed"):
            return {
                "resumable": True,
                "resume_confidence": "high",
                "recommended_action": f"Retry the {run_mode or 'run'} via /kw_implement (implement) or /kw_github_analyze (analyze)",
                "resume_note": "Run failed — can be retried with the same or revised description",
            }
        return {
            "resumable": True,
            "resume_confidence": "medium",
            "recommended_action": "Retry via /kw_implement or close via /kw_complete_task",
            "resume_note": "Task failed — review failure reason before retrying",
        }
    if task_status == "awaiting_revision":
        if run_status == "cancelled":
            return {
                "resumable": True,
                "resume_confidence": "high",
                "recommended_action": "Retry via /kw_implement with a revised description, or close via /kw_complete_task",
                "resume_note": "Run was cancelled — ready to retry",
            }
        return {
            "resumable": True,
            "resume_confidence": "high",
            "recommended_action": "Provide revised instructions via /kw_implement, or close via /kw_complete_task",
            "resume_note": "Kiro completed the run but needs direction on next step",
        }
    if task_status == "awaiting_approval":
        return {
            "resumable": True,
            "resume_confidence": "high",
            "recommended_action": "Approve via /kw_approve_implement or close via /kw_complete_task",
            "resume_note": "Blocked on action-level approval gate",
        }
    if task_status == "opening":
        return {
            "resumable": False,
            "resume_confidence": "low",
            "recommended_action": "Close via /kw_complete_task — task never started a run",
            "resume_note": "Task got stuck before any run started — likely an orphaned task",
        }
    return {
        "resumable": False,
        "resume_confidence": "unknown",
        "recommended_action": "Inspect with /kw_task_status",
        "resume_note": "Unknown state",
    }


def _elapsed(started_at: str | None) -> str | None:
    if not started_at:
        return None
    try:
        start = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        delta = now - start
        total = int(delta.total_seconds())
        if total < 60:
            return f"{total}s"
        if total < 3600:
            return f"{total // 60}m {total % 60}s"
        return f"{total // 3600}h {(total % 3600) // 60}m"
    except Exception:
        return None


@router.get("/dashboard/active-tasks")
def list_active_tasks(db: Session = Depends(get_db)):
    """
    Return all tasks currently in an active state (opening, analyzing, implementing, validating).
    Sorted by last_activity_at descending (most recently active first).
    """
    tasks = (
        db.query(Task)
        .filter(Task.status.in_(ACTIVE_TASK_STATES))
        .order_by(Task.updated_at.desc())
        .all()
    )

    items = []
    for task in tasks:
        last_run = (
            db.query(Run)
            .filter(Run.task_id == task.id)
            .order_by(Run.started_at.desc())
            .first()
        )
        project = db.query(Project).filter(Project.id == task.project_id).first()
        items.append({
            "task_id": task.id,
            "project_id": task.project_id,
            "project_name": project.name if project else None,
            "task_status": task.status,
            "operation": task.operation,
            "description": task.description[:120] + "..." if len(task.description) > 120 else task.description,
            "run_id": last_run.id if last_run else None,
            "run_status": last_run.status if last_run else None,
            "run_mode": last_run.mode if last_run else None,
            "progress_message": last_run.progress_message if last_run else None,
            "last_activity_at": last_run.last_activity_at if last_run else task.updated_at,
            "started_at": last_run.started_at if last_run else task.created_at,
            "elapsed": _elapsed(last_run.started_at if last_run else task.created_at),
        })

    return {"active_tasks": items, "count": len(items)}


@router.get("/dashboard/active-projects")
def list_active_projects(db: Session = Depends(get_db)):
    """
    Return all projects that have at least one active task.
    Sorted by most recent activity first.
    """
    active_tasks = (
        db.query(Task)
        .filter(Task.status.in_(ACTIVE_TASK_STATES))
        .order_by(Task.updated_at.desc())
        .all()
    )

    # Group by project
    project_map: dict[str, dict] = {}
    for task in active_tasks:
        pid = task.project_id
        if pid not in project_map:
            project = db.query(Project).filter(Project.id == pid).first()
            project_map[pid] = {
                "project_id": pid,
                "project_name": project.name if project else None,
                "active_task_count": 0,
                "most_recent_task_id": None,
                "most_recent_task_status": None,
                "most_recent_progress": None,
                "last_activity_at": None,
            }
        entry = project_map[pid]
        entry["active_task_count"] += 1
        if entry["most_recent_task_id"] is None:
            # First task is most recent (already sorted)
            last_run = (
                db.query(Run)
                .filter(Run.task_id == task.id)
                .order_by(Run.started_at.desc())
                .first()
            )
            entry["most_recent_task_id"] = task.id
            entry["most_recent_task_status"] = task.status
            entry["most_recent_progress"] = last_run.progress_message if last_run else None
            entry["last_activity_at"] = (last_run.last_activity_at if last_run else None) or task.updated_at

    items = list(project_map.values())
    return {"active_projects": items, "count": len(items)}


@router.get("/dashboard/pending-decisions")
def list_pending_decisions(db: Session = Depends(get_db)):
    """
    Return all tasks that need Project Manager attention.
    Includes: awaiting_revision, awaiting_approval.
    Sorted by updated_at ascending (oldest unresolved first — most urgent).
    """
    tasks = (
        db.query(Task)
        .filter(Task.status.in_(PENDING_DECISION_STATES))
        .order_by(Task.updated_at.asc())
        .all()
    )

    items = []
    for task in tasks:
        last_run = (
            db.query(Run)
            .filter(Run.task_id == task.id)
            .order_by(Run.started_at.desc())
            .first()
        )
        project = db.query(Project).filter(Project.id == task.project_id).first()
        reason, next_action = PENDING_REASONS.get(task.status, ("Needs attention", "Check task status"))

        # Enrich reason for cancelled runs
        if last_run and last_run.status == "cancelled":
            reason = f"Run was cancelled: {last_run.failure_reason or 'no reason given'}"
            next_action = "Retry via /kw_implement or close via /kw_complete_task"

        items.append({
            "task_id": task.id,
            "project_id": task.project_id,
            "project_name": project.name if project else None,
            "task_status": task.status,
            "run_id": last_run.id if last_run else None,
            "run_status": last_run.status if last_run else None,
            "reason": reason,
            "next_action": next_action,
            "last_activity_at": (last_run.last_activity_at if last_run else None) or task.updated_at,
            "waiting_since": task.updated_at,
            "elapsed_waiting": _elapsed(task.updated_at),
        })

    return {"pending_decisions": items, "count": len(items)}


@router.get("/dashboard/unfinished-tasks")
def list_unfinished_tasks(db: Session = Depends(get_db)):
    """
    Return all tasks that were started but not completed and are not currently active.
    Includes: failed, awaiting_revision, awaiting_approval, opening (stuck/orphaned).
    Sorted by updated_at ascending (oldest unresolved first).
    Each item includes a resumability assessment and recommended next action.
    """
    tasks = (
        db.query(Task)
        .filter(Task.status.in_(UNFINISHED_TASK_STATES))
        .order_by(Task.updated_at.asc())
        .all()
    )

    items = []
    for task in tasks:
        last_run = (
            db.query(Run)
            .filter(Run.task_id == task.id)
            .order_by(Run.started_at.desc())
            .first()
        )
        last_artifact = (
            db.query(Artifact)
            .filter(Artifact.task_id == task.id)
            .order_by(Artifact.created_at.desc())
            .first()
        )
        project = db.query(Project).filter(Project.id == task.project_id).first()

        # Extract headline from artifact content JSON
        artifact_headline = None
        if last_artifact and last_artifact.content:
            try:
                artifact_data = json.loads(last_artifact.content)
                artifact_headline = artifact_data.get("headline") or artifact_data.get("summary") or artifact_data.get("title")
            except Exception:
                pass

        resume = _resume_recommendation(
            task_status=task.status,
            run_status=last_run.status if last_run else None,
            run_mode=last_run.mode if last_run else None,
        )

        items.append({
            "task_id": task.id,
            "project_id": task.project_id,
            "project_name": project.name if project else None,
            "task_status": task.status,
            "operation": task.operation,
            "description": task.description[:120] + "..." if len(task.description) > 120 else task.description,
            "run_id": last_run.id if last_run else None,
            "run_status": last_run.status if last_run else None,
            "run_mode": last_run.mode if last_run else None,
            "last_artifact_headline": artifact_headline,
            "unfinished_since": task.updated_at,
            "elapsed_unfinished": _elapsed(task.updated_at),
            **resume,
        })

    return {"unfinished_tasks": items, "count": len(items)}


# Workspace health categories
# healthy   — canonical workspace exists and path is valid on disk
# missing   — no workspace record exists for the project
# invalid   — workspace record exists but path is gone from disk
# stale     — workspace exists and is valid but has not been accessed in >7 days

import os
from datetime import timedelta

STALE_THRESHOLD_DAYS = 7


def _workspace_health(project, db: Session) -> tuple[str, str | None, str | None]:
    """
    Return (status, workspace_id, workspace_path) for a project.
    status: 'healthy' | 'stale' | 'invalid' | 'missing'
    """
    from kiro_worker.db.models import Workspace as WS

    # Prefer pinned workspace
    ws = None
    if project.workspace_id:
        ws = db.query(WS).filter(WS.id == project.workspace_id).first()

    # Fall back to most recently accessed
    if ws is None:
        ws = (
            db.query(WS)
            .filter(WS.project_id == project.id)
            .order_by(WS.last_accessed_at.desc())
            .first()
        )

    if ws is None:
        return "missing", None, None

    if not os.path.exists(ws.path):
        return "invalid", ws.id, ws.path

    # Check staleness
    try:
        last = datetime.fromisoformat(ws.last_accessed_at.replace("Z", "+00:00"))
        if (datetime.now(timezone.utc) - last) > timedelta(days=STALE_THRESHOLD_DAYS):
            return "stale", ws.id, ws.path
    except Exception:
        pass

    return "healthy", ws.id, ws.path


def _project_continuity_action(ws_status: str, unfinished_count: int, active_count: int) -> str:
    if ws_status == "missing":
        return "Re-initialize workspace via /kw_local_folder_analyze or /kw_github_analyze"
    if ws_status == "invalid":
        return "Workspace path is gone — re-initialize or update source_url"
    if active_count > 0:
        return "Work is in progress — monitor with /kw_list_active_tasks"
    if unfinished_count > 0:
        return "Resume or close unfinished tasks via /kw_list_unfinished_tasks"
    if ws_status == "stale":
        return "No recent activity — workspace is valid but idle"
    return "Project is healthy — no action needed"


@router.get("/dashboard/project-continuity")
def list_project_continuity(
    db: Session = Depends(get_db),
    include_archived: bool = False,
):
    """
    Portfolio-level project continuity audit.
    For each project: workspace health, unfinished task count, active task count,
    latest activity, shared-path warning, and a recommended PM action.
    Sorted by urgency: invalid/missing first, then shared-path, then unfinished, then stale, then healthy.

    Archived projects are hidden by default. Pass include_archived=true to include them.
    """
    from kiro_worker.db.models import Workspace as WS
    from kiro_worker.services.project_service import get_aliases
    import json as _json

    # Build set of archived project IDs from Meta table
    archive_rows = db.query(Meta).filter(Meta.key.like("project_archive:%")).all()
    archived_ids: set[str] = set()
    for row in archive_rows:
        try:
            data = _json.loads(row.value)
            if data.get("archived"):
                pid = row.key.removeprefix("project_archive:")
                archived_ids.add(pid)
        except Exception:
            pass

    all_projects = db.query(Project).order_by(Project.updated_at.desc()).all()

    # Filter archived projects unless explicitly requested
    if include_archived:
        projects = all_projects
    else:
        projects = [p for p in all_projects if p.id not in archived_ids]

    # Build shared-path map: workspace_id → [project_id, ...]
    # A workspace is "shared" when multiple projects pin the same workspace_id,
    # OR when a workspace's project_id differs from the project that currently pins it.
    # Strategy: for each valid workspace, find all projects that pin it via workspace_id.
    all_workspaces = db.query(WS).all()
    ws_id_to_projects: dict[str, list[str]] = {}
    for p in projects:
        if p.workspace_id:
            ws_id_to_projects.setdefault(p.workspace_id, [])
            if p.id not in ws_id_to_projects[p.workspace_id]:
                ws_id_to_projects[p.workspace_id].append(p.id)

    # Also detect path-level sharing: workspace records whose path is valid and whose
    # project_id differs from the project currently pinning them.
    # Since the DB has a UNIQUE constraint on path, each path has at most one workspace record.
    # Shared-path means: project A pins workspace W, but W.project_id = project B.
    ws_map: dict[str, WS] = {ws.id: ws for ws in all_workspaces}

    # Build project_id → project_name lookup for warning messages
    project_name_map = {p.id: p.name for p in projects}

    URGENCY = {"invalid": 0, "missing": 1, "shared_path": 2, "stale_unfinished": 3, "unfinished": 4, "stale": 5, "active": 6, "healthy": 7}

    items = []
    for project in projects:
        ws_status, ws_id, ws_path = _workspace_health(project, db)

        # Shared-path detection
        # Case 1: multiple projects pin the same workspace_id
        # Case 2: the project's canonical workspace record has a different project_id
        shared_path_warning = None
        shared_with: list[str] = []

        if ws_id and ws_id in ws_id_to_projects:
            pinning_projects = [pid for pid in ws_id_to_projects[ws_id] if pid != project.id]
            if pinning_projects:
                shared_with = pinning_projects

        # Also check if the workspace record's project_id differs from this project
        if ws_id and not shared_with:
            ws_record = ws_map.get(ws_id)
            if ws_record and ws_record.project_id != project.id:
                shared_with = [ws_record.project_id]

        if shared_with:
            other_names = [
                f"{project_name_map.get(pid, pid)} ({pid})" for pid in shared_with
            ]
            shared_path_warning = (
                f"Workspace path is shared with: {', '.join(other_names)}. "
                "Review whether this is intended. "
                "Use /kw_update_project_source_url to assign a unique path if needed."
            )

        # Count unfinished tasks
        unfinished_tasks = (
            db.query(Task)
            .filter(Task.project_id == project.id, Task.status.in_(UNFINISHED_TASK_STATES))
            .order_by(Task.updated_at.desc())
            .all()
        )
        unfinished_count = len(unfinished_tasks)
        most_recent_unfinished_id = unfinished_tasks[0].id if unfinished_tasks else None

        # Count active tasks
        active_count = (
            db.query(Task)
            .filter(Task.project_id == project.id, Task.status.in_(ACTIVE_TASK_STATES))
            .count()
        )

        # Latest activity: most recent run across all tasks for this project
        latest_run = (
            db.query(Run)
            .join(Task, Run.task_id == Task.id)
            .filter(Task.project_id == project.id)
            .order_by(Run.started_at.desc())
            .first()
        )
        latest_activity_at = (
            (latest_run.last_activity_at or latest_run.started_at) if latest_run else project.updated_at
        )

        recommended_action = _project_continuity_action(ws_status, unfinished_count, active_count)
        if shared_path_warning and ws_status == "healthy" and unfinished_count == 0 and active_count == 0:
            recommended_action = "Review shared workspace path — use /kw_update_project_source_url to assign a unique path if needed"

        # Compute urgency bucket for sorting
        if ws_status in ("invalid", "missing"):
            urgency_key = ws_status
        elif shared_with and ws_status == "healthy" and unfinished_count == 0:
            urgency_key = "shared_path"
        elif active_count > 0:
            urgency_key = "active"
        elif unfinished_count > 0 and ws_status == "stale":
            urgency_key = "stale_unfinished"
        elif unfinished_count > 0:
            urgency_key = "unfinished"
        elif ws_status == "stale":
            urgency_key = "stale"
        else:
            urgency_key = "healthy"

        items.append({
            "project_id": project.id,
            "project_name": project.name,
            "aliases": get_aliases(db, project.id),
            "source": project.source,
            "archived": project.id in archived_ids,
            "workspace_id": ws_id,
            "workspace_path": ws_path,
            "workspace_status": ws_status,
            "shared_path_warning": shared_path_warning,
            "shared_with_project_ids": shared_with if shared_with else None,
            "unfinished_task_count": unfinished_count,
            "active_task_count": active_count,
            "most_recent_unfinished_task_id": most_recent_unfinished_id,
            "latest_activity_at": latest_activity_at,
            "elapsed_since_activity": _elapsed(latest_activity_at),
            "recommended_action": recommended_action,
            "_urgency": URGENCY.get(urgency_key, 99),
        })

    # Sort by urgency ascending (most urgent first), then by latest_activity_at descending
    items.sort(key=lambda x: (x["_urgency"], x.get("latest_activity_at") or ""))
    for item in items:
        del item["_urgency"]

    # Summary counts
    shared_path_count = sum(1 for i in items if i["shared_path_warning"])
    summary = {
        "healthy": sum(1 for i in items if i["workspace_status"] == "healthy" and i["unfinished_task_count"] == 0 and i["active_task_count"] == 0 and not i["shared_path_warning"]),
        "active": sum(1 for i in items if i["active_task_count"] > 0),
        "unfinished": sum(1 for i in items if i["unfinished_task_count"] > 0 and i["active_task_count"] == 0),
        "stale": sum(1 for i in items if i["workspace_status"] == "stale" and i["unfinished_task_count"] == 0),
        "invalid": sum(1 for i in items if i["workspace_status"] == "invalid"),
        "missing": sum(1 for i in items if i["workspace_status"] == "missing"),
        "shared_path": shared_path_count,
        "archived_shown": sum(1 for i in items if i.get("archived")),
        "archived_hidden": len(archived_ids) - sum(1 for i in items if i.get("archived")),
    }

    return {"projects": items, "count": len(items), "summary": summary, "include_archived": include_archived}
