from fastapi import APIRouter, Depends

from common.cache import cache_get, l2_key, pitch_key, tempo_key
from common.celery_client import send_task
from common.config import get_settings
from common.db.models import Job, User
from common.db.session import SessionLocal
from common.media_registry import clone_media_for_user

from ..deps import enforce_separate_quota, get_accessible_media, require_user
from ..errors import ApiError
from ..job_utils import ETA_SEC, create_job, queue_position
from ..schemas.jobs import JobCreatedResponse
from ..schemas.process import MixRequest, PitchRequest, SeparateRequest, TempoRequest

router = APIRouter()


def _record_cache_hit(db, job_type: str, body, user: User, cached_ids: list[str]) -> Job | None:
    """캐시된 결과물을 요청자 명의로 복제하고 즉시 완료된 작업으로 기록한다.
    캐시가 가리키는 행이 이미 지워졌으면 None — 호출부는 캐시 미스로 처리한다."""
    output_ids = []
    for media_id in cached_ids:
        cloned = clone_media_for_user(db, media_id, user.id, parent_id=body.media_id)
        if cloned is None:
            db.rollback()
            return None
        output_ids.append(cloned)
    db.commit()

    job = create_job(db, job_type, body.media_id, body.model_dump(), user_id=user.id)
    job.status = "succeeded"
    job.output_media = output_ids
    job.cache_hit = True
    job.progress = 100
    db.commit()
    return job


@router.post("/separate", response_model=JobCreatedResponse, dependencies=[Depends(enforce_separate_quota)])
def process_separate(body: SeparateRequest, current_user: User = Depends(require_user)) -> JobCreatedResponse:
    if body.stems != 2:
        raise ApiError("VALIDATION_ERROR", "MVP는 2스템(보컬/반주) 분리만 지원합니다.", {"stems": body.stems})

    settings = get_settings()
    db = SessionLocal()
    try:
        media = get_accessible_media(db, body.media_id, current_user)
        model_name = settings.demucs_fast_model if body.quality == "fast" else settings.demucs_hq_model

        cached = cache_get(l2_key(media.content_hash, model_name, body.stems))
        if cached:
            # 순서가 중요하다 — 스튜디오는 outputs[0]=보컬, [1]=반주로 읽는다.
            cached_ids = [cached.get("vocals_media_id"), cached.get("instrumental_media_id")]
            if all(cached_ids):
                job = _record_cache_hit(db, "separate", body, current_user, cached_ids)
                if job:
                    return JobCreatedResponse(job_id=job.id, status="succeeded", cached=True)

        job = create_job(db, "separate", body.media_id, body.model_dump(), user_id=current_user.id)
    finally:
        db.close()

    send_task("tasks.separate_stems", args=[job.id], queue="separate")

    eta = ETA_SEC["separate_high"] if body.quality == "high" else ETA_SEC["separate_fast"]
    return JobCreatedResponse(
        job_id=job.id, status="queued", queue_position=queue_position("separate"), eta_sec=eta, cached=False
    )


@router.post("/pitch", response_model=JobCreatedResponse)
def process_pitch(body: PitchRequest, current_user: User = Depends(require_user)) -> JobCreatedResponse:
    db = SessionLocal()
    try:
        media = get_accessible_media(db, body.media_id, current_user)

        cached = cache_get(pitch_key(media.content_hash, body.semitones, body.stem_type, body.preview))
        if cached and cached.get("media_id"):
            job = _record_cache_hit(db, "pitch", body, current_user, [cached["media_id"]])
            if job:
                return JobCreatedResponse(job_id=job.id, status="succeeded", cached=True)

        job = create_job(db, "pitch", body.media_id, body.model_dump(), user_id=current_user.id)
    finally:
        db.close()

    send_task("tasks.pitch_shift_stems", args=[job.id], queue="dsp")
    return JobCreatedResponse(
        job_id=job.id, status="queued", queue_position=queue_position("pitch"), eta_sec=ETA_SEC["pitch"]
    )


@router.post("/tempo", response_model=JobCreatedResponse)
def process_tempo(body: TempoRequest, current_user: User = Depends(require_user)) -> JobCreatedResponse:
    db = SessionLocal()
    try:
        media = get_accessible_media(db, body.media_id, current_user)

        cached = cache_get(tempo_key(media.content_hash, body.ratio))
        if cached and cached.get("media_id"):
            job = _record_cache_hit(db, "tempo", body, current_user, [cached["media_id"]])
            if job:
                return JobCreatedResponse(job_id=job.id, status="succeeded", cached=True)

        job = create_job(db, "tempo", body.media_id, body.model_dump(), user_id=current_user.id)
    finally:
        db.close()

    send_task("tasks.time_stretch_stems", args=[job.id], queue="dsp")
    return JobCreatedResponse(
        job_id=job.id, status="queued", queue_position=queue_position("tempo"), eta_sec=ETA_SEC["tempo"]
    )


@router.post("/mix", response_model=JobCreatedResponse)
def process_mix(body: MixRequest, current_user: User = Depends(require_user)) -> JobCreatedResponse:
    if body.gains is not None and len(body.gains) != len(body.media_ids):
        raise ApiError(
            "VALIDATION_ERROR",
            "gains 개수가 media_ids 개수와 달라요.",
            {"media_ids": len(body.media_ids), "gains": len(body.gains)},
        )

    db = SessionLocal()
    try:
        for media_id in body.media_ids:
            get_accessible_media(db, media_id, current_user)
        job = create_job(db, "mix", body.media_ids[0], body.model_dump(), user_id=current_user.id)
    finally:
        db.close()

    send_task("tasks.mix_stems", args=[job.id], queue="dsp")
    return JobCreatedResponse(
        job_id=job.id, status="queued", queue_position=queue_position("mix"), eta_sec=ETA_SEC["mix"]
    )
