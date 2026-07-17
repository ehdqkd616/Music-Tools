from sqlalchemy.orm import Session

from common.db.models import Job
from common.ids import new_id
from common.redis_client import get_redis

# Rough ETA table (seconds) for a ~4min track, per §13 performance targets.
ETA_SEC = {
    "extract": 20,
    "separate_fast": 60,
    "separate_high": 180,
    "pitch": 15,
    "tempo": 15,
    "mix": 10,
}

QUEUE_NAME = {
    "extract": "download",
    "separate": "separate",
    "pitch": "dsp",
    "tempo": "dsp",
    "mix": "dsp",
}


def create_job(db: Session, job_type: str, input_media: str | None, params: dict) -> Job:
    job = Job(id=new_id("job"), type=job_type, status="queued", input_media=input_media, params=params)
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def queue_position(job_type: str) -> int:
    queue = QUEUE_NAME.get(job_type, "dsp")
    return get_redis().llen(queue)
