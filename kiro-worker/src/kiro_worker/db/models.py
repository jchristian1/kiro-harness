from sqlalchemy import CheckConstraint, Index, UniqueConstraint, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Meta(Base):
    __tablename__ = "meta"

    key: Mapped[str] = mapped_column(primary_key=True)
    value: Mapped[str] = mapped_column(nullable=False)


class Project(Base):
    __tablename__ = "projects"
    __table_args__ = (
        CheckConstraint(
            "source IN ('new_project', 'github_repo', 'local_repo', 'local_folder')",
            name="ck_projects_source",
        ),
        UniqueConstraint("name", name="uq_projects_name"),
    )

    id: Mapped[str] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(nullable=False)
    source: Mapped[str] = mapped_column(nullable=False)
    source_url: Mapped[str | None] = mapped_column(nullable=True)
    workspace_id: Mapped[str | None] = mapped_column(nullable=True)
    owner_id: Mapped[str | None] = mapped_column(nullable=True)
    created_at: Mapped[str] = mapped_column(nullable=False)
    updated_at: Mapped[str] = mapped_column(nullable=False)


class Workspace(Base):
    __tablename__ = "workspaces"
    __table_args__ = (UniqueConstraint("path", name="uq_workspaces_path"),)

    id: Mapped[str] = mapped_column(primary_key=True)
    project_id: Mapped[str] = mapped_column(nullable=False)
    path: Mapped[str] = mapped_column(nullable=False)
    git_remote: Mapped[str | None] = mapped_column(nullable=True)
    git_branch: Mapped[str | None] = mapped_column(nullable=True)
    created_at: Mapped[str] = mapped_column(nullable=False)
    last_accessed_at: Mapped[str] = mapped_column(nullable=False)


class Task(Base):
    __tablename__ = "tasks"
    __table_args__ = (
        CheckConstraint(
            "intent IN ('new_project','add_feature','refactor','fix_bug','analyze_codebase','upgrade_dependencies','prepare_pr')",
            name="ck_tasks_intent",
        ),
        CheckConstraint(
            "source IN ('new_project','github_repo','local_repo','local_folder')",
            name="ck_tasks_source",
        ),
        CheckConstraint(
            "operation IN ('plan_only','analyze_then_approve','implement_now','implement_and_prepare_pr')",
            name="ck_tasks_operation",
        ),
        CheckConstraint(
            "status IN ('created','opening','analyzing','awaiting_approval','implementing','validating','awaiting_revision','done','failed')",
            name="ck_tasks_status",
        ),
        Index("idx_tasks_project_id", "project_id"),
        Index("idx_tasks_status", "status"),
    )

    id: Mapped[str] = mapped_column(primary_key=True)
    project_id: Mapped[str] = mapped_column(nullable=False)
    workspace_id: Mapped[str] = mapped_column(nullable=False)
    intent: Mapped[str] = mapped_column(nullable=False)
    source: Mapped[str] = mapped_column(nullable=False)
    operation: Mapped[str] = mapped_column(nullable=False)
    description: Mapped[str] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(nullable=False)
    approved_at: Mapped[str | None] = mapped_column(nullable=True)
    created_at: Mapped[str] = mapped_column(nullable=False)
    updated_at: Mapped[str] = mapped_column(nullable=False)


class Run(Base):
    __tablename__ = "runs"
    __table_args__ = (
        CheckConstraint("mode IN ('analyze','implement','validate')", name="ck_runs_mode"),
        CheckConstraint("status IN ('running','completed','parse_failed','error')", name="ck_runs_status"),
        CheckConstraint("parse_status IN ('ok','parse_failed','schema_invalid')", name="ck_runs_parse_status"),
        Index("idx_runs_task_id", "task_id"),
    )

    id: Mapped[str] = mapped_column(primary_key=True)
    task_id: Mapped[str] = mapped_column(nullable=False)
    mode: Mapped[str] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(nullable=False)
    agent: Mapped[str] = mapped_column(nullable=False)
    skill: Mapped[str] = mapped_column(nullable=False)
    context_snapshot: Mapped[str] = mapped_column(nullable=False)
    raw_output: Mapped[str | None] = mapped_column(nullable=True)
    parse_status: Mapped[str | None] = mapped_column(nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(nullable=True)
    started_at: Mapped[str] = mapped_column(nullable=False)
    completed_at: Mapped[str | None] = mapped_column(nullable=True)


class Artifact(Base):
    __tablename__ = "artifacts"
    __table_args__ = (
        CheckConstraint("type IN ('analysis','implementation','validation')", name="ck_artifacts_type"),
        UniqueConstraint("run_id", name="uq_artifacts_run_id"),
        Index("idx_artifacts_task_id", "task_id"),
    )

    id: Mapped[str] = mapped_column(primary_key=True)
    run_id: Mapped[str] = mapped_column(nullable=False)
    task_id: Mapped[str] = mapped_column(nullable=False)
    type: Mapped[str] = mapped_column(nullable=False)
    schema_version: Mapped[str] = mapped_column(nullable=False)
    content: Mapped[str] = mapped_column(nullable=False)
    file_path: Mapped[str | None] = mapped_column(nullable=True)
    created_at: Mapped[str] = mapped_column(nullable=False)
