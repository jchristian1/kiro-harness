"""add progress fields to runs

Revision ID: 0002
Revises: 0001
Create Date: 2026-04-08 00:00:00.000000
"""
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE runs ADD COLUMN progress_message TEXT")
    op.execute("ALTER TABLE runs ADD COLUMN last_activity_at TEXT")
    op.execute("ALTER TABLE runs ADD COLUMN partial_output TEXT")


def downgrade() -> None:
    # SQLite does not support DROP COLUMN before 3.35; safe to leave columns
    pass
