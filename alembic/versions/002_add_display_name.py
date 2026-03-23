"""add display_name to shifts

Revision ID: 002
Revises: 001
Create Date: 2026-03-23
"""

from alembic import op
import sqlalchemy as sa

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("shifts", sa.Column("display_name", sa.String(128), nullable=True))


def downgrade() -> None:
    op.drop_column("shifts", "display_name")
