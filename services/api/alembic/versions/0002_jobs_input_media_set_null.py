"""jobs.input_media FK: SET NULL on delete instead of blocking it

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-17

"""
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("jobs_input_media_fkey", "jobs", type_="foreignkey")
    op.create_foreign_key(
        "jobs_input_media_fkey", "jobs", "media", ["input_media"], ["id"], ondelete="SET NULL"
    )


def downgrade() -> None:
    op.drop_constraint("jobs_input_media_fkey", "jobs", type_="foreignkey")
    op.create_foreign_key("jobs_input_media_fkey", "jobs", "media", ["input_media"], ["id"])
