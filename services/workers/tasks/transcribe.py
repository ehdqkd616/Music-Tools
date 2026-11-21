import os
import shutil
import tempfile

from common.audio_convert import ensure_wav
from common.cache import L2_TTL, cache_get, cache_set, transcribe_key
from common.db.models import Job, Media
from common.db.session import session_scope
from common.storage import download_file, upload_file

from ..celery_app import app
from ..job_lifecycle import claim_cached_outputs, mark_failed, mark_progress, mark_running, mark_succeeded, register_media
from ..transcription.notation import beat_grid, build_score, render_pdf
from ..transcription.piano import SAMPLE_RATE, transcribe

# Bump when the transcription or notation output changes, so old cache entries
# and storage keys aren't reused.
PIPELINE_VERSION = "piano-v1"

# 순서가 중요하다 — 화면은 outputs를 [MIDI, MusicXML, PDF]로 읽는다.
OUTPUTS = (
    ("midi", "piano.mid", "audio/midi"),
    ("musicxml", "score.musicxml", "application/vnd.recordare.musicxml+xml"),
    ("pdf", "score.pdf", "application/pdf"),
)


class NoNotesDetected(Exception):
    pass


@app.task(name="tasks.transcribe_piano", bind=True, max_retries=1)
def transcribe_piano(self, job_id: str) -> dict:
    import librosa

    with session_scope() as db:
        job = db.get(Job, job_id)
        media_id = job.params["media_id"]
        user_id = job.user_id
        media = db.get(Media, media_id)
        source_hash = media.content_hash
        storage_key = media.storage_key
        mime_type = media.mime_type
        title = media.title
        artist = media.artist

    mark_running(job_id)

    cache_key = transcribe_key(source_hash, PIPELINE_VERSION)
    cached = cache_get(cache_key)
    if cached:
        output_ids = claim_cached_outputs([cached.get(f"{name}_media_id") for name, _, _ in OUTPUTS], user_id, media_id)
        if output_ids:
            mark_succeeded(job_id, output_ids, cache_hit=True)
            return dict(zip([f"{name}_media_id" for name, _, _ in OUTPUTS], output_ids))

    work_dir = tempfile.mkdtemp(prefix="transcribe_")
    try:
        local_src = os.path.join(work_dir, f"source.{mime_type.split('/')[-1]}")
        download_file(storage_key, local_src)
        audio, _ = librosa.load(ensure_wav(local_src), sr=SAMPLE_RATE, mono=True)

        mark_progress(job_id, 5, "transcribing")
        paths = {name: os.path.join(work_dir, filename) for name, filename, _ in OUTPUTS}
        events = transcribe(audio, paths["midi"])
        if not events:
            raise NoNotesDetected()

        mark_progress(job_id, 80, "engraving")
        bpm, beats = beat_grid(audio, SAMPLE_RATE)
        score, detected_key = build_score(events, bpm, beats, title)
        score.write("musicxml", fp=paths["musicxml"])
        pages = render_pdf(paths["musicxml"], paths["pdf"])
        mark_progress(job_id, 95, "engraving")

        output_ids: dict[str, str] = {}
        for name, filename, mime in OUTPUTS:
            key = f"transcribed/{source_hash}/{PIPELINE_VERSION}/{filename}"
            upload_file(paths[name], key, mime)
            output_ids[name] = register_media(
                kind="processed",
                source_type="derived",
                parent_id=media_id,
                content_hash=f"{source_hash}:{PIPELINE_VERSION}:{name}",
                storage_key=key,
                mime_type=mime,
                size_bytes=os.path.getsize(paths[name]),
                title=title,
                artist=artist,
                lineage={
                    "op": "transcribe",
                    "format": name,
                    "pipeline": PIPELINE_VERSION,
                    "notes": len(events),
                    "bpm": round(bpm, 1),
                    "key": detected_key.name,
                    "pages": pages,
                },
                user_id=user_id,
            )

        payload = {f"{name}_media_id": output_ids[name] for name, _, _ in OUTPUTS}
        cache_set(cache_key, payload, L2_TTL)
        mark_succeeded(job_id, [output_ids[name] for name, _, _ in OUTPUTS])
        return payload
    except NoNotesDetected:
        mark_failed(job_id, "NO_NOTES_DETECTED", "no piano notes were detected")
        raise
    except Exception as exc:
        mark_failed(job_id, "TRANSCRIPTION_FAILED", str(exc))
        raise
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)
