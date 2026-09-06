import os
import tempfile

from common.cache import L2_TTL, cache_get, cache_set, l2_key
from common.config import get_settings
from common.db.models import Media
from common.db.session import session_scope
from common.storage import download_file, upload_file

from ..celery_app import app
from ..job_lifecycle import mark_failed, mark_progress, mark_running, mark_succeeded, register_media
from ..separation.separator import load_model, save_stem, separate

QUALITY_MODEL = {"fast": "demucs_fast_model", "high": "demucs_hq_model"}


@app.task(name="tasks.separate_stems", bind=True, max_retries=1)
def separate_stems(self, job_id: str) -> dict:
    settings = get_settings()

    with session_scope() as db:
        from common.db.models import Job

        job = db.get(Job, job_id)
        params = dict(job.params)
        user_id = job.user_id
        media = db.get(Media, params["media_id"])
        source_hash = media.content_hash
        storage_key = media.storage_key
        source_title = media.title
        source_artist = media.artist

    stems = int(params.get("stems", 2))
    quality = params.get("quality", "fast")
    model_name = getattr(settings, QUALITY_MODEL.get(quality, "demucs_fast_model"))

    mark_running(job_id)

    cache_key = l2_key(source_hash, model_name, stems)
    cached = cache_get(cache_key)
    if cached:
        mark_succeeded(job_id, [cached["vocals_media_id"], cached["instrumental_media_id"]], cache_hit=True)
        return cached

    work_dir = tempfile.mkdtemp(prefix="sep_")
    try:
        local_src = os.path.join(work_dir, "source")
        download_file(storage_key, local_src)

        mark_progress(job_id, 5, "separating")
        model = load_model(model_name)  # cached — separate() below loads the same instance
        result = separate(local_src, model_name, stems)
        mark_progress(job_id, 80, "separating")

        output_ids: dict[str, str] = {}
        for stem_name, tensor in result.items():
            local_out = os.path.join(work_dir, f"{stem_name}.wav")
            save_stem(tensor, local_out, sample_rate=model.samplerate)

            stem_key = f"separated/{source_hash}/{model_name}/{stem_name}.wav"
            upload_file(local_out, stem_key, "audio/wav")

            media_id = register_media(
                kind="stem",
                source_type="derived",
                parent_id=params["media_id"],
                content_hash=f"{source_hash}:{model_name}:{stem_name}",
                storage_key=stem_key,
                mime_type="audio/wav",
                size_bytes=os.path.getsize(local_out),
                title=source_title,
                artist=source_artist,
                lineage={"op": "separate", "model": model_name, "stem": stem_name, "stems": stems},
                user_id=user_id,
            )
            output_ids[stem_name] = media_id

        cache_payload = {
            "vocals_media_id": output_ids.get("vocals"),
            "instrumental_media_id": output_ids.get("instrumental"),
            **{f"{k}_media_id": v for k, v in output_ids.items() if k not in ("vocals", "instrumental")},
        }
        cache_set(cache_key, cache_payload, L2_TTL)

        mark_succeeded(job_id, list(output_ids.values()))
        return cache_payload

    except Exception as exc:
        code = "GPU_OOM" if "out of memory" in str(exc).lower() else "EXTRACTION_FAILED"
        mark_failed(job_id, code, str(exc))
        raise
    finally:
        import shutil

        shutil.rmtree(work_dir, ignore_errors=True)
