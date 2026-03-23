"""add ticket threading for notes

Revision ID: 004
Revises: 003
Create Date: 2026-03-23
"""

from alembic import op
import sqlalchemy as sa

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tickets", sa.Column("is_active", sa.Boolean(), nullable=False, server_default="false"))
    op.add_column("notes", sa.Column("ticket_id", sa.Uuid(), nullable=True))
    op.create_foreign_key("fk_notes_ticket_id", "notes", "tickets", ["ticket_id"], ["id"], ondelete="CASCADE")


def downgrade() -> None:
    op.drop_constraint("fk_notes_ticket_id", "notes", type_="foreignkey")
    op.drop_column("notes", "ticket_id")
    op.drop_column("tickets", "is_active")
