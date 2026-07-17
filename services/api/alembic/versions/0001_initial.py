"""initial schema (§8)

Revision ID: 0001
Revises:
Create Date: 2026-07-17

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("email", sa.String(), unique=True),
        sa.Column("tier", sa.String(), nullable=False, server_default="free"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "media",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE")),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("source_type", sa.Text(), nullable=False),
        sa.Column("parent_id", sa.Text(), sa.ForeignKey("media.id", ondelete="CASCADE")),
        sa.Column("content_hash", sa.Text(), nullable=False),
        sa.Column("storage_key", sa.Text(), nullable=False),
        sa.Column("mime_type", sa.Text(), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("duration_sec", sa.Numeric(10, 3)),
        sa.Column("sample_rate", sa.Integer()),
        sa.Column("channels", sa.SmallInteger()),
        sa.Column("yt_video_id", sa.Text()),
        sa.Column("title", sa.Text()),
        sa.Column("artist", sa.Text()),
        sa.Column("lineage", postgresql.JSONB(), server_default="{}"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_media_hash", "media", ["content_hash"])
    op.create_index("idx_media_expires", "media", ["expires_at"])
    op.create_index("idx_media_user", "media", ["user_id", "created_at"])
    op.create_index(
        "idx_media_ytid", "media", ["yt_video_id"], postgresql_where=sa.text("yt_video_id IS NOT NULL")
    )

    op.create_table(
        "analyses",
        sa.Column("content_hash", sa.Text(), primary_key=True),
        sa.Column("key_tonic", sa.Text()),
        sa.Column("key_mode", sa.Text()),
        sa.Column("key_conf", sa.REAL()),
        sa.Column("bpm", sa.REAL()),
        sa.Column("beat_times", postgresql.JSONB()),
        sa.Column("lufs", sa.REAL()),
        sa.Column("true_peak_db", sa.REAL()),
        sa.Column("computed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "jobs",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="queued"),
        sa.Column("input_media", sa.Text(), sa.ForeignKey("media.id")),
        sa.Column("params", postgresql.JSONB(), server_default="{}"),
        sa.Column("output_media", postgresql.ARRAY(sa.Text())),
        sa.Column("progress", sa.REAL(), server_default="0"),
        sa.Column("error_code", sa.Text()),
        sa.Column("error_message", sa.Text()),
        sa.Column("worker_id", sa.Text()),
        sa.Column("cache_hit", sa.Boolean(), server_default=sa.false()),
        sa.Column("attempts", sa.Integer(), server_default="0"),
        sa.Column("queued_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
    )
    op.create_index("idx_jobs_status", "jobs", ["status", "queued_at"])
    op.create_index("idx_jobs_user", "jobs", ["user_id", "queued_at"])

    op.create_table(
        "usage_counters",
        sa.Column("subject", sa.Text(), primary_key=True),
        sa.Column("window_date", sa.Date(), primary_key=True),
        sa.Column("downloads", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("separations", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("gpu_seconds", sa.Numeric(10, 2), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_table("usage_counters")
    op.drop_table("jobs")
    op.drop_table("analyses")
    op.drop_index("idx_media_ytid", table_name="media")
    op.drop_index("idx_media_user", table_name="media")
    op.drop_index("idx_media_expires", table_name="media")
    op.drop_index("idx_media_hash", table_name="media")
    op.drop_table("media")
    op.drop_table("users")
