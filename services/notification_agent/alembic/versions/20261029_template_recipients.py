"""Add editable recipient expressions to notification templates.

Revision ID: 20261029_tplrecip
Revises: a1b2c3d4e5f6
"""
from alembic import op
import sqlalchemy as sa

revision = "20261029_tplrecip"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("notification_templates", sa.Column("recipient_template", sa.String(length=512), nullable=True))


def downgrade():
    op.drop_column("notification_templates", "recipient_template")
