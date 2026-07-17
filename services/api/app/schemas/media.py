from datetime import datetime

from pydantic import BaseModel


class MediaUrlResponse(BaseModel):
    media_id: str
    url: str
    expires_in_sec: int


class UploadResponse(BaseModel):
    media_id: str
    title: str | None
    duration_sec: float | None
    content_hash: str


class LibraryItem(BaseModel):
    media_id: str
    title: str | None
    artist: str | None
    source_type: str
    yt_video_id: str | None
    thumbnail: str | None
    duration_sec: float | None
    has_stems: bool
    created_at: datetime
