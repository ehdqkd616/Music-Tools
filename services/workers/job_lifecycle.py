"""Job status transitions shared by every Celery task (§9.1 state machine)."""

from datetime import datetime, timezone

from common.cache import publish_progress
from common.db.models import Job
from common.db.session import session_scope
from common.media_registry import clone_media_for_user
from common.media_registry import register_media  # noqa: F401 — re-exported for task modules

RETRYABLE_CODES = {"EXTRACTION_FAILED", "RATE_LIMITED", "QUEUE_FULL", "GPU_OOM"}
MAX_ATTEMPTS = 3
BACKOFF_SEC = [2, 8, 32]


def claim_cached_outputs(media_ids: list[str | None], user_id, parent_id: str | None) -> list[str] | None:
    """캐시 적중 결과물을 이 작업의 요청자 명의로 복제한다 (API 쪽 캐시 처리와 같은 규칙).
    하나라도 이미 지워졌으면 None — 호출부는 캐시 미스로 보고 새로 처리한다."""
    if not all(media_ids):
        return None
    with session_scope() as db:
        output_ids = []
        for media_id in media_ids:
            cloned = clone_media_for_user(db, media_id, user_id, parent_id=parent_id)
            if cloned is None:
                db.rollback()
                return None
            output_ids.append(cloned)
    return output_ids


def mark_running(job_id: str) -> None:
    with session_scope() as db:
        job = db.get(Job, job_id)
        job.status = "running"
        job.started_at = datetime.now(timezone.utc)


def mark_progress(job_id: str, percent: float, stage: str) -> None:
    with session_scope() as db:
        job = db.get(Job, job_id)
        job.progress = percent
    publish_progress(job_id, {"stage": stage, "percent": percent})


def mark_succeeded(job_id: str, output_media: list[str], cache_hit: bool = False) -> None:
    with session_scope() as db:
        job = db.get(Job, job_id)
        job.status = "succeeded"
        job.output_media = output_media
        job.cache_hit = cache_hit
        job.progress = 100
        job.finished_at = datetime.now(timezone.utc)
    publish_progress(
        job_id,
        {
            "event": "complete",
            "status": "succeeded",
            "outputs": [{"media_id": m} for m in output_media],
        },
    )


def mark_failed(job_id: str, code: str, message: str, detail: dict | None = None) -> bool:
    """Returns True if the caller should retry (attempts remain and code is retryable)."""
    with session_scope() as db:
        job = db.get(Job, job_id)
        job.attempts += 1
        retryable = code in RETRYABLE_CODES and job.attempts < MAX_ATTEMPTS
        job.status = "queued" if retryable else "failed"
        job.error_code = code
        job.error_message = message
        attempts = job.attempts
    publish_progress(
        job_id,
        {
            "event": "error",
            "code": code,
            "message": message,
            "detail": detail or {},
            "retryable": retryable,
        },
    )
    return retryable
