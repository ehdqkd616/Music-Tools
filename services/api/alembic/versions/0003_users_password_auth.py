"""users: NOT NULL email + password_hash for email/password auth

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-06

"""
import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("users", "email", existing_type=sa.String(), nullable=False)
    op.add_column("users", sa.Column("password_hash", sa.Text(), nullable=False))


def downgrade() -> None:
    op.drop_column("users", "password_hash")
    op.alter_column("users", "email", existing_type=sa.String(), nullable=True)
