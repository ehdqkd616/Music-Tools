"""Job status transitions shared by every Celery task (§9.1 state machine)."""

from datetime import datetime, timezone

from common.cache import publish_progress
from common.db.models import Job
from common.db.session import session_scope
from common.media_registry import register_media  # noqa: F401 — re-exported for task modules

RETRYABLE_CODES = {"EXTRACTION_FAILED", "RATE_LIMITED", "QUEUE_FULL", "GPU_OOM"}
MAX_ATTEMPTS = 3
BACKOFF_SEC = [2, 8, 32]


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
