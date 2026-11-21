import os
import shutil
import tempfile

from common.cache import L2_TTL, cache_get, cache_set, l2_key
from common.config import get_settings
from common.db.models import Job, Media
from common.db.session import session_scope
from common.storage import download_file, upload_file

from ..celery_app import app
from ..job_lifecycle import claim_cached_outputs, mark_failed, mark_progress, mark_running, mark_succeeded, register_media
from ..separation.karaoke import split_lead_backing


@app.task(name="tasks.split_vocals", bind=True, max_retries=1)
def split_vocals(self, job_id: str) -> dict:
    model_name = get_settings().karaoke_model

    with session_scope() as db:
        job = db.get(Job, job_id)
        media_id = job.params["media_id"]
        user_id = job.user_id
        media = db.get(Media, media_id)
        vocals_hash = media.content_hash
        storage_key = media.storage_key
        title = media.title
        artist = media.artist

    mark_running(job_id)

    cache_key = l2_key(vocals_hash, model_name, 2)
    cached = cache_get(cache_key)
    if cached:
        output_ids = claim_cached_outputs(
            [cached.get("lead_media_id"), cached.get("backing_media_id")], user_id, media_id
        )
        if output_ids:
            mark_succeeded(job_id, output_ids, cache_hit=True)
            return {"lead_media_id": output_ids[0], "backing_media_id": output_ids[1]}

    work_dir = tempfile.mkdtemp(prefix="karaoke_")
    try:
        local_src = os.path.join(work_dir, "vocals.wav")
        download_file(storage_key, local_src)

        mark_progress(job_id, 10, "splitting_vocals")
        paths = split_lead_backing(local_src, os.path.join(work_dir, "out"))
        mark_progress(job_id, 85, "splitting_vocals")

        # The content hash of a stem is "<source>:<model>:<stem>" — colons are
        # legal in S3 keys, but path segments keep the bucket browsable.
        key_prefix = f"separated/{vocals_hash.replace(':', '/')}/{model_name.rsplit('.', 1)[0]}"
        output_ids: dict[str, str] = {}
        for stem in ("lead", "backing"):
            stem_key = f"{key_prefix}/{stem}.wav"
            upload_file(paths[stem], stem_key, "audio/wav")
            output_ids[stem] = register_media(
                kind="stem",
                source_type="derived",
                parent_id=media_id,
                content_hash=f"{vocals_hash}:{model_name}:{stem}",
                storage_key=stem_key,
                mime_type="audio/wav",
                size_bytes=os.path.getsize(paths[stem]),
                title=title,
                artist=artist,
                lineage={"op": "separate", "model": model_name, "stem": stem},
                user_id=user_id,
            )

        payload = {"lead_media_id": output_ids["lead"], "backing_media_id": output_ids["backing"]}
        cache_set(cache_key, payload, L2_TTL)

        # 순서가 중요하다 — 화면은 outputs[0]=리드, [1]=코러스로 읽는다.
        mark_succeeded(job_id, [output_ids["lead"], output_ids["backing"]])
        return payload
    except Exception as exc:
        mark_failed(job_id, "SEPARATION_FAILED", str(exc))
        raise
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)
