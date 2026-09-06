"""§9.2 Celery queue routing.

Separation runs on CUDA in this local stack (NVIDIA GPU host). The `-P solo`
worker pool still processes one Demucs job at a time in-process — the GPU
itself is the bottleneck resource, so there's no benefit to more concurrency
here, and it keeps memory bounded on a dev machine.
"""

from celery import Celery
from kombu import Queue

from common.config import get_settings

settings = get_settings()

app = Celery("studio", broker=settings.redis_url, backend=settings.redis_url)

app.conf.task_queues = (
    Queue("download", routing_key="download.#"),
    Queue("separate", routing_key="separate.#"),
    Queue("dsp", routing_key="dsp.#"),
    Queue("separate_priority", routing_key="separate.pro.#"),
)

app.conf.task_routes = {
    "tasks.extract_youtube": {"queue": "download"},
    "tasks.separate_stems": {"queue": "separate"},
    "tasks.pitch_shift_stems": {"queue": "dsp"},
    "tasks.time_stretch_stems": {"queue": "dsp"},
    "tasks.mix_stems": {"queue": "dsp"},
    "tasks.analyze_media": {"queue": "dsp"},
    "tasks.canary_healthcheck": {"queue": "dsp"},
    "tasks.purge_expired_media": {"queue": "dsp"},
}

app.conf.task_track_started = True
app.conf.task_acks_late = True
app.conf.worker_prefetch_multiplier = 1
app.conf.timezone = "UTC"
app.conf.broker_connection_retry_on_startup = True

app.conf.beat_schedule = {
    "canary-healthcheck": {
        "task": "tasks.canary_healthcheck",
        "schedule": 300.0,  # 5 min, §5.1.3
    },
    "purge-expired-media": {
        "task": "tasks.purge_expired_media",
        "schedule": 900.0,  # 15 min, TTL cleanup
    },
}

app.autodiscover_tasks(["workers"], related_name="tasks")
