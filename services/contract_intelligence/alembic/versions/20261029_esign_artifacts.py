"""Persist provider identity and completed signature artifacts.

Revision ID: 20261029_esign
Revises: 7851334d2080
"""
from alembic import op
import sqlalchemy as sa

revision = "20261029_esign"
down_revision = "7851334d2080"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TYPE contract_status ADD VALUE IF NOT EXISTS 'declined'")
    op.add_column("contracts", sa.Column("signature_page", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("contracts", sa.Column("signing_url", sa.Text(), nullable=True))
    op.add_column("contracts", sa.Column("signer_name", sa.String(length=256), nullable=True))
    op.add_column("contracts", sa.Column("signer_email", sa.String(length=256), nullable=True))
    op.add_column("contracts", sa.Column("signing_provider", sa.String(length=32), nullable=True))
    op.add_column("contracts", sa.Column("signing_error", sa.Text(), nullable=True))
    op.add_column("contracts", sa.Column("signed_object_key", sa.String(length=512), nullable=True))
    op.add_column("contracts", sa.Column("certificate_object_key", sa.String(length=512), nullable=True))


def downgrade():
    for column in (
        "certificate_object_key", "signed_object_key", "signing_error",
        "signing_provider", "signer_email", "signer_name", "signing_url",
        "signature_page",
    ):
        op.drop_column("contracts", column)
    # PostgreSQL enum values cannot be removed safely without rebuilding the type.
