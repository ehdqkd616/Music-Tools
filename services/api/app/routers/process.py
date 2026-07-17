from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from common.cache import cache_get, l2_key, pitch_key, tempo_key
from common.celery_client import send_task
from common.config import get_settings
from common.db.models import Media
from common.db.session import SessionLocal

from ..deps import enforce_separate_quota
from ..errors import ApiError
from ..job_utils import ETA_SEC, create_job, queue_position
from ..schemas.jobs import JobCreatedResponse
from ..schemas.process import MixRequest, PitchRequest, SeparateRequest, TempoRequest

router = APIRouter()


def _get_media(db: Session, media_id: str) -> Media:
    media = db.get(Media, media_id)
    if not media:
        raise ApiError("NOT_FOUND", "미디어를 찾을 수 없습니다.", {"media_id": media_id})
    return media


@router.post("/separate", response_model=JobCreatedResponse, dependencies=[Depends(enforce_separate_quota)])
def process_separate(body: SeparateRequest) -> JobCreatedResponse:
    if body.stems != 2:
        raise ApiError("VALIDATION_ERROR", "MVP는 2스템(보컬/반주) 분리만 지원합니다.", {"stems": body.stems})

    settings = get_settings()
    db = SessionLocal()
    try:
        media = _get_media(db, body.media_id)
        model_name = settings.demucs_fast_model if body.quality == "fast" else settings.demucs_hq_model

        cached = cache_get(l2_key(media.content_hash, model_name, body.stems))
        if cached:
            job = create_job(db, "separate", body.media_id, body.model_dump())
            job.status = "succeeded"
            job.output_media = [v for v in cached.values() if v]
            job.cache_hit = True
            job.progress = 100
            db.commit()
            return JobCreatedResponse(job_id=job.id, status="succeeded", cached=True)

        job = create_job(db, "separate", body.media_id, body.model_dump())
    finally:
        db.close()

    send_task("tasks.separate_stems", args=[job.id], queue="separate")

    eta = ETA_SEC["separate_high"] if body.quality == "high" else ETA_SEC["separate_fast"]
    return JobCreatedResponse(
        job_id=job.id, status="queued", queue_position=queue_position("separate"), eta_sec=eta, cached=False
    )


@router.post("/pitch", response_model=JobCreatedResponse)
def process_pitch(body: PitchRequest) -> JobCreatedResponse:
    db = SessionLocal()
    try:
        media = _get_media(db, body.media_id)

        cache_key = pitch_key(media.content_hash, body.semitones, body.stem_type)
        cached = cache_get(cache_key)
        if cached and cached.get("media_id"):
            job = create_job(db, "pitch", body.media_id, body.model_dump())
            job.status = "succeeded"
            job.output_media = [cached["media_id"]]
            job.cache_hit = True
            job.progress = 100
            db.commit()
            return JobCreatedResponse(job_id=job.id, status="succeeded", cached=True)

        job = create_job(db, "pitch", body.media_id, body.model_dump())
    finally:
        db.close()

    send_task("tasks.pitch_shift_stems", args=[job.id], queue="dsp")
    return JobCreatedResponse(
        job_id=job.id, status="queued", queue_position=queue_position("pitch"), eta_sec=ETA_SEC["pitch"]
    )


@router.post("/tempo", response_model=JobCreatedResponse)
def process_tempo(body: TempoRequest) -> JobCreatedResponse:
    db = SessionLocal()
    try:
        media = _get_media(db, body.media_id)

        cache_key = tempo_key(media.content_hash, body.ratio)
        cached = cache_get(cache_key)
        if cached and cached.get("media_id"):
            job = create_job(db, "tempo", body.media_id, body.model_dump())
            job.status = "succeeded"
            job.output_media = [cached["media_id"]]
            job.cache_hit = True
            job.progress = 100
            db.commit()
            return JobCreatedResponse(job_id=job.id, status="succeeded", cached=True)

        job = create_job(db, "tempo", body.media_id, body.model_dump())
    finally:
        db.close()

    send_task("tasks.time_stretch_stems", args=[job.id], queue="dsp")
    return JobCreatedResponse(
        job_id=job.id, status="queued", queue_position=queue_position("tempo"), eta_sec=ETA_SEC["tempo"]
    )


@router.post("/mix", response_model=JobCreatedResponse)
def process_mix(body: MixRequest) -> JobCreatedResponse:
    db = SessionLocal()
    try:
        for media_id in body.media_ids:
            _get_media(db, media_id)
        job = create_job(db, "mix", body.media_ids[0], body.model_dump())
    finally:
        db.close()

    send_task("tasks.mix_stems", args=[job.id], queue="dsp")
    return JobCreatedResponse(
        job_id=job.id, status="queued", queue_position=queue_position("mix"), eta_sec=ETA_SEC["mix"]
    )
