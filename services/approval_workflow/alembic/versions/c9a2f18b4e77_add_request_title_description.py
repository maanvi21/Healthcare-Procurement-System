"""add procurement request title and description

An approver's inbox previously showed only department, total value and step number, which
is not enough information to approve or reject a purchase. These columns carry what is
actually being bought; both nullable so existing rows migrate cleanly and are backfilled
from their line items by the application (service.derive_title).

Revision ID: c9a2f18b4e77
Revises: b36030ce9776
Create Date: 2026-08-28
"""
from alembic import op
import sqlalchemy as sa


revision = 'c9a2f18b4e77'
down_revision = 'b36030ce9776'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('procurement_requests', sa.Column('title', sa.String(length=256), nullable=True))
    op.add_column('procurement_requests', sa.Column('description', sa.Text(), nullable=True))


def downgrade():
    op.drop_column('procurement_requests', 'description')
    op.drop_column('procurement_requests', 'title')
