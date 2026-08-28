"""baseline schema

Revision ID: a1b2c3d4e5f6
Revises:
Create Date: 2026-08-26 11:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = "a1b2c3d4e5f6"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "notification_templates",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("event_type", sa.String(length=128), nullable=False),
        sa.Column(
            "channel",
            sa.Enum("email", "sms", "teams", "slack", name="notification_channel"),
            nullable=False,
        ),
        sa.Column("subject_template", sa.String(length=512), nullable=True),
        sa.Column("body_template", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "notifications",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("template_id", sa.UUID(), nullable=True),
        sa.Column(
            "channel",
            sa.Enum("email", "sms", "teams", "slack", name="notification_channel", create_type=False),
            nullable=False,
        ),
        sa.Column("recipient", sa.String(length=256), nullable=False),
        sa.Column("subject", sa.String(length=512), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("event_type", sa.String(length=128), nullable=True),
        sa.Column("event_key", sa.String(length=256), nullable=True),
        sa.Column(
            "status",
            sa.Enum("queued", "sent", "failed", name="notification_status"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["template_id"], ["notification_templates.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade():
    op.drop_table("notifications")
    op.drop_table("notification_templates")
    op.execute("DROP TYPE IF EXISTS notification_status")
    op.execute("DROP TYPE IF EXISTS notification_channel")
