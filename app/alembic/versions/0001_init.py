"""init: users, dialog_state, profiles, leads, messages

Revision ID: 0001_init
Revises:
Create Date: 2026-06-10
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "0001_init"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("channel", sa.String(16), server_default="max", index=True),
        sa.Column("ext_id", sa.String(64), nullable=False, index=True),
        sa.Column("username", sa.String(128), nullable=True),
        sa.Column("full_name", sa.String(256), nullable=True),
        sa.Column("consent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("channel", "ext_id", name="uq_user_channel_ext"),
        sa.CheckConstraint("channel in ('max','telegram')", name="ck_user_channel"),
    )
    op.create_table(
        "dialog_state",
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("step", sa.String(48), server_default="menu"),
        sa.Column("mode", sa.String(16), nullable=True),
        sa.Column("data", JSONB, server_default="{}"),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "profiles",
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("trainer", JSONB, server_default="{}"),
        sa.Column("diet", JSONB, server_default="{}"),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "progress",
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("belt", sa.String(16), nullable=True),
        sa.Column("stripes", sa.Integer, server_default="0"),
        sa.Column("xp", sa.Integer, server_default="0"),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "leads",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), index=True),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("phone", sa.String(64), nullable=True),
        sa.Column("note", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "messages",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), index=True),
        sa.Column("direction", sa.String(8), nullable=False),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), index=True),
        sa.CheckConstraint("direction in ('in','out')", name="ck_message_direction"),
    )


def downgrade() -> None:
    op.drop_table("messages")
    op.drop_table("leads")
    op.drop_table("progress")
    op.drop_table("profiles")
    op.drop_table("dialog_state")
    op.drop_table("users")
