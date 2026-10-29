"""Persist provider diagnostics for failed notification deliveries.

Revision ID: 20261029_notiferror
Revises: 20261029_tplactive
"""
from alembic import op
import sqlalchemy as sa

revision = "20261029_notiferror"
down_revision = "20261029_tplactive"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("notifications", sa.Column("failure_reason", sa.Text(), nullable=True))


def downgrade():
    op.drop_column("notifications", "failure_reason")
