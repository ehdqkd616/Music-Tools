import uuid
from datetime import datetime

from sqlalchemy import (
    ARRAY,
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    REAL,
    Numeric,
    SmallInteger,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from .session import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    is_approved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    tier: Mapped[str] = mapped_column(String, nullable=False, default="free")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Media(Base):
    __tablename__ = "media"

    id: Mapped[str] = mapped_column(Text, primary_key=True)  # med_xxxxx
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE")
    )
    kind: Mapped[str] = mapped_column(Text, nullable=False)  # source | stem | processed
    source_type: Mapped[str] = mapped_column(Text, nullable=False)  # youtube | upload | derived
    parent_id: Mapped[str | None] = mapped_column(Text, ForeignKey("media.id", ondelete="CASCADE"))

    content_hash: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    storage_key: Mapped[str] = mapped_column(Text, nullable=False)
    mime_type: Mapped[str] = mapped_column(Text, nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    duration_sec: Mapped[float | None] = mapped_column(Numeric(10, 3))
    sample_rate: Mapped[int | None] = mapped_column()
    channels: Mapped[int | None] = mapped_column(SmallInteger)

    yt_video_id: Mapped[str | None] = mapped_column(Text, index=True)
    title: Mapped[str | None] = mapped_column(Text)
    artist: Mapped[str | None] = mapped_column(Text)

    lineage: Mapped[dict] = mapped_column(JSONB, server_default="{}")

    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Analysis(Base):
    __tablename__ = "analyses"

    content_hash: Mapped[str] = mapped_column(Text, primary_key=True)
    key_tonic: Mapped[str | None] = mapped_column(Text)
    key_mode: Mapped[str | None] = mapped_column(Text)  # major | minor
    key_conf: Mapped[float | None] = mapped_column(REAL)
    bpm: Mapped[float | None] = mapped_column(REAL)
    beat_times: Mapped[list | None] = mapped_column(JSONB)
    lufs: Mapped[float | None] = mapped_column(REAL)
    true_peak_db: Mapped[float | None] = mapped_column(REAL)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(Text, primary_key=True)  # job_xxxxx
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    type: Mapped[str] = mapped_column(Text, nullable=False)  # extract|separate|pitch|tempo|mix
    status: Mapped[str] = mapped_column(Text, nullable=False, default="queued")
    input_media: Mapped[str | None] = mapped_column(Text, ForeignKey("media.id", ondelete="SET NULL"))
    params: Mapped[dict] = mapped_column(JSONB, server_default="{}")
    output_media: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    progress: Mapped[float] = mapped_column(REAL, default=0)
    error_code: Mapped[str | None] = mapped_column(Text)
    error_message: Mapped[str | None] = mapped_column(Text)
    worker_id: Mapped[str | None] = mapped_column(Text)
    cache_hit: Mapped[bool] = mapped_column(Boolean, default=False)
    attempts: Mapped[int] = mapped_column(default=0)

    queued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class UsageCounter(Base):
    __tablename__ = "usage_counters"

    subject: Mapped[str] = mapped_column(Text, primary_key=True)  # user:{uuid} | ip:{hash}
    window_date: Mapped[datetime] = mapped_column(Date, primary_key=True)
    downloads: Mapped[int] = mapped_column(default=0)
    separations: Mapped[int] = mapped_column(default=0)
    gpu_seconds: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
