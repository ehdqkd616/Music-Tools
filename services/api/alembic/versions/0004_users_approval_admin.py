"""users: is_approved + is_admin for admin-gated signup

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-06

"""
import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users", sa.Column("is_approved", sa.Boolean(), nullable=False, server_default=sa.false())
    )
    op.add_column("users", sa.Column("is_admin", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    op.drop_column("users", "is_admin")
    op.drop_column("users", "is_approved")
