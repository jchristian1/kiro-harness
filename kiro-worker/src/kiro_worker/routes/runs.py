import json
import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from kiro_worker.db.engine import get_db
from kiro_worker.schemas.run import RunResponse, RunListItem
from kiro_worker.schemas.artifact import ArtifactResponse
from kiro_worker.services import run_service

logger = logging.getLogger(__name__)
router = APIRouter()


def _error(code: str, message: str, details: dict = {}, status: int = 400):
    raise HTTPException(status_code=status, detail={"code": code, "message": message, "details": details})


@router.get("/runs/{run_id}")
def get_run(run_id: str, db: Session = Depends(get_db)) -> RunResponse:
    run = run_service.get_run(db, run_id)
    if not run:
        _error("NOT_FOUND", "Run not found.", {}, 404)

    try:
        context_snapshot = json.loads(run.context_snapshot)
    except Exception:
        context_snapshot = run.context_snapshot

    return RunResponse(
        id=run.id,
        task_id=run.task_id,
        mode=run.mode,
        status=run.status,
        agent=run.agent,
        skill=run.skill,
        context_snapshot=context_snapshot,
        raw_output=run.raw_output,
        parse_status=run.parse_status,
        failure_reason=run.failure_reason,
        started_at=run.started_at,
        completed_at=run.completed_at,
        progress_message=run.progress_message,
        last_activity_at=run.last_activity_at,
        partial_output=run.partial_output,
    )


@router.get("/runs/{run_id}/artifact")
def get_artifact(run_id: str, db: Session = Depends(get_db)) -> ArtifactResponse:
    run = run_service.get_run(db, run_id)
    if not run:
        _error("NOT_FOUND", "Run not found.", {}, 404)

    artifact = run_service.get_artifact_for_run(db, run_id)
    if not artifact:
        _error(
            "ARTIFACT_NOT_FOUND",
            "Run has no artifact. The run may still be in progress or failed to parse.",
            {"run_status": run.status, "parse_status": run.parse_status},
            404,
        )

    try:
        content = json.loads(artifact.content)
    except Exception:
        content = artifact.content

    return ArtifactResponse(
        id=artifact.id,
        run_id=artifact.run_id,
        task_id=artifact.task_id,
        type=artifact.type,
        schema_version=artifact.schema_version,
        content=content,
        file_path=artifact.file_path,
        created_at=artifact.created_at,
    )
