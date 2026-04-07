from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from ulid import ULID

from kiro_worker.db.models import Project
from kiro_worker.domain.enums import Source


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id(prefix: str) -> str:
    return f"{prefix}{ULID()}"


def create_project(db: Session, name: str, source: Source, source_url: str | None) -> Project:
    """Create a new project. Raises IntegrityError on duplicate name."""
    now = _now()
    project = Project(
        id=_new_id("proj_"),
        name=name,
        source=source.value,
        source_url=source_url,
        workspace_id=None,
        owner_id=None,
        created_at=now,
        updated_at=now,
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


def get_project(db: Session, project_id: str) -> Project | None:
    return db.query(Project).filter(Project.id == project_id).first()


def get_project_by_name(db: Session, name: str) -> Project | None:
    return db.query(Project).filter(Project.name == name).first()


def set_workspace(db: Session, project: Project, workspace_id: str) -> Project:
    project.workspace_id = workspace_id
    project.updated_at = _now()
    db.commit()
    db.refresh(project)
    return project
