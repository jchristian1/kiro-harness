import json
import logging
import asyncio
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import Optional

from kiro_worker.db.engine import get_db
from kiro_worker.schemas.task import TaskCreate, TaskResponse, ReviseRequest
from kiro_worker.schemas.run import RunCreate, RunSummary, RunCreateResponse, RunListResponse, RunListItem
from kiro_worker.services import project_service, workspace_service, task_service, run_service
from kiro_worker.adapters.kiro_adapter import invoke_kiro
from kiro_worker.domain.enums import TaskStatus, RunMode, Operation
from kiro_worker.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()

# Process registry: run_id → asyncio.subprocess.Process
# Used by the cancel endpoint to kill active kiro-cli subprocesses
_active_processes: dict[str, asyncio.subprocess.Process] = {}

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
            progress_message=last_run.progress_message,
            last_activity_at=last_run.last_activity_at,
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
    """
    Determine the next task status based on run mode and Kiro output.

    Architecture model:
    - A task represents one bounded specialist execution unit.
    - A completed specialist run returns control to the Project Lead / Project Manager.
    - The Project Lead handles the user-facing conversation and creates a NEW task
      for the next bounded run (implement, deploy, test, etc.).
    - Only real in-run blockers (risky actions, missing clarification) keep a task waiting.
    - awaiting_approval is NOT used for normal post-analysis continuation.
      It is reserved for explicit action-level blockers inside a run.

    Analyze run outcomes:
      no_action_needed       -> done  (nothing to do)
      request_clarification  -> awaiting_revision  (Kiro needs more input before proceeding)
      approve_and_implement  + implement_now -> implementing  (immediate, no gate)
      approve_and_implement  + any other operation -> done  (Project Lead creates next task)

    Implement run outcomes:
      run_validation         -> validating
      request_review / needs_follow_up -> awaiting_revision

    Validate run outcomes:
      passed=True            -> done
      passed=False           -> awaiting_revision
    """
    rns = parsed_output.get("recommended_next_step", "")
    operation = Operation(task.operation)

    if mode == RunMode.analyze:
        # Kiro says nothing to do
        if rns == "no_action_needed":
            return TaskStatus.done

        # Kiro needs clarification before it can proceed
        if rns == "request_clarification":
            return TaskStatus.awaiting_revision

        # rns == "approve_and_implement" — Kiro finished analysis cleanly
        if operation == Operation.implement_now:
            # Caller explicitly requested immediate implementation — no gate
            return TaskStatus.implementing

        # All other operations (plan_only, analyze_then_approve, implement_and_prepare_pr):
        # Analysis is done. Project Lead reads the artifact and creates the next task.
        return TaskStatus.done

    elif mode == RunMode.implement:
        if rns == "run_validation":
            return TaskStatus.validating
        # request_review or needs_follow_up — Project Lead reviews before next step
        return TaskStatus.awaiting_revision

    elif mode == RunMode.validate:
        passed = parsed_output.get("passed", False)
        if passed:
            return TaskStatus.done
        return TaskStatus.awaiting_revision

    return TaskStatus.failed


def _make_progress_callback(db: Session, run):
    """Return a proper async callback for progress updates during streaming."""
    async def on_progress(msg: str, partial: str) -> None:
        run_service.update_progress(db, run, msg, partial)
    return on_progress


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
        on_progress=_make_progress_callback(db, run),
        on_process=lambda proc: _active_processes.__setitem__(run.id, proc),
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
async def create_task(body: TaskCreate, db: Session = Depends(get_db)):
    project = project_service.get_project(db, body.project_id)
    if not project:
        _error("NOT_FOUND", "Project not found.", {}, 404)

    # Resolve or create workspace — reuses existing if valid, creates only if needed
    try:
        workspace, reuse_decision = await workspace_service.resolve_or_create_workspace(
            db, project, settings.WORKSPACE_SAFE_ROOT
        )
    except RuntimeError as e:
        _error("INTERNAL_ERROR", str(e), {}, 500)

    task = task_service.create_task(
        db,
        project_id=project.id,
        workspace_id=workspace.id,
        intent=body.intent,
        source=body.source,
        operation=body.operation,
        description=body.description,
    )
    response = _task_to_response(task, db)
    # Attach workspace continuity info for PM visibility
    response_dict = response.model_dump()
    response_dict["workspace_reuse"] = reuse_decision
    response_dict["workspace_path"] = workspace.path
    return response_dict


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


@router.post("/tasks/{task_id}/runs/start", status_code=202)
async def start_run_async(task_id: str, body: RunCreate, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """
    Start a run in the background and return immediately with task_id, run_id, and status=running.
    The run executes asynchronously. Use GET /tasks/{id} to poll progress.
    This is the non-blocking variant of POST /tasks/{id}/runs.
    """
    task = task_service.get_task(db, task_id)
    if not task:
        _error("NOT_FOUND", "Task not found.", {}, 404)

    current = TaskStatus(task.status)
    mode = body.mode

    if current == TaskStatus.awaiting_approval:
        _error("APPROVAL_REQUIRED", "Task is awaiting approval.", {"current_status": task.status}, 409)

    allowed_states = {TaskStatus.created, TaskStatus.failed}
    if current not in allowed_states:
        _error("INVALID_STATE_TRANSITION", f"Cannot trigger a run from state '{task.status}'.", {"current_status": task.status}, 409)

    workspace = workspace_service.get_workspace(db, task.workspace_id)
    if not workspace:
        _error("NOT_FOUND", "Workspace not found.", {}, 404)

    # Transition to in-progress state synchronously before returning
    if current == TaskStatus.created:
        task = task_service.transition_task(db, task, TaskStatus.opening)
    if TaskStatus(task.status) == TaskStatus.opening:
        if mode == RunMode.implement:
            task = task_service.transition_task(db, task, TaskStatus.implementing)
        elif mode == RunMode.analyze:
            task = task_service.transition_task(db, task, TaskStatus.analyzing)
        else:
            task = task_service.transition_task(db, task, TaskStatus.analyzing)
    elif TaskStatus(task.status) == TaskStatus.failed:
        if mode == RunMode.implement:
            task = task_service.transition_task(db, task, TaskStatus.implementing)
        elif mode == RunMode.analyze:
            task = task_service.transition_task(db, task, TaskStatus.analyzing)
        elif mode == RunMode.validate:
            task = task_service.transition_task(db, task, TaskStatus.validating)

    # Create the run record synchronously so we can return the run_id immediately
    skill = SKILL_MAP[mode]
    context = task_service.build_resume_context(db, task, workspace.path)
    run = run_service.create_run(
        db,
        task_id=task.id,
        mode=mode.value,
        agent=settings.KIRO_DEFAULT_AGENT,
        skill=skill,
        context_snapshot=context,
    )

    # Fire the actual kiro invocation as a background task
    async def _run_in_background():
        from kiro_worker.db.engine import SessionLocal
        bg_db = SessionLocal()
        try:
            bg_run = run_service.get_run(bg_db, run.id)
            bg_task = task_service.get_task(bg_db, task.id)
            bg_workspace = workspace_service.get_workspace(bg_db, bg_task.workspace_id)
            bg_context = task_service.build_resume_context(bg_db, bg_task, bg_workspace.path)
            await _execute_run_from_existing(bg_db, bg_task, bg_run, mode, bg_workspace.path, bg_context)
        except Exception as e:
            logger.exception(f"Background run failed for run {run.id}: {e}")
        finally:
            bg_db.close()

    background_tasks.add_task(_run_in_background)

    mode_labels = {
        RunMode.analyze: "Analysis",
        RunMode.implement: "Implementation",
        RunMode.validate: "Validation",
    }
    mode_label = mode_labels.get(mode, "Run")
    active_status = task.status

    return {
        "task_id": task.id,
        "run_id": run.id,
        "task_status": active_status,
        "run_status": "running",
        "message": f"{mode_label} started. Use kw_task_status to check progress.",
    }


async def _execute_run_from_existing(db: Session, task, run, mode: RunMode, workspace_path: str, context: dict):
    """Execute a Kiro run from an already-created run record."""
    skill = SKILL_MAP[mode]
    artifact_type = ARTIFACT_TYPE_MAP[mode]

    result = await invoke_kiro(
        agent=settings.KIRO_DEFAULT_AGENT,
        workspace_path=workspace_path,
        skill=skill,
        context=context,
        timeout=settings.KIRO_CLI_TIMEOUT,
        on_progress=_make_progress_callback(db, run),
        on_process=lambda proc: _active_processes.__setitem__(run.id, proc),
    )

    if result.parse_status == "ok" and result.parsed_output:
        run_service.complete_run(db, run, raw_output=result.stdout, parse_status="ok", failure_reason=None)
        run_service.create_artifact(
            db, run_id=run.id, task_id=task.id,
            artifact_type=artifact_type,
            schema_version=result.parsed_output.get("schema_version", "1"),
            content=result.parsed_output,
        )
        next_status = _determine_next_status_after_run(task, mode, result.parsed_output)
        task_service.transition_task(db, task, next_status)
    else:
        ps = result.parse_status if result.parse_status else "parse_failed"
        run_service.fail_run(
            db, run,
            raw_output=result.stdout or None,
            failure_reason=result.failure_reason or "unknown failure",
            parse_status=ps if ps != "parse_failed" or result.exit_code == 0 else None,
        )
        task_service.transition_task(db, task, TaskStatus.failed)
    # Clean up process registry
    _active_processes.pop(run.id, None)


@router.post("/tasks/{task_id}/cancel")
async def cancel_task(task_id: str, db: Session = Depends(get_db)):
    """
    Cancel an active specialist run for a task.
    Kills the kiro-cli subprocess if still running, marks the run as cancelled,
    and transitions the task to awaiting_revision so it can be retried or closed.
    """
    task = task_service.get_task(db, task_id)
    if not task:
        _error("NOT_FOUND", "Task not found.", {}, 404)

    current = TaskStatus(task.status)
    cancellable_states = {
        TaskStatus.opening,
        TaskStatus.analyzing,
        TaskStatus.implementing,
        TaskStatus.validating,
    }
    if current not in cancellable_states:
        _error(
            "INVALID_STATE_TRANSITION",
            f"Task cannot be cancelled from state '{task.status}'. Cancellable states: opening, analyzing, implementing, validating.",
            {"current_status": task.status},
            409,
        )

    # Get the active run
    last_run = run_service.get_last_run(db, task_id)
    if not last_run or last_run.status != "running":
        _error(
            "NO_ACTIVE_RUN",
            "Task has no active run to cancel.",
            {"current_status": task.status, "last_run_status": last_run.status if last_run else None},
            409,
        )

    prev_task_status = task.status
    prev_run_status = last_run.status

    # Kill the subprocess if it is still active
    proc = _active_processes.pop(last_run.id, None)
    if proc is not None:
        try:
            proc.kill()
            logger.info(f"Killed kiro-cli process for run {last_run.id}")
        except ProcessLookupError:
            pass  # Process already exited
        except Exception as e:
            logger.warning(f"Failed to kill process for run {last_run.id}: {e}")

    # Mark run as cancelled
    reason = f"Cancelled by Project Manager from state '{prev_task_status}'"
    run_service.cancel_run(db, last_run, reason=reason)

    # Transition task to awaiting_revision
    task = task_service.transition_task(db, task, TaskStatus.awaiting_revision)

    return {
        "task_id": task_id,
        "run_id": last_run.id,
        "previous_task_status": prev_task_status,
        "previous_run_status": prev_run_status,
        "new_task_status": task.status,
        "new_run_status": "cancelled",
        "message": "Task cancelled. Use kw_task_status to check status, or kw_complete_task to close it.",
    }


@router.post("/tasks/{task_id}/close")
def close_task(task_id: str, db: Session = Depends(get_db)) -> TaskResponse:
    """
    Close a task that is stuck in validating or awaiting_revision.
    Used by the Project Lead when validation is not needed or not possible.
    Transitions the task directly to done.
    """
    task = task_service.get_task(db, task_id)
    if not task:
        _error("NOT_FOUND", "Task not found.", {}, 404)

    current = TaskStatus(task.status)
    closeable = {TaskStatus.validating, TaskStatus.awaiting_revision, TaskStatus.failed}
    if current not in closeable:
        _error(
            "INVALID_STATE_TRANSITION",
            f"Task cannot be closed from state '{task.status}'. Closeable states: validating, awaiting_revision, failed.",
            {"current_status": task.status},
            409,
        )

    task = task_service.transition_task(db, task, TaskStatus.done)
    return _task_to_response(task, db)


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
