from fastapi import APIRouter, Depends, Request

from common.cache import cache_get, cache_set, l1_key, L1_TTL
from common.celery_client import send_task
from common.redis_client import get_redis
from common.youtube_url import extract_video_id, normalize_youtube_url
from common.ytdlp import fetch_info
from common.config import get_settings

from ..deps import enforce_download_quota
from ..errors import ApiError
from ..job_utils import ETA_SEC, create_job, queue_position
from ..schemas.jobs import JobCreatedResponse
from ..schemas.youtube import FormatOption, YoutubeExtractRequest, YoutubeInfoRequest, YoutubeInfoResponse

router = APIRouter()

AUDIO_QUALITIES = [
    ("mp3-320", "MP3 320kbps", 320),
    ("mp3-192", "MP3 192kbps", 192),
    ("wav", "WAV 무손실", 1411),
]
VIDEO_QUALITIES = [
    ("mp4-1080", "MP4 1080p", 1080),
    ("mp4-720", "MP4 720p", 720),
    ("mp4-360", "MP4 360p", 360),
]

_VIDEO_MB_PER_SEC = {1080: 0.28, 720: 0.14, 360: 0.05}


@router.post("/info", response_model=YoutubeInfoResponse)
def get_info(body: YoutubeInfoRequest) -> YoutubeInfoResponse:
    settings = get_settings()
    normalized = normalize_youtube_url(body.url)
    if not normalized:
        raise ApiError("INVALID_URL", "유효한 유튜브 URL이 아닙니다.")

    video_id = extract_video_id(normalized)
    cached = cache_get(l1_key(video_id, "info", "meta"))
    if cached:
        return YoutubeInfoResponse(**cached, cached=True)

    try:
        info = fetch_info(normalized)
    except Exception as exc:  # yt-dlp failure surfaces as retryable extraction error
        raise ApiError("EXTRACTION_FAILED", "유튜브 정보를 가져오지 못했습니다.", {"reason": str(exc)})

    if info.get("is_live"):
        raise ApiError("LIVE_STREAM_UNSUPPORTED", "라이브 스트림은 처리할 수 없습니다.")

    duration = int(info.get("duration") or 0)
    if duration > settings.max_youtube_duration_sec:
        raise ApiError(
            "VIDEO_TOO_LONG",
            f"{settings.max_youtube_duration_sec // 60}분을 초과하는 영상은 처리할 수 없습니다.",
            {"duration_sec": duration, "max_sec": settings.max_youtube_duration_sec},
        )

    audio_formats = [
        FormatOption(id=fid, label=label, est_size_mb=round(duration * kbps / 8 / 1000, 1))
        for fid, label, kbps in AUDIO_QUALITIES
    ]
    video_formats = [
        FormatOption(id=fid, label=label, est_size_mb=round(duration * _VIDEO_MB_PER_SEC[h], 1))
        for fid, label, h in VIDEO_QUALITIES
    ]

    payload = {
        "video_id": video_id,
        "title": info.get("title") or "",
        "channel": info.get("channel") or info.get("uploader") or "",
        "duration_sec": duration,
        "thumbnail": info.get("thumbnail"),
        "available_formats": {"audio": [f.model_dump() for f in audio_formats], "video": [f.model_dump() for f in video_formats]},
    }
    cache_set(l1_key(video_id, "info", "meta"), payload, L1_TTL)
    return YoutubeInfoResponse(**payload, cached=False)


@router.post("/extract", response_model=JobCreatedResponse, dependencies=[Depends(enforce_download_quota)])
def extract(body: YoutubeExtractRequest, request: Request) -> JobCreatedResponse:
    from sqlalchemy.orm import Session

    from common.db.session import SessionLocal

    if get_redis().get("circuit:download_disabled"):
        # §5.1.3 circuit breaker — downloads go dark, rest of the product stays up.
        raise ApiError(
            "DOWNLOAD_TEMPORARILY_DISABLED",
            "유튜브 다운로드 기능이 일시적으로 비활성화되었습니다. 잠시 후 다시 시도하거나 파일을 직접 업로드해주세요.",
        )

    normalized = normalize_youtube_url(body.url)
    if not normalized:
        raise ApiError("INVALID_URL", "유효한 유튜브 URL이 아닙니다.")
    video_id = extract_video_id(normalized)

    cache_key = l1_key(video_id, body.kind, body.format_id)
    cached = cache_get(cache_key)
    if cached and cached.get("media_id"):
        return JobCreatedResponse(job_id=cached.get("job_id", "cached"), status="succeeded", cached=True)

    db: Session = SessionLocal()
    try:
        job = create_job(
            db,
            "extract",
            None,
            {"url": normalized, "video_id": video_id, "kind": body.kind, "format_id": body.format_id},
        )
    finally:
        db.close()

    send_task("tasks.extract_youtube", args=[job.id], queue="download")

    return JobCreatedResponse(
        job_id=job.id,
        status="queued",
        queue_position=queue_position("extract"),
        eta_sec=ETA_SEC["extract"],
        cached=False,
    )
