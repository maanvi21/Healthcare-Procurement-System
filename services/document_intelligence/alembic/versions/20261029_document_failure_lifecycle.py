"""Persist watched-file location and processing failures.

Revision ID: 20261029_docfail
Revises: fd0120855bdf
"""
from alembic import op
import sqlalchemy as sa

revision = "20261029_docfail"
down_revision = "fd0120855bdf"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TYPE document_status ADD VALUE IF NOT EXISTS 'failed'")
    op.add_column("documents", sa.Column("watcher_input_path", sa.String(length=1024), nullable=True))
    op.add_column("documents", sa.Column("processing_error", sa.Text(), nullable=True))


def downgrade():
    op.drop_column("documents", "processing_error")
    op.drop_column("documents", "watcher_input_path")
    # PostgreSQL enum values cannot be removed safely without rebuilding the type.
