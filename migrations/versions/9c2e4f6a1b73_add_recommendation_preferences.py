"""add recommendation preferences and source references

Revision ID: 9c2e4f6a1b73
Revises: 36475e375cb5
Create Date: 2026-07-15 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "9c2e4f6a1b73"
down_revision = "36475e375cb5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("recommendations") as batch_op:
        batch_op.add_column(
            sa.Column("source_references", sa.JSON(), nullable=False, server_default="[]")
        )
    op.create_table(
        "recommendation_preferences",
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("workspace_id", sa.String(length=64), nullable=False),
        sa.Column("workspace_app_id", sa.String(length=64), nullable=False),
        sa.Column("preference", sa.String(length=16), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "preference IN ('enabled', 'reduced', 'disabled')",
            name="ck_recommendation_preferences_preference",
        ),
        sa.PrimaryKeyConstraint("user_id", "workspace_id"),
    )


def downgrade() -> None:
    op.drop_table("recommendation_preferences")
    with op.batch_alter_table("recommendations") as batch_op:
        batch_op.drop_column("source_references")
