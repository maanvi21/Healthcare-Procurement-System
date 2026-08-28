"""add vendor registered address columns

Adds the registered business address that onboarding's contact & address validation
checks (see app/kyc.py check_address). Nullable so the migration applies cleanly to
existing rows; vendors missing an address are surfaced through the onboarding decision
(pending_review with an explicit reason) rather than by a NOT NULL constraint that would
make the migration fail on any existing deployment.

Revision ID: b7e1c4a92f30
Revises: 5050de28e65f
Create Date: 2026-08-28
"""
from alembic import op
import sqlalchemy as sa


revision = 'b7e1c4a92f30'
down_revision = '5050de28e65f'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('vendors', sa.Column('address_line1', sa.String(length=256), nullable=True))
    op.add_column('vendors', sa.Column('address_line2', sa.String(length=256), nullable=True))
    op.add_column('vendors', sa.Column('city', sa.String(length=128), nullable=True))
    op.add_column('vendors', sa.Column('state', sa.String(length=128), nullable=True))
    op.add_column('vendors', sa.Column('postal_code', sa.String(length=16), nullable=True))
    op.add_column('vendors', sa.Column('country', sa.String(length=64), nullable=True))


def downgrade():
    op.drop_column('vendors', 'country')
    op.drop_column('vendors', 'postal_code')
    op.drop_column('vendors', 'state')
    op.drop_column('vendors', 'city')
    op.drop_column('vendors', 'address_line2')
    op.drop_column('vendors', 'address_line1')
