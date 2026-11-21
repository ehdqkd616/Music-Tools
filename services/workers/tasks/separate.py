import os
import tempfile

from common.cache import L2_TTL, cache_get, cache_set, l2_key
from common.config import get_settings
from common.db.models import Media
from common.db.session import session_scope
from common.audio_convert import encode
from common.stems import STEM_ORDER, cached_output_ids, has_previews, output_names, separation_model
from common.storage import download_file, upload_file

from ..celery_app import app
from ..job_lifecycle import claim_cached_outputs, mark_failed, mark_progress, mark_running, mark_succeeded, register_media
from ..separation.separator import load_model, save_stem, separate

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
    model_name = separation_model(settings, stems, quality)

    mark_running(job_id)

    cache_key = l2_key(source_hash, model_name, stems)
    cached = cache_get(cache_key)
    if cached:
        output_ids = claim_cached_outputs(cached_output_ids(cached, stems), user_id, params["media_id"])
        if output_ids:
            mark_succeeded(job_id, output_ids, cache_hit=True)
            return dict(zip([f"{name}_media_id" for name in output_names(stems)], output_ids))

    work_dir = tempfile.mkdtemp(prefix="sep_")
    try:
        local_src = os.path.join(work_dir, "source")
        download_file(storage_key, local_src)

        mark_progress(job_id, 5, "separating")
        model = load_model(model_name)  # cached — separate() below loads the same instance
        result = separate(local_src, model_name, stems)
        mark_progress(job_id, 80, "separating")

        output_ids: dict[str, str] = {}
        for stem_name in STEM_ORDER[stems]:
            tensor = result[stem_name]
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

            if has_previews(stems):
                preview_out = os.path.join(work_dir, f"{stem_name}.mp3")
                encode(local_out, preview_out, "mp3-192")
                preview_key = f"separated/{source_hash}/{model_name}/{stem_name}.mp3"
                upload_file(preview_out, preview_key, "audio/mpeg")
                output_ids[f"{stem_name}_preview"] = register_media(
                    kind="stem",
                    source_type="derived",
                    parent_id=params["media_id"],
                    content_hash=f"{source_hash}:{model_name}:{stem_name}:mp3",
                    storage_key=preview_key,
                    mime_type="audio/mpeg",
                    size_bytes=os.path.getsize(preview_out),
                    title=source_title,
                    artist=source_artist,
                    lineage={"op": "separate", "model": model_name, "stem": stem_name, "stems": stems, "preview": True},
                    user_id=user_id,
                )

        cache_payload = {f"{name}_media_id": output_ids[name] for name in output_names(stems)}
        cache_set(cache_key, cache_payload, L2_TTL)

        # 순서가 중요하다 — 화면은 outputs를 output_names(stems) 순서로 읽는다.
        mark_succeeded(job_id, [output_ids[name] for name in output_names(stems)])
        return cache_payload

    except Exception as exc:
        code = "GPU_OOM" if "out of memory" in str(exc).lower() else "EXTRACTION_FAILED"
        mark_failed(job_id, code, str(exc))
        raise
    finally:
        import shutil

        shutil.rmtree(work_dir, ignore_errors=True)
