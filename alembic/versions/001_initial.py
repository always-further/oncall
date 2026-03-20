"""initial schema

Revision ID: 001
Revises:
Create Date: 2026-03-19
"""

from alembic import op
import sqlalchemy as sa

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "shifts",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("slack_user_id", sa.String(64), nullable=False),
        sa.Column("start_time", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("end_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("channel_id", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_one_active_shift_per_user",
        "shifts",
        ["slack_user_id"],
        unique=True,
        postgresql_where=sa.text("end_time IS NULL"),
    )

    op.create_table(
        "tickets",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("shift_id", sa.Uuid(), nullable=False),
        sa.Column("issue_url", sa.Text(), nullable=False),
        sa.Column("logged_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["shift_id"], ["shifts.id"], ondelete="CASCADE"),
    )


def downgrade() -> None:
    op.drop_table("tickets")
    op.drop_index("ix_one_active_shift_per_user", table_name="shifts")
    op.drop_table("shifts")
