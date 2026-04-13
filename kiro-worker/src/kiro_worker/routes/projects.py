import logging
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from kiro_worker.db.engine import get_db
from kiro_worker.schemas.project import ProjectCreate, ProjectResponse, SourceUrlUpdate, AliasSet, AliasRemove
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


def _project_response(project, db: Session) -> ProjectResponse:
    aliases = project_service.get_aliases(db, project.id)
    return ProjectResponse(
        id=project.id,
        name=project.name,
        source=project.source,
        source_url=project.source_url,
        workspace_id=project.workspace_id,
        owner_id=project.owner_id,
        aliases=aliases,
        created_at=project.created_at,
        updated_at=project.updated_at,
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

    return _project_response(project, db)


@router.post("/projects/{project_id}/workspaces", status_code=201)
async def open_workspace(
    project_id: str,
    body: WorkspaceCreate,
    db: Session = Depends(get_db),
) -> WorkspaceResponse:
    project = project_service.get_project(db, project_id)
    if not project:
        _error("NOT_FOUND", "Project not found.", {}, 404)

    try:
        workspace, reuse_decision = await workspace_service.resolve_or_create_workspace(
            db, project, settings.WORKSPACE_SAFE_ROOT, body.git_branch
        )
    except RuntimeError as e:
        _error("INTERNAL_ERROR", str(e), {}, 500)
    except Exception as e:
        logger.exception("Failed to open workspace")
        _error("INTERNAL_ERROR", f"Failed to open workspace: {e}", {}, 500)

    return WorkspaceResponse(
        id=workspace.id,
        project_id=workspace.project_id,
        path=workspace.path,
        git_remote=workspace.git_remote,
        git_branch=workspace.git_branch,
        created_at=workspace.created_at,
        last_accessed_at=workspace.last_accessed_at,
        reuse_decision=reuse_decision,
    )


@router.get("/projects/{project_id}/workspace")
async def get_project_workspace(project_id: str, db: Session = Depends(get_db)) -> WorkspaceResponse:
    """
    Return the canonical workspace for a project.
    Resolves the best available workspace without creating a new one.
    Use this for PM visibility into which workspace continuity is active.
    """
    project = project_service.get_project(db, project_id)
    if not project:
        _error("NOT_FOUND", "Project not found.", {}, 404)

    workspace = workspace_service.get_canonical_workspace(db, project)
    if not workspace:
        _error("NOT_FOUND", "No valid workspace found for this project.", {}, 404)

    return WorkspaceResponse(
        id=workspace.id,
        project_id=workspace.project_id,
        path=workspace.path,
        git_remote=workspace.git_remote,
        git_branch=workspace.git_branch,
        created_at=workspace.created_at,
        last_accessed_at=workspace.last_accessed_at,
        reuse_decision="existing",
    )


@router.post("/projects/{project_id}/source-url")
def update_project_source_url(
    project_id: str,
    body: SourceUrlUpdate,
    db: Session = Depends(get_db),
):
    """
    Update a project's source_url in place.
    Preserves project identity and task history.
    Allowed for: local_folder, local_repo, github_repo.
    Not allowed for: new_project (managed path is derived from project name, not source_url).
    After updating, call POST /projects/{id}/workspace/reinitialize to repair workspace continuity.
    """
    project = project_service.get_project(db, project_id)
    if not project:
        _error("NOT_FOUND", "Project not found.", {}, 404)

    source = Source(project.source)

    # new_project does not use source_url — managed path is derived from project name
    if source == Source.new_project:
        _error(
            "SOURCE_UPDATE_NOT_SUPPORTED",
            "new_project workspaces are managed by the worker and do not use source_url. "
            "Use POST /projects/{id}/workspace/reinitialize to recreate the managed workspace.",
            {"source": project.source},
            400,
        )

    if not body.source_url or not body.source_url.strip():
        _error("VALIDATION_ERROR", "source_url cannot be empty.")

    old_source_url = project.source_url
    new_source_url = body.source_url.strip()

    # Validate existence for local sources
    path_exists: bool | None = None
    if source in (Source.local_folder, Source.local_repo):
        import os
        path_exists = os.path.exists(new_source_url)

    project = project_service.update_source_url(db, project, new_source_url)

    # Determine recommended next step
    if source in (Source.local_folder, Source.local_repo):
        if path_exists:
            next_step = "retry_recovery"
            next_step_message = "Path exists — run POST /projects/{id}/workspace/reinitialize to rebind the workspace."
        else:
            next_step = "path_not_found"
            next_step_message = f"Warning: path '{new_source_url}' does not exist on disk yet. Ensure it exists before running workspace recovery."
    else:
        next_step = "retry_recovery"
        next_step_message = "Run POST /projects/{id}/workspace/reinitialize to re-clone and rebind the workspace."

    return {
        "project_id": project.id,
        "project_name": project.name,
        "source": project.source,
        "old_source_url": old_source_url,
        "new_source_url": project.source_url,
        "path_exists": path_exists,
        "next_step": next_step,
        "message": next_step_message,
    }


@router.post("/projects/{project_id}/workspace/reinitialize")
async def reinitialize_project_workspace(
    project_id: str,
    db: Session = Depends(get_db),
):
    """
    Recover a project's canonical workspace when it is missing or invalid.
    - local_folder/local_repo: rebinds to source_url if path still exists; blocked if gone.
    - github_repo: re-clones into managed workspace path if needed.
    - new_project: recreates the managed directory under safe_root.
    Returns a structured recovery result with outcome, workspace details, and PM message.
    """
    project = project_service.get_project(db, project_id)
    if not project:
        _error("NOT_FOUND", "Project not found.", {}, 404)

    try:
        result = await workspace_service.reinitialize_workspace(
            db, project, settings.WORKSPACE_SAFE_ROOT
        )
    except Exception as e:
        logger.exception("Workspace reinitialize failed")
        _error("INTERNAL_ERROR", f"Recovery failed: {e}", {}, 500)

    return {
        "project_id": project.id,
        "project_name": project.name,
        "source": project.source,
        **result,
    }


@router.post("/projects/{project_id}/aliases", status_code=200)
def set_project_alias(project_id: str, body: AliasSet, db: Session = Depends(get_db)):
    """
    Add a friendly alias to a project.
    Aliases are case-insensitive and globally unique.
    Returns the updated alias list, or a conflict error if the alias is taken by another project.
    """
    project = project_service.get_project(db, project_id)
    if not project:
        _error("NOT_FOUND", "Project not found.", {}, 404)

    try:
        updated_aliases, conflict_pid = project_service.set_alias(db, project_id, body.alias)
    except ValueError as e:
        _error("VALIDATION_ERROR", str(e))

    if conflict_pid:
        conflict = project_service.get_project(db, conflict_pid)
        _error(
            "ALIAS_CONFLICT",
            f"Alias '{body.alias.strip().lower()}' is already assigned to project '{conflict.name if conflict else conflict_pid}'.",
            {"conflict_project_id": conflict_pid, "conflict_project_name": conflict.name if conflict else None},
            409,
        )

    return {
        "project_id": project_id,
        "project_name": project.name,
        "aliases": updated_aliases,
        "message": f"Alias '{body.alias.strip().lower()}' added.",
    }


@router.delete("/projects/{project_id}/aliases")
def remove_project_alias(project_id: str, body: AliasRemove, db: Session = Depends(get_db)):
    """Remove an alias from a project. No-op if alias does not exist."""
    project = project_service.get_project(db, project_id)
    if not project:
        _error("NOT_FOUND", "Project not found.", {}, 404)

    updated_aliases = project_service.remove_alias(db, project_id, body.alias)
    return {
        "project_id": project_id,
        "project_name": project.name,
        "aliases": updated_aliases,
        "message": f"Alias '{body.alias.strip().lower()}' removed.",
    }


@router.get("/projects/resolve")
def resolve_project(query: str = Query(..., description="Project id, canonical name, or alias"), db: Session = Depends(get_db)):
    """
    Resolve a project by id, canonical name, or alias.
    Returns the project with match_type indicating how it was found.
    """
    project, match_type = project_service.resolve_project(db, query)
    if not project:
        _error("NOT_FOUND", f"No project found matching '{query}'.", {"query": query}, 404)

    aliases = project_service.get_aliases(db, project.id)
    return {
        "project_id": project.id,
        "project_name": project.name,
        "source": project.source,
        "source_url": project.source_url,
        "workspace_id": project.workspace_id,
        "aliases": aliases,
        "match_type": match_type,
        "query": query,
    }


@router.get("/projects/{project_id}/active-task")
def get_active_task(project_id: str, db: Session = Depends(get_db)) -> TaskResponse:
    project = project_service.get_project(db, project_id)
    if not project:
        _error("NOT_FOUND", "Project not found.", {}, 404)

    task = task_service.get_active_task(db, project_id)
    if not task:
        _error("NO_ACTIVE_TASK", "Project has no active task.", {}, 404)

    return _task_to_response(task, db)
