import json
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from ulid import ULID

from kiro_worker.db.models import Task, Artifact
from kiro_worker.domain.enums import Intent, Source, Operation, TaskStatus
from kiro_worker.domain.state_machine import validate_transition, TERMINAL_STATES


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id(prefix: str) -> str:
    return f"{prefix}{ULID()}"


def create_task(
    db: Session,
    project_id: str,
    workspace_id: str,
    intent: Intent,
    source: Source,
    operation: Operation,
    description: str,
) -> Task:
    now = _now()
    task = Task(
        id=_new_id("task_"),
        project_id=project_id,
        workspace_id=workspace_id,
        intent=intent.value,
        source=source.value,
        operation=operation.value,
        description=description,
        status=TaskStatus.created.value,
        approved_at=None,
        created_at=now,
        updated_at=now,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def get_task(db: Session, task_id: str) -> Task | None:
    return db.query(Task).filter(Task.id == task_id).first()


def get_active_task(db: Session, project_id: str) -> Task | None:
    """Return the most recently created non-terminal task for the project."""
    terminal = [s.value for s in TERMINAL_STATES]
    return (
        db.query(Task)
        .filter(Task.project_id == project_id, Task.status.notin_(terminal))
        .order_by(Task.created_at.desc())
        .first()
    )


def transition_task(db: Session, task: Task, new_status: TaskStatus) -> Task:
    """Validate and apply a state transition."""
    current = TaskStatus(task.status)
    if not validate_transition(current, new_status):
        raise ValueError(f"Invalid transition: {current.value} → {new_status.value}")
    task.status = new_status.value
    task.updated_at = _now()
    db.commit()
    db.refresh(task)
    return task


def approve_task(db: Session, task: Task) -> Task:
    """Set approved_at and transition to implementing."""
    if TaskStatus(task.status) != TaskStatus.awaiting_approval:
        raise ValueError(f"Task not in awaiting_approval: {task.status}")
    task.approved_at = _now()
    task.status = TaskStatus.implementing.value
    task.updated_at = _now()
    db.commit()
    db.refresh(task)
    return task


def revise_task(db: Session, task: Task) -> Task:
    """Transition awaiting_revision → implementing."""
    if TaskStatus(task.status) != TaskStatus.awaiting_revision:
        raise ValueError(f"Task not in awaiting_revision: {task.status}")
    task.status = TaskStatus.implementing.value
    task.updated_at = _now()
    db.commit()
    db.refresh(task)
    return task


def build_resume_context(db: Session, task: Task, workspace_path: str, revision_instructions: str | None = None) -> dict:
    """Construct the resume context object from DB."""
    # Get most recent analysis artifact
    analysis_artifact = (
        db.query(Artifact)
        .filter(Artifact.task_id == task.id, Artifact.type == "analysis")
        .order_by(Artifact.created_at.desc())
        .first()
    )
    prior_analysis = None
    approved_plan = None
    if analysis_artifact:
        try:
            prior_analysis = json.loads(analysis_artifact.content)
        except Exception:
            prior_analysis = None
        if task.approved_at:
            approved_plan = prior_analysis

    return {
        "task_id": task.id,
        "intent": task.intent,
        "source": task.source,
        "operation": task.operation,
        "description": task.description,
        "workspace_path": workspace_path,
        "current_status": task.status,
        "prior_analysis": prior_analysis,
        "approved_plan": approved_plan,
        "revision_instructions": revision_instructions,
    }
