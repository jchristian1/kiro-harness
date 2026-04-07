"""initial schema

Revision ID: 0001
Revises:
Create Date: 2025-01-01 00:00:00.000000
"""
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("PRAGMA foreign_keys = ON")

    op.execute("""
        CREATE TABLE IF NOT EXISTS meta (
            key   TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    """)
    op.execute("INSERT OR IGNORE INTO meta (key, value) VALUES ('schema_version', '1')")

    op.execute("""
        CREATE TABLE IF NOT EXISTS projects (
            id           TEXT PRIMARY KEY,
            name         TEXT NOT NULL,
            source       TEXT NOT NULL CHECK (source IN ('new_project', 'github_repo', 'local_repo', 'local_folder')),
            source_url   TEXT,
            workspace_id TEXT REFERENCES workspaces(id) ON DELETE SET NULL,
            owner_id     TEXT,
            created_at   TEXT NOT NULL,
            updated_at   TEXT NOT NULL,
            UNIQUE (name)
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS workspaces (
            id               TEXT PRIMARY KEY,
            project_id       TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            path             TEXT NOT NULL UNIQUE,
            git_remote       TEXT,
            git_branch       TEXT,
            created_at       TEXT NOT NULL,
            last_accessed_at TEXT NOT NULL
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id           TEXT PRIMARY KEY,
            project_id   TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            workspace_id TEXT NOT NULL REFERENCES workspaces(id),
            intent       TEXT NOT NULL CHECK (intent IN (
                             'new_project', 'add_feature', 'refactor', 'fix_bug',
                             'analyze_codebase', 'upgrade_dependencies', 'prepare_pr'
                           )),
            source       TEXT NOT NULL CHECK (source IN (
                             'new_project', 'github_repo', 'local_repo', 'local_folder'
                           )),
            operation    TEXT NOT NULL CHECK (operation IN (
                             'plan_only', 'analyze_then_approve', 'implement_now', 'implement_and_prepare_pr'
                           )),
            description  TEXT NOT NULL,
            status       TEXT NOT NULL CHECK (status IN (
                             'created', 'opening', 'analyzing', 'awaiting_approval',
                             'implementing', 'validating', 'awaiting_revision', 'done', 'failed'
                           )),
            approved_at  TEXT,
            created_at   TEXT NOT NULL,
            updated_at   TEXT NOT NULL
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_tasks_project_id ON tasks(project_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status)")

    op.execute("""
        CREATE TABLE IF NOT EXISTS runs (
            id                TEXT PRIMARY KEY,
            task_id           TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
            mode              TEXT NOT NULL CHECK (mode IN ('analyze', 'implement', 'validate')),
            status            TEXT NOT NULL CHECK (status IN ('running', 'completed', 'parse_failed', 'error')),
            agent             TEXT NOT NULL,
            skill             TEXT NOT NULL,
            context_snapshot  TEXT NOT NULL,
            raw_output        TEXT,
            parse_status      TEXT CHECK (parse_status IN ('ok', 'parse_failed', 'schema_invalid')),
            failure_reason    TEXT,
            started_at        TEXT NOT NULL,
            completed_at      TEXT
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_runs_task_id ON runs(task_id)")

    op.execute("""
        CREATE TABLE IF NOT EXISTS artifacts (
            id             TEXT PRIMARY KEY,
            run_id         TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
            task_id        TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
            type           TEXT NOT NULL CHECK (type IN ('analysis', 'implementation', 'validation')),
            schema_version TEXT NOT NULL,
            content        TEXT NOT NULL,
            file_path      TEXT,
            created_at     TEXT NOT NULL,
            UNIQUE (run_id)
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_artifacts_task_id ON artifacts(task_id)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_artifacts_task_id")
    op.execute("DROP TABLE IF EXISTS artifacts")
    op.execute("DROP INDEX IF EXISTS idx_runs_task_id")
    op.execute("DROP TABLE IF EXISTS runs")
    op.execute("DROP INDEX IF EXISTS idx_tasks_status")
    op.execute("DROP INDEX IF EXISTS idx_tasks_project_id")
    op.execute("DROP TABLE IF EXISTS tasks")
    op.execute("DROP TABLE IF EXISTS workspaces")
    op.execute("DROP TABLE IF EXISTS projects")
    op.execute("DROP TABLE IF EXISTS meta")
