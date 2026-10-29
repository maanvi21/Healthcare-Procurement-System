"""Allow administrators to disable and restore templates without losing history.

Revision ID: 20261029_tplactive
Revises: 20261029_simulated
"""
from alembic import op
import sqlalchemy as sa

revision = "20261029_tplactive"
down_revision = "20261029_simulated"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "notification_templates",
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )


def downgrade():
    op.drop_column("notification_templates", "is_active")
