import asyncio
import os
from datetime import datetime, timezone
from pathlib import Path
from sqlalchemy.orm import Session
from ulid import ULID

from kiro_worker.db.models import Workspace, Project
from kiro_worker.domain.enums import Source


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id(prefix: str) -> str:
    return f"{prefix}{ULID()}"


def validate_workspace_path(path: str, safe_root: str) -> bool:
    """
    Return True if path is safe to use as a workspace.
    Rejects paths with .. traversal or symlinks that escape safe_root.
    Note: local_repo and local_folder may be outside safe_root (they are opened in-place).
    This function validates that a *managed* path (new_project, github_repo) is within safe_root.
    """
    try:
        resolved = Path(path).resolve()
        safe = Path(safe_root).resolve()
        # Check for .. in the original path
        if ".." in Path(path).parts:
            return False
        # Check symlink escape
        if resolved != Path(path).resolve():
            # Path was a symlink; check if resolved is still under safe_root
            pass
        return str(resolved).startswith(str(safe))
    except Exception:
        return False


def validate_external_path(path: str) -> bool:
    """Validate that an external (local_repo / local_folder) path exists."""
    return os.path.exists(path)


def _check_path_traversal(path: str) -> bool:
    """Return True if path contains .. traversal."""
    return ".." in Path(path).parts


async def _run_subprocess(cmd: list[str], cwd: str | None = None) -> tuple[int, str, str]:
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=cwd,
    )
    stdout, stderr = await proc.communicate()
    return proc.returncode or 0, stdout.decode(), stderr.decode()


async def open_workspace(
    db: Session,
    project: Project,
    safe_root: str,
    git_branch: str | None = None,
) -> Workspace:
    """
    Open or create a workspace for the project based on its source mode.
    Returns the Workspace record.
    """
    source = Source(project.source)
    now = _now()
    ws_id = _new_id("ws_")
    git_remote: str | None = None
    git_branch_actual: str | None = None

    if source == Source.new_project:
        ws_path = os.path.join(safe_root, project.name)
        os.makedirs(ws_path, exist_ok=True)

    elif source == Source.github_repo:
        ws_path = os.path.join(safe_root, project.name)
        if not os.path.exists(ws_path):
            clone_cmd = ["git", "clone", project.source_url, ws_path]
            rc, _, stderr = await _run_subprocess(clone_cmd)
            if rc != 0:
                raise RuntimeError(f"git clone failed: {stderr.strip()}")
        if git_branch:
            await _run_subprocess(["git", "checkout", git_branch], cwd=ws_path)
        # Capture git metadata
        _, remote_out, _ = await _run_subprocess(["git", "remote", "get-url", "origin"], cwd=ws_path)
        git_remote = remote_out.strip() or None
        _, branch_out, _ = await _run_subprocess(["git", "branch", "--show-current"], cwd=ws_path)
        git_branch_actual = branch_out.strip() or None

    elif source == Source.local_repo:
        ws_path = project.source_url  # use in-place
        if not os.path.exists(ws_path):
            raise RuntimeError(f"workspace_path_not_found: {ws_path}")
        # Capture git metadata
        _, remote_out, _ = await _run_subprocess(["git", "remote", "get-url", "origin"], cwd=ws_path)
        git_remote = remote_out.strip() or None
        _, branch_out, _ = await _run_subprocess(["git", "branch", "--show-current"], cwd=ws_path)
        git_branch_actual = branch_out.strip() or None

    elif source == Source.local_folder:
        ws_path = project.source_url  # use in-place
        if not os.path.exists(ws_path):
            raise RuntimeError(f"workspace_path_not_found: {ws_path}")

    else:
        raise ValueError(f"Unknown source: {source}")

    workspace = Workspace(
        id=ws_id,
        project_id=project.id,
        path=ws_path,
        git_remote=git_remote,
        git_branch=git_branch_actual,
        created_at=now,
        last_accessed_at=now,
    )
    db.add(workspace)
    db.commit()
    db.refresh(workspace)
    return workspace


def get_workspace(db: Session, workspace_id: str) -> Workspace | None:
    return db.query(Workspace).filter(Workspace.id == workspace_id).first()


def get_workspace_by_project(db: Session, project_id: str) -> Workspace | None:
    """Return the most recently created workspace for a project."""
    return (
        db.query(Workspace)
        .filter(Workspace.project_id == project_id)
        .order_by(Workspace.created_at.desc())
        .first()
    )


def get_canonical_workspace(db: Session, project: Project) -> Workspace | None:
    """
    Return the canonical (most recently accessed) workspace for a project.
    Prefers the workspace referenced by project.workspace_id if it exists and is valid.
    Falls back to the most recently accessed workspace for the project.
    """
    # Prefer the project's pinned workspace
    if project.workspace_id:
        ws = db.query(Workspace).filter(Workspace.id == project.workspace_id).first()
        if ws and os.path.exists(ws.path):
            return ws

    # Fall back to most recently accessed workspace with a valid path
    candidates = (
        db.query(Workspace)
        .filter(Workspace.project_id == project.id)
        .order_by(Workspace.last_accessed_at.desc())
        .all()
    )
    for ws in candidates:
        if os.path.exists(ws.path):
            return ws

    return None


async def resolve_or_create_workspace(
    db: Session,
    project: Project,
    safe_root: str,
    git_branch: str | None = None,
) -> tuple["Workspace", str]:
    """
    Return (workspace, reuse_decision) where reuse_decision is 'reused' or 'created'.

    Reuses the canonical workspace if it exists and the path is valid on disk.
    Creates a new workspace only when no valid workspace exists.
    Uses _get_or_create_workspace_for_path to prevent duplicate path records.
    Updates project.workspace_id and touches last_accessed_at on reuse.
    """
    existing = get_canonical_workspace(db, project)
    if existing:
        touch_workspace(db, existing)
        # Re-pin project to this workspace if it drifted
        if project.workspace_id != existing.id:
            from kiro_worker.services.project_service import set_workspace
            set_workspace(db, project, existing.id)
        return existing, "reused"

    # No valid workspace — determine the target path and use duplicate-safe creation
    source = Source(project.source)
    git_remote: str | None = None
    git_branch_actual: str | None = None

    if source == Source.new_project:
        ws_path = os.path.join(safe_root, project.name)
        os.makedirs(ws_path, exist_ok=True)

    elif source == Source.github_repo:
        ws_path = os.path.join(safe_root, project.name)
        if not os.path.exists(ws_path):
            rc, _, stderr = await _run_subprocess(["git", "clone", project.source_url, ws_path])
            if rc != 0:
                raise RuntimeError(f"git clone failed: {stderr.strip()}")
        if git_branch:
            await _run_subprocess(["git", "checkout", git_branch], cwd=ws_path)
        _, remote_out, _ = await _run_subprocess(["git", "remote", "get-url", "origin"], cwd=ws_path)
        git_remote = remote_out.strip() or None
        _, branch_out, _ = await _run_subprocess(["git", "branch", "--show-current"], cwd=ws_path)
        git_branch_actual = branch_out.strip() or None

    elif source == Source.local_repo:
        ws_path = project.source_url
        if not os.path.exists(ws_path):
            raise RuntimeError(f"workspace_path_not_found: {ws_path}")
        _, remote_out, _ = await _run_subprocess(["git", "remote", "get-url", "origin"], cwd=ws_path)
        git_remote = remote_out.strip() or None
        _, branch_out, _ = await _run_subprocess(["git", "branch", "--show-current"], cwd=ws_path)
        git_branch_actual = branch_out.strip() or None

    elif source == Source.local_folder:
        ws_path = project.source_url
        if not os.path.exists(ws_path):
            raise RuntimeError(f"workspace_path_not_found: {ws_path}")

    else:
        raise ValueError(f"Unknown source: {source}")

    workspace, _, _ = _get_or_create_workspace_for_path(db, project, ws_path, git_remote, git_branch_actual)
    return workspace, "created"


def touch_workspace(db: Session, workspace: Workspace) -> None:
    workspace.last_accessed_at = _now()
    db.commit()


def get_workspace_for_path(db: Session, path: str) -> Workspace | None:
    """
    Return any existing workspace record with this exact path, regardless of project.
    Used to prevent duplicate path records during rebound/recovery.
    """
    return db.query(Workspace).filter(Workspace.path == path).first()


def _get_or_create_workspace_for_path(
    db: Session,
    project: Project,
    path: str,
    git_remote: str | None = None,
    git_branch: str | None = None,
) -> tuple[Workspace, str, str | None]:
    """
    Return (workspace, decision, previous_project_id) where:
      decision: 'reused_existing' | 'created'
      previous_project_id: the project_id the workspace previously belonged to,
                           or None if it already belonged to this project or was just created.

    Policy: cross-project path reuse is ALLOWED but surfaced explicitly.
    If a workspace record already exists for this path (any project), reuse it and re-pin
    it to this project. The caller receives previous_project_id so it can include a
    shared_path_warning in the PM-facing response.
    Only creates a new record when no record exists for the path.
    """
    from kiro_worker.services.project_service import set_workspace

    existing = get_workspace_for_path(db, path)
    if existing:
        previous_project_id = existing.project_id if existing.project_id != project.id else None
        # Re-pin to this project
        if existing.project_id != project.id:
            existing.project_id = project.id
            db.commit()
        touch_workspace(db, existing)
        set_workspace(db, project, existing.id)
        return existing, "reused_existing", previous_project_id

    now = _now()
    ws = Workspace(
        id=_new_id("ws_"),
        project_id=project.id,
        path=path,
        git_remote=git_remote,
        git_branch=git_branch,
        created_at=now,
        last_accessed_at=now,
    )
    db.add(ws)
    db.commit()
    db.refresh(ws)
    set_workspace(db, project, ws.id)
    return ws, "created", None


async def reinitialize_workspace(
    db: Session,
    project: Project,
    safe_root: str,
    git_branch: str | None = None,
) -> dict:
    """
    Recover a project's canonical workspace.

    Returns a dict with:
      outcome: 'already_healthy' | 'rebound' | 'rebound_reused' | 'recreated' | 'blocked'
      workspace_id, workspace_path, previous_workspace_id, reason, message

    Source-specific behaviour:
      local_folder / local_repo:
        - If source_url path exists on disk → get_or_create workspace record (duplicate-safe).
        - If source_url path is gone → blocked.
      github_repo:
        - Re-clone into safe_root if the managed path is gone.
        - If already present on disk, rebind (duplicate-safe).
      new_project:
        - Recreate the managed directory under safe_root (duplicate-safe).
    """
    source = Source(project.source)
    previous_ws_id = project.workspace_id

    # 1. Check if already healthy — no action needed
    existing = get_canonical_workspace(db, project)
    if existing:
        touch_workspace(db, existing)
        return {
            "outcome": "already_healthy",
            "workspace_id": existing.id,
            "workspace_path": existing.path,
            "previous_workspace_id": previous_ws_id,
            "shared_path_warning": None,
            "reason": "Canonical workspace is valid and accessible",
            "message": "Project workspace is already healthy — no recovery needed.",
        }

    # 2. Source-specific recovery

    if source in (Source.local_folder, Source.local_repo):
        if not project.source_url or not os.path.exists(project.source_url):
            return {
                "outcome": "blocked",
                "workspace_id": None,
                "workspace_path": project.source_url,
                "previous_workspace_id": previous_ws_id,
                "shared_path_warning": None,
                "reason": f"source_url path does not exist on disk: {project.source_url!r}",
                "message": (
                    "Cannot recover workspace automatically. "
                    "The original source path is gone. "
                    "Update the project source_url or re-create the project."
                ),
            }
        # Path exists — get or create workspace record (duplicate-safe)
        git_remote: str | None = None
        git_branch_actual: str | None = None
        if source == Source.local_repo:
            try:
                _, remote_out, _ = await _run_subprocess(
                    ["git", "remote", "get-url", "origin"], cwd=project.source_url
                )
                git_remote = remote_out.strip() or None
                _, branch_out, _ = await _run_subprocess(
                    ["git", "branch", "--show-current"], cwd=project.source_url
                )
                git_branch_actual = branch_out.strip() or None
            except Exception:
                pass

        ws, ws_decision, prev_proj = _get_or_create_workspace_for_path(
            db, project, project.source_url, git_remote, git_branch_actual
        )
        outcome = "rebound" if ws_decision == "created" else "rebound_reused"
        shared_path_warning = (
            f"This workspace path was previously associated with project {prev_proj}. "
            "Both projects now share the same workspace path. Review if this is intended."
            if prev_proj else None
        )
        return {
            "outcome": outcome,
            "workspace_id": ws.id,
            "workspace_path": ws.path,
            "previous_workspace_id": previous_ws_id,
            "shared_path_warning": shared_path_warning,
            "reason": (
                "Source path exists on disk — existing workspace record reused and re-pinned"
                if ws_decision == "reused_existing"
                else "Source path exists on disk — new workspace record created and pinned"
            ),
            "message": f"Workspace rebound to existing source path: {ws.path}",
        }

    elif source == Source.github_repo:
        if not project.source_url:
            return {
                "outcome": "blocked",
                "workspace_id": None,
                "workspace_path": None,
                "previous_workspace_id": previous_ws_id,
                "shared_path_warning": None,
                "reason": "github_repo project has no source_url — cannot re-clone",
                "message": "Cannot recover: project has no GitHub URL recorded.",
            }
        ws_path = os.path.join(safe_root, project.name)
        if not os.path.exists(ws_path):
            rc, _, stderr = await _run_subprocess(["git", "clone", project.source_url, ws_path])
            if rc != 0:
                return {
                    "outcome": "blocked",
                    "workspace_id": None,
                    "workspace_path": ws_path,
                    "previous_workspace_id": previous_ws_id,
                    "shared_path_warning": None,
                    "reason": f"git clone failed: {stderr.strip()}",
                    "message": "Recovery blocked: git clone failed. Check network access and source_url.",
                }
        if git_branch:
            await _run_subprocess(["git", "checkout", git_branch], cwd=ws_path)
        _, remote_out, _ = await _run_subprocess(["git", "remote", "get-url", "origin"], cwd=ws_path)
        git_remote = remote_out.strip() or None
        _, branch_out, _ = await _run_subprocess(["git", "branch", "--show-current"], cwd=ws_path)
        git_branch_actual = branch_out.strip() or None

        ws, ws_decision, prev_proj = _get_or_create_workspace_for_path(
            db, project, ws_path, git_remote, git_branch_actual
        )
        shared_path_warning = (
            f"This workspace path was previously associated with project {prev_proj}. "
            "Both projects now share the same workspace path. Review if this is intended."
            if prev_proj else None
        )
        return {
            "outcome": "recreated" if ws_decision == "created" else "rebound_reused",
            "workspace_id": ws.id,
            "workspace_path": ws.path,
            "previous_workspace_id": previous_ws_id,
            "shared_path_warning": shared_path_warning,
            "reason": "GitHub repo re-cloned into managed workspace path" if ws_decision == "created" else "Existing workspace record reused for managed path",
            "message": f"Workspace recreated at {ws.path} from {project.source_url}",
        }

    elif source == Source.new_project:
        ws_path = os.path.join(safe_root, project.name)
        os.makedirs(ws_path, exist_ok=True)
        ws, ws_decision, prev_proj = _get_or_create_workspace_for_path(db, project, ws_path)
        shared_path_warning = (
            f"This workspace path was previously associated with project {prev_proj}. "
            "Both projects now share the same workspace path. Review if this is intended."
            if prev_proj else None
        )
        return {
            "outcome": "recreated" if ws_decision == "created" else "rebound_reused",
            "workspace_id": ws.id,
            "workspace_path": ws.path,
            "previous_workspace_id": previous_ws_id,
            "shared_path_warning": shared_path_warning,
            "reason": "Managed project directory recreated under safe_root" if ws_decision == "created" else "Existing workspace record reused for managed path",
            "message": f"Workspace directory recreated at {ws.path}",
        }

    return {
        "outcome": "blocked",
        "workspace_id": None,
        "workspace_path": None,
        "previous_workspace_id": previous_ws_id,
        "shared_path_warning": None,
        "reason": f"Unknown source type: {project.source}",
        "message": "Cannot recover workspace for unknown source type.",
    }
