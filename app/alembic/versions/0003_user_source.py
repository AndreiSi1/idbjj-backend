"""add users.source (атрибуция из deep-link ?start=...)

Revision ID: 0003_user_source
Revises: 0002_user_lang
Create Date: 2026-06-11
"""
from alembic import op
import sqlalchemy as sa

revision = "0003_user_source"
down_revision = "0002_user_lang"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("source", sa.String(64), nullable=True))
    op.create_index("ix_users_source", "users", ["source"])


def downgrade() -> None:
    op.drop_index("ix_users_source", table_name="users")
    op.drop_column("users", "source")
