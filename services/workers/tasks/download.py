import glob
import os
import shutil
import tempfile

from yt_dlp import DownloadError, YoutubeDL

from common.cache import L1_TTL, cache_set, content_hash, l1_key
from common.db.models import Job
from common.db.session import session_scope
from common.ffprobe import probe
from common.storage import upload_file
from common.ytdlp import CLIENT_FALLBACK_CHAIN, classify_youtube_error, is_permanent_error

from ..celery_app import app
from ..download.ytdlp_config import audio_opts, video_opts
from ..job_lifecycle import (
    BACKOFF_SEC,
    mark_failed,
    mark_progress,
    mark_running,
    mark_succeeded,
    register_media,
)

MIME_TYPES = {"mp3": "audio/mpeg", "wav": "audio/wav", "m4a": "audio/mp4", "mp4": "video/mp4"}


@app.task(name="tasks.extract_youtube", bind=True, max_retries=3)
def extract_youtube(self, job_id: str) -> dict:
    with session_scope() as db:
        job = db.get(Job, job_id)
        params = dict(job.params)
        user_id = job.user_id

    mark_running(job_id)
    mark_progress(job_id, 1, "downloading")  # immediate feedback — the client fallback loop below can take a while
    url, video_id = params["url"], params["video_id"]
    kind, format_id = params["kind"], params["format_id"]

    out_dir = tempfile.mkdtemp(prefix="dl_")
    try:
        info = None
        last_error: Exception | None = None
        for client in CLIENT_FALLBACK_CHAIN:
            opts = (audio_opts if kind == "audio" else video_opts)(job_id, format_id, out_dir, client)
            try:
                with YoutubeDL(opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                break
            except DownloadError as exc:  # §5.1.3 — try next client in the chain
                last_error = exc
                if is_permanent_error(str(exc)):
                    # DRM/unavailable/private is a property of the video, not the
                    # client — every other client would fail the same way, so
                    # don't waste time (and re-download bytes) trying them.
                    break
                continue
        if info is None:
            raise last_error or RuntimeError("yt-dlp extraction failed for all clients")

        candidates = [
            f for f in glob.glob(f"{out_dir}/*") if not f.endswith((".jpg", ".webp", ".png", ".part"))
        ]
        if not candidates:
            raise RuntimeError("no output file produced")
        local_path = max(candidates, key=os.path.getsize)
        ext = local_path.rsplit(".", 1)[-1].lower()

        meta = probe(local_path)
        file_hash = content_hash(local_path)
        size_bytes = os.path.getsize(local_path)
        mime_type = MIME_TYPES.get(ext, "application/octet-stream")

        storage_key = f"youtube/{video_id}/{format_id}.{ext}"
        upload_file(local_path, storage_key, mime_type)

        media_id = register_media(
            kind="source",
            source_type="youtube",
            parent_id=None,
            content_hash=file_hash,
            storage_key=storage_key,
            mime_type=mime_type,
            size_bytes=size_bytes,
            duration_sec=meta["duration_sec"],
            sample_rate=meta["sample_rate"],
            channels=meta["channels"],
            yt_video_id=video_id,
            title=info.get("title"),
            artist=info.get("channel") or info.get("uploader"),
            lineage={"op": "youtube_extract", "kind": kind, "format_id": format_id},
            user_id=user_id,
        )

        cache_set(l1_key(video_id, kind, format_id), {"media_id": media_id, "job_id": job_id}, L1_TTL)
        mark_succeeded(job_id, [media_id])
        return {"media_id": media_id}

    except Exception as exc:
        code = classify_youtube_error(str(exc))
        retryable = mark_failed(job_id, code, str(exc))
        if retryable:
            attempt = self.request.retries
            raise self.retry(exc=exc, countdown=BACKOFF_SEC[min(attempt, len(BACKOFF_SEC) - 1)])
        raise
    finally:
        shutil.rmtree(out_dir, ignore_errors=True)
