"""add cancelled status to runs

Revision ID: 0003
Revises: 0002
Create Date: 2026-04-10 00:00:00.000000

SQLite does not support ALTER COLUMN for CHECK constraints.
We recreate the runs table with the updated constraint.
"""
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Clean up any leftover temp table from a previous failed attempt
    op.execute("DROP TABLE IF EXISTS runs_new")
    # SQLite: drop and recreate the check constraint by rebuilding the table
    op.execute("""
        CREATE TABLE runs_new (
            id                TEXT PRIMARY KEY,
            task_id           TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
            mode              TEXT NOT NULL CHECK (mode IN ('analyze', 'implement', 'validate')),
            status            TEXT NOT NULL CHECK (status IN ('running', 'completed', 'parse_failed', 'error', 'cancelled')),
            agent             TEXT NOT NULL,
            skill             TEXT NOT NULL,
            context_snapshot  TEXT NOT NULL,
            raw_output        TEXT,
            parse_status      TEXT CHECK (parse_status IN ('ok', 'parse_failed', 'schema_invalid')),
            failure_reason    TEXT,
            progress_message  TEXT,
            last_activity_at  TEXT,
            partial_output    TEXT,
            started_at        TEXT NOT NULL DEFAULT '1970-01-01T00:00:00+00:00',
            completed_at      TEXT
        )
    """)
    # Use COALESCE to handle any rows with NULL started_at from previous failed runs
    op.execute("""
        INSERT INTO runs_new
        SELECT
            id, task_id, mode, status, agent, skill, context_snapshot,
            raw_output, parse_status, failure_reason, progress_message,
            last_activity_at, partial_output,
            COALESCE(started_at, '1970-01-01T00:00:00+00:00'),
            completed_at
        FROM runs
    """)
    op.execute("DROP TABLE runs")
    op.execute("ALTER TABLE runs_new RENAME TO runs")
    op.execute("CREATE INDEX IF NOT EXISTS idx_runs_task_id ON runs(task_id)")


def downgrade() -> None:
    # Remove cancelled status — any cancelled runs become error
    op.execute("UPDATE runs SET status='error' WHERE status='cancelled'")
    op.execute("DROP TABLE IF EXISTS runs_new")
    op.execute("""
        CREATE TABLE runs_new (
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
            progress_message  TEXT,
            last_activity_at  TEXT,
            partial_output    TEXT,
            started_at        TEXT NOT NULL DEFAULT '1970-01-01T00:00:00+00:00',
            completed_at      TEXT
        )
    """)
    op.execute("""
        INSERT INTO runs_new
        SELECT
            id, task_id, mode, status, agent, skill, context_snapshot,
            raw_output, parse_status, failure_reason, progress_message,
            last_activity_at, partial_output,
            COALESCE(started_at, '1970-01-01T00:00:00+00:00'),
            completed_at
        FROM runs
    """)
    op.execute("DROP TABLE runs")
    op.execute("ALTER TABLE runs_new RENAME TO runs")
    op.execute("CREATE INDEX IF NOT EXISTS idx_runs_task_id ON runs(task_id)")
