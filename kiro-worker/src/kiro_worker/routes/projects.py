import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from kiro_worker.db.engine import get_db
from kiro_worker.schemas.project import ProjectCreate, ProjectResponse
from kiro_worker.schemas.workspace import WorkspaceCreate, WorkspaceResponse
from kiro_worker.schemas.task import TaskResponse
from kiro_worker.schemas.run import RunSummary
from kiro_worker.services import project_service, workspace_service, task_service, run_service
from kiro_worker.domain.enums import Source
from kiro_worker.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()


def _error(code: str, message: str, details: dict = {}, status: int = 400):
    raise HTTPException(status_code=status, detail={"code": code, "message": message, "details": details})


def _task_to_response(task, db: Session) -> TaskResponse:
    last_run = run_service.get_last_run(db, task.id)
    last_run_summary = None
    if last_run:
        last_run_summary = RunSummary(
            id=last_run.id,
            mode=last_run.mode,
            status=last_run.status,
            started_at=last_run.started_at,
            completed_at=last_run.completed_at,
            failure_reason=last_run.failure_reason,
        )
    return TaskResponse(
        id=task.id,
        project_id=task.project_id,
        workspace_id=task.workspace_id,
        intent=task.intent,
        source=task.source,
        operation=task.operation,
        description=task.description,
        status=task.status,
        approved_at=task.approved_at,
        created_at=task.created_at,
        updated_at=task.updated_at,
        last_run=last_run_summary,
    )


@router.post("/projects", status_code=201)
def create_project(body: ProjectCreate, db: Session = Depends(get_db)) -> ProjectResponse:
    # Validate source_url requirement
    if body.source != Source.new_project and not body.source_url:
        _error("VALIDATION_ERROR", f"source_url is required for source '{body.source.value}'")

    # Check for duplicate name
    existing = project_service.get_project_by_name(db, body.name)
    if existing:
        _error(
            "PROJECT_NAME_CONFLICT",
            f"A project named '{body.name}' already exists.",
            {"existing_project_id": existing.id},
            409,
        )

    try:
        project = project_service.create_project(db, body.name, body.source, body.source_url)
    except IntegrityError:
        db.rollback()
        existing = project_service.get_project_by_name(db, body.name)
        _error(
            "PROJECT_NAME_CONFLICT",
            f"A project named '{body.name}' already exists.",
            {"existing_project_id": existing.id if existing else ""},
            409,
        )

    return ProjectResponse(
        id=project.id,
        name=project.name,
        source=project.source,
        source_url=project.source_url,
        workspace_id=project.workspace_id,
        owner_id=project.owner_id,
        created_at=project.created_at,
        updated_at=project.updated_at,
    )


@router.post("/projects/{project_id}/workspaces", status_code=201)
async def open_workspace(
    project_id: str,
    body: WorkspaceCreate,
    db: Session = Depends(get_db),
) -> WorkspaceResponse:
    project = project_service.get_project(db, project_id)
    if not project:
        _error("NOT_FOUND", "Project not found.", {}, 404)

    if project.workspace_id:
        _error("WORKSPACE_ALREADY_EXISTS", "Project already has an active workspace.", {}, 409)

    try:
        workspace = await workspace_service.open_workspace(
            db, project, settings.WORKSPACE_SAFE_ROOT, body.git_branch
        )
    except RuntimeError as e:
        _error("INTERNAL_ERROR", str(e), {}, 500)
    except Exception as e:
        logger.exception("Failed to open workspace")
        _error("INTERNAL_ERROR", f"Failed to open workspace: {e}", {}, 500)

    project_service.set_workspace(db, project, workspace.id)

    return WorkspaceResponse(
        id=workspace.id,
        project_id=workspace.project_id,
        path=workspace.path,
        git_remote=workspace.git_remote,
        git_branch=workspace.git_branch,
        created_at=workspace.created_at,
        last_accessed_at=workspace.last_accessed_at,
    )


@router.get("/projects/{project_id}/active-task")
def get_active_task(project_id: str, db: Session = Depends(get_db)) -> TaskResponse:
    project = project_service.get_project(db, project_id)
    if not project:
        _error("NOT_FOUND", "Project not found.", {}, 404)

    task = task_service.get_active_task(db, project_id)
    if not task:
        _error("NO_ACTIVE_TASK", "Project has no active task.", {}, 404)

    return _task_to_response(task, db)
