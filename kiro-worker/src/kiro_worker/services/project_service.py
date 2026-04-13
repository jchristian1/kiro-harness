from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from ulid import ULID
import json

from kiro_worker.db.models import Project, Meta
from kiro_worker.domain.enums import Source


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id(prefix: str) -> str:
    return f"{prefix}{ULID()}"


def _alias_key(project_id: str) -> str:
    return f"project_aliases:{project_id}"


def get_aliases(db: Session, project_id: str) -> list[str]:
    """Return the list of aliases for a project (empty list if none)."""
    row = db.query(Meta).filter(Meta.key == _alias_key(project_id)).first()
    if not row:
        return []
    try:
        return json.loads(row.value)
    except Exception:
        return []


def set_alias(db: Session, project_id: str, alias: str) -> tuple[list[str], str]:
    """
    Add an alias to a project.
    Alias is stored lowercase for case-insensitive lookup.
    Returns (updated_aliases, conflict_project_id_or_none).
    If the alias is already taken by another project, returns (current_aliases, conflicting_project_id).
    If the alias already exists on this project, it is a no-op (idempotent).
    """
    normalized = alias.strip().lower()
    if not normalized:
        raise ValueError("Alias cannot be empty")

    # Check global uniqueness: scan all alias meta rows
    conflict_pid = _find_alias_owner(db, normalized)
    if conflict_pid and conflict_pid != project_id:
        return get_aliases(db, project_id), conflict_pid

    current = get_aliases(db, project_id)
    if normalized in current:
        return current, None  # already exists, idempotent

    updated = current + [normalized]
    _save_aliases(db, project_id, updated)
    return updated, None


def remove_alias(db: Session, project_id: str, alias: str) -> list[str]:
    """Remove an alias from a project. No-op if alias does not exist."""
    normalized = alias.strip().lower()
    current = get_aliases(db, project_id)
    updated = [a for a in current if a != normalized]
    _save_aliases(db, project_id, updated)
    return updated


def _save_aliases(db: Session, project_id: str, aliases: list[str]) -> None:
    key = _alias_key(project_id)
    row = db.query(Meta).filter(Meta.key == key).first()
    if row:
        row.value = json.dumps(aliases)
    else:
        row = Meta(key=key, value=json.dumps(aliases))
        db.add(row)
    db.commit()


def _find_alias_owner(db: Session, normalized_alias: str) -> str | None:
    """Return the project_id that owns this alias, or None."""
    rows = db.query(Meta).filter(Meta.key.like("project_aliases:%")).all()
    for row in rows:
        try:
            aliases = json.loads(row.value)
            if normalized_alias in aliases:
                return row.key.removeprefix("project_aliases:")
        except Exception:
            pass
    return None


def resolve_project(db: Session, query: str) -> tuple[Project | None, str]:
    """
    Resolve a project by id, canonical name, or alias.
    Returns (project, match_type) where match_type is 'id' | 'name' | 'alias' | 'not_found'.
    Lookup order: exact id → exact name → case-insensitive name → alias.
    """
    q = query.strip()
    q_lower = q.lower()

    # 1. Exact id
    p = db.query(Project).filter(Project.id == q).first()
    if p:
        return p, "id"

    # 2. Exact canonical name
    p = db.query(Project).filter(Project.name == q).first()
    if p:
        return p, "name"

    # 3. Case-insensitive name
    projects = db.query(Project).all()
    for p in projects:
        if p.name.lower() == q_lower:
            return p, "name"

    # 4. Alias lookup
    owner_id = _find_alias_owner(db, q_lower)
    if owner_id:
        p = db.query(Project).filter(Project.id == owner_id).first()
        if p:
            return p, "alias"

    return None, "not_found"


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


def update_source_url(db: Session, project: Project, new_source_url: str) -> Project:
    """Update a project's source_url in place. Preserves project identity and task history."""
    project.source_url = new_source_url
    project.updated_at = _now()
    db.commit()
    db.refresh(project)
    return project
