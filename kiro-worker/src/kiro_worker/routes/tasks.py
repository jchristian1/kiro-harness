import json
import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from kiro_worker.db.engine import get_db
from kiro_worker.schemas.task import TaskCreate, TaskResponse, ReviseRequest
from kiro_worker.schemas.run import RunCreate, RunSummary, RunCreateResponse, RunListResponse, RunListItem
from kiro_worker.services import project_service, workspace_service, task_service, run_service
from kiro_worker.adapters.kiro_adapter import invoke_kiro
from kiro_worker.domain.enums import TaskStatus, RunMode, Operation
from kiro_worker.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()

SKILL_MAP = {
    RunMode.analyze: "analysis-workflow",
    RunMode.implement: "implementation-workflow",
    RunMode.validate: "validation-workflow",
}

ARTIFACT_TYPE_MAP = {
    RunMode.analyze: "analysis",
    RunMode.implement: "implementation",
    RunMode.validate: "validation",
}


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


def _determine_next_status_after_run(task, mode: RunMode, parsed_output: dict) -> TaskStatus:
    """Determine the next task status based on run mode and Kiro output."""
    rns = parsed_output.get("recommended_next_step", "")
    operation = Operation(task.operation)

    if mode == RunMode.analyze:
        if rns == "no_action_needed":
            return TaskStatus.done
        if operation == Operation.implement_now:
            return TaskStatus.implementing
        if operation == Operation.plan_only:
            return TaskStatus.done
        # analyze_then_approve or implement_and_prepare_pr
        return TaskStatus.awaiting_approval

    elif mode == RunMode.implement:
        if rns in ("run_validation",):
            return TaskStatus.validating
        # request_review or needs_follow_up
        return TaskStatus.awaiting_revision

    elif mode == RunMode.validate:
        passed = parsed_output.get("passed", False)
        if passed:
            return TaskStatus.done
        return TaskStatus.awaiting_revision

    return TaskStatus.failed


async def _execute_run(
    db: Session,
    task,
    mode: RunMode,
    workspace_path: str,
    context: dict,
) -> tuple:
    """Execute a Kiro run and update DB. Returns (run, task)."""
    skill = SKILL_MAP[mode]
    artifact_type = ARTIFACT_TYPE_MAP[mode]

    run = run_service.create_run(
        db,
        task_id=task.id,
        mode=mode.value,
        agent=settings.KIRO_DEFAULT_AGENT,
        skill=skill,
        context_snapshot=context,
    )

    result = await invoke_kiro(
        agent=settings.KIRO_DEFAULT_AGENT,
        workspace_path=workspace_path,
        skill=skill,
        context=context,
        timeout=settings.KIRO_CLI_TIMEOUT,
    )

    if result.parse_status == "ok" and result.parsed_output:
        run = run_service.complete_run(
            db, run,
            raw_output=result.stdout,
            parse_status="ok",
            failure_reason=None,
        )
        run_service.create_artifact(
            db,
            run_id=run.id,
            task_id=task.id,
            artifact_type=artifact_type,
            schema_version=result.parsed_output.get("schema_version", "1"),
            content=result.parsed_output,
        )
        next_status = _determine_next_status_after_run(task, mode, result.parsed_output)
        task = task_service.transition_task(db, task, next_status)
    else:
        ps = result.parse_status if result.parse_status else "parse_failed"
        run = run_service.fail_run(
            db, run,
            raw_output=result.stdout or None,
            failure_reason=result.failure_reason or "unknown failure",
            parse_status=ps if ps != "parse_failed" or result.exit_code == 0 else None,
        )
        task = task_service.transition_task(db, task, TaskStatus.failed)

    return run, task


@router.post("/tasks", status_code=201)
def create_task(body: TaskCreate, db: Session = Depends(get_db)) -> TaskResponse:
    project = project_service.get_project(db, body.project_id)
    if not project:
        _error("NOT_FOUND", "Project not found.", {}, 404)
    if not project.workspace_id:
        _error("NOT_FOUND", "Project has no active workspace.", {}, 404)

    workspace = workspace_service.get_workspace(db, project.workspace_id)
    if not workspace:
        _error("NOT_FOUND", "Workspace not found.", {}, 404)

    task = task_service.create_task(
        db,
        project_id=project.id,
        workspace_id=workspace.id,
        intent=body.intent,
        source=body.source,
        operation=body.operation,
        description=body.description,
    )
    return _task_to_response(task, db)


@router.get("/tasks/{task_id}")
def get_task(task_id: str, db: Session = Depends(get_db)) -> TaskResponse:
    task = task_service.get_task(db, task_id)
    if not task:
        _error("NOT_FOUND", "Task not found.", {}, 404)
    return _task_to_response(task, db)


@router.post("/tasks/{task_id}/approve")
async def approve_task(task_id: str, db: Session = Depends(get_db)) -> TaskResponse:
    task = task_service.get_task(db, task_id)
    if not task:
        _error("NOT_FOUND", "Task not found.", {}, 404)

    if TaskStatus(task.status) != TaskStatus.awaiting_approval:
        _error(
            "INVALID_STATE_FOR_APPROVAL",
            "Task is not in awaiting_approval state.",
            {"current_status": task.status},
            409,
        )

    workspace = workspace_service.get_workspace(db, task.workspace_id)
    if not workspace:
        _error("NOT_FOUND", "Workspace not found.", {}, 404)

    task = task_service.approve_task(db, task)
    context = task_service.build_resume_context(db, task, workspace.path)

    _, task = await _execute_run(db, task, RunMode.implement, workspace.path, context)
    return _task_to_response(task, db)


@router.post("/tasks/{task_id}/runs", status_code=201)
async def trigger_run(task_id: str, body: RunCreate, db: Session = Depends(get_db)):
    task = task_service.get_task(db, task_id)
    if not task:
        _error("NOT_FOUND", "Task not found.", {}, 404)

    current = TaskStatus(task.status)
    mode = body.mode

    # Reject if awaiting_approval
    if current == TaskStatus.awaiting_approval:
        _error(
            "APPROVAL_REQUIRED",
            "Task is awaiting approval. Call POST /tasks/{id}/approve before triggering a run.",
            {"current_status": task.status, "approve_endpoint": f"/tasks/{task_id}/approve"},
            409,
        )

    # Validate allowed states
    allowed_states = {TaskStatus.created, TaskStatus.failed}
    if current not in allowed_states:
        _error(
            "INVALID_STATE_TRANSITION",
            f"Cannot trigger a run from state '{task.status}'.",
            {"current_status": task.status},
            409,
        )

    workspace = workspace_service.get_workspace(db, task.workspace_id)
    if not workspace:
        _error("NOT_FOUND", "Workspace not found.", {}, 404)

    # Transition created → opening
    if current == TaskStatus.created:
        task = task_service.transition_task(db, task, TaskStatus.opening)

    # Transition opening → analyzing or implementing
    if TaskStatus(task.status) == TaskStatus.opening:
        if mode == RunMode.analyze:
            task = task_service.transition_task(db, task, TaskStatus.analyzing)
        elif mode == RunMode.implement:
            task = task_service.transition_task(db, task, TaskStatus.implementing)
        else:
            task = task_service.transition_task(db, task, TaskStatus.analyzing)
    elif TaskStatus(task.status) == TaskStatus.failed:
        # Retry: transition to appropriate state
        if mode == RunMode.analyze:
            task = task_service.transition_task(db, task, TaskStatus.analyzing)
        elif mode == RunMode.implement:
            task = task_service.transition_task(db, task, TaskStatus.implementing)
        elif mode == RunMode.validate:
            task = task_service.transition_task(db, task, TaskStatus.validating)

    context = task_service.build_resume_context(db, task, workspace.path)
    run, task = await _execute_run(db, task, mode, workspace.path, context)

    return RunCreateResponse(
        id=run.id,
        task_id=run.task_id,
        mode=run.mode,
        status=run.status,
        agent=run.agent,
        skill=run.skill,
        started_at=run.started_at,
        completed_at=run.completed_at,
    )


@router.get("/tasks/{task_id}/runs")
def list_runs(task_id: str, db: Session = Depends(get_db)) -> RunListResponse:
    task = task_service.get_task(db, task_id)
    if not task:
        _error("NOT_FOUND", "Task not found.", {}, 404)

    runs = run_service.get_runs_for_task(db, task_id)
    items = [
        RunListItem(
            id=r.id,
            task_id=r.task_id,
            mode=r.mode,
            status=r.status,
            agent=r.agent,
            skill=r.skill,
            parse_status=r.parse_status,
            failure_reason=r.failure_reason,
            started_at=r.started_at,
            completed_at=r.completed_at,
        )
        for r in runs
    ]
    return RunListResponse(runs=items)


@router.post("/tasks/{task_id}/revise")
async def revise_task(task_id: str, body: ReviseRequest, db: Session = Depends(get_db)) -> TaskResponse:
    if not body.instructions or not body.instructions.strip():
        _error("VALIDATION_ERROR", "instructions is required and cannot be empty.")

    task = task_service.get_task(db, task_id)
    if not task:
        _error("NOT_FOUND", "Task not found.", {}, 404)

    if TaskStatus(task.status) != TaskStatus.awaiting_revision:
        _error(
            "INVALID_STATE_TRANSITION",
            "Task is not in awaiting_revision state.",
            {"current_status": task.status},
            409,
        )

    workspace = workspace_service.get_workspace(db, task.workspace_id)
    if not workspace:
        _error("NOT_FOUND", "Workspace not found.", {}, 404)

    task = task_service.revise_task(db, task)
    context = task_service.build_resume_context(db, task, workspace.path, revision_instructions=body.instructions)

    _, task = await _execute_run(db, task, RunMode.implement, workspace.path, context)
    return _task_to_response(task, db)
