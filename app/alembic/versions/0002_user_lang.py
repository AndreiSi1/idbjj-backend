"""add users.lang (выбор языка: ru|en|es|pt)

Revision ID: 0002_user_lang
Revises: 0001_init
Create Date: 2026-06-11
"""
from alembic import op
import sqlalchemy as sa

revision = "0002_user_lang"
down_revision = "0001_init"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("lang", sa.String(8), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "lang")
