"""add users.referred_by (рефералка)

Revision ID: 0005_referral
Revises: 0004_journal
Create Date: 2026-06-11
"""
from alembic import op
import sqlalchemy as sa

revision = "0005_referral"
down_revision = "0004_journal"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("referred_by", sa.Integer(), nullable=True))
    op.create_index("ix_users_referred_by", "users", ["referred_by"])


def downgrade() -> None:
    op.drop_index("ix_users_referred_by", table_name="users")
    op.drop_column("users", "referred_by")
