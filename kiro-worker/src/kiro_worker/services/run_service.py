import json
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from ulid import ULID

from kiro_worker.db.models import Run, Artifact


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id(prefix: str) -> str:
    return f"{prefix}{ULID()}"


def create_run(
    db: Session,
    task_id: str,
    mode: str,
    agent: str,
    skill: str,
    context_snapshot: dict,
) -> Run:
    now = _now()
    run = Run(
        id=_new_id("run_"),
        task_id=task_id,
        mode=mode,
        status="running",
        agent=agent,
        skill=skill,
        context_snapshot=json.dumps(context_snapshot),
        raw_output=None,
        parse_status=None,
        failure_reason=None,
        started_at=now,
        completed_at=None,
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def complete_run(
    db: Session,
    run: Run,
    raw_output: str,
    parse_status: str,
    failure_reason: str | None,
) -> Run:
    run.status = "completed" if parse_status == "ok" else "parse_failed"
    run.raw_output = raw_output
    run.parse_status = parse_status
    run.failure_reason = failure_reason
    run.completed_at = _now()
    db.commit()
    db.refresh(run)
    return run


def fail_run(
    db: Session,
    run: Run,
    raw_output: str | None,
    failure_reason: str,
    parse_status: str | None = None,
) -> Run:
    run.status = "error" if parse_status is None else "parse_failed"
    run.raw_output = raw_output
    run.parse_status = parse_status
    run.failure_reason = failure_reason
    run.completed_at = _now()
    db.commit()
    db.refresh(run)
    return run


def create_artifact(
    db: Session,
    run_id: str,
    task_id: str,
    artifact_type: str,
    schema_version: str,
    content: dict,
) -> Artifact:
    now = _now()
    artifact = Artifact(
        id=_new_id("art_"),
        run_id=run_id,
        task_id=task_id,
        type=artifact_type,
        schema_version=schema_version,
        content=json.dumps(content),
        file_path=None,
        created_at=now,
    )
    db.add(artifact)
    db.commit()
    db.refresh(artifact)
    return artifact


def update_progress(
    db: Session,
    run: Run,
    progress_message: str,
    partial_output: str | None = None,
) -> Run:
    """Update progress fields on an active run. Called during streaming execution."""
    run.progress_message = progress_message
    run.last_activity_at = _now()
    if partial_output is not None:
        run.partial_output = partial_output[-2000:]  # rolling 2000-char window
    db.commit()
    return run


def cancel_run(
    db: Session,
    run: Run,
    reason: str | None = None,
) -> Run:
    """Mark a run as cancelled. Called when the Project Manager cancels an active task."""
    run.status = "cancelled"
    run.failure_reason = reason or "Cancelled by Project Manager"
    run.completed_at = _now()
    db.commit()
    db.refresh(run)
    return run


def get_run(db: Session, run_id: str) -> Run | None:
    return db.query(Run).filter(Run.id == run_id).first()


def get_runs_for_task(db: Session, task_id: str) -> list[Run]:
    return db.query(Run).filter(Run.task_id == task_id).order_by(Run.started_at.asc()).all()


def get_last_run(db: Session, task_id: str) -> Run | None:
    return db.query(Run).filter(Run.task_id == task_id).order_by(Run.started_at.desc()).first()


def get_artifact_for_run(db: Session, run_id: str) -> Artifact | None:
    return db.query(Artifact).filter(Artifact.run_id == run_id).first()
