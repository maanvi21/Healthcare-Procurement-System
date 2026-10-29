"""Distinguish live deliveries from log-only notification demos.

Revision ID: 20261029_simulated
Revises: 20261029_tplrecip
"""
from alembic import op

revision = "20261029_simulated"
down_revision = "20261029_tplrecip"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TYPE notification_status ADD VALUE IF NOT EXISTS 'simulated'")


def downgrade():
    # PostgreSQL enum values cannot be removed safely without rebuilding the type.
    pass
