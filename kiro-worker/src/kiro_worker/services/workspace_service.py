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
    return db.query(Workspace).filter(Workspace.project_id == project_id).first()


def touch_workspace(db: Session, workspace: Workspace) -> None:
    workspace.last_accessed_at = _now()
    db.commit()
