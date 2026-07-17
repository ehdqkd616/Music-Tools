from pydantic import BaseModel


class YoutubeInfoRequest(BaseModel):
    url: str


class FormatOption(BaseModel):
    id: str
    label: str
    est_size_mb: float


class YoutubeInfoResponse(BaseModel):
    video_id: str
    title: str
    channel: str
    duration_sec: int
    thumbnail: str | None = None
    available_formats: dict[str, list[FormatOption]]
    cached: bool


class YoutubeExtractRequest(BaseModel):
    url: str
    kind: str  # "audio" | "video"
    format_id: str  # e.g. mp3-320, wav, mp4-1080
