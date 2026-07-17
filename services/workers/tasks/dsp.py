import os
import shutil
import tempfile

import numpy as np
import soundfile as sf

from common.audio_convert import encode, ensure_wav
from common.cache import L3_TTL, cache_get, cache_set, content_hash, l3_key
from common.db.models import Analysis, Job, Media
from common.db.session import session_scope
from common.ffprobe import probe
from common.storage import download_file, upload_file

from ..celery_app import app
from ..dsp.analyze import analyze_file
from ..dsp.pitch import pitch_shift, time_stretch
from ..job_lifecycle import mark_failed, mark_progress, mark_running, mark_succeeded, register_media


def _load_job(job_id: str) -> tuple[dict, Media]:
    with session_scope() as db:
        job = db.get(Job, job_id)
        params = dict(job.params)
        media = db.get(Media, params["media_id"])
        media_snapshot = Media(**{c.name: getattr(media, c.name) for c in Media.__table__.columns})
    return params, media_snapshot


@app.task(name="tasks.pitch_shift_stems", bind=True, max_retries=1)
def pitch_shift_stems(self, job_id: str) -> dict:
    params, media = _load_job(job_id)
    mark_running(job_id)
    work_dir = tempfile.mkdtemp(prefix="pitch_")
    try:
        local_src = os.path.join(work_dir, f"source.{media.mime_type.split('/')[-1]}")
        download_file(media.storage_key, local_src)
        wav_src = ensure_wav(local_src)

        mark_progress(job_id, 30, "pitch_shifting")
        semitones = float(params["semitones"])
        stem_type = params.get("stem_type", "other")
        out_path = os.path.join(work_dir, "out.wav")
        pitch_shift(wav_src, out_path, semitones, stem_type)

        meta = probe(out_path)
        out_hash = content_hash(out_path)
        storage_key = f"processed/{out_hash}.wav"
        upload_file(out_path, storage_key, "audio/wav")

        media_id = register_media(
            kind="processed",
            source_type="derived",
            parent_id=media.id,
            content_hash=out_hash,
            storage_key=storage_key,
            mime_type="audio/wav",
            size_bytes=os.path.getsize(out_path),
            duration_sec=meta["duration_sec"],
            sample_rate=meta["sample_rate"],
            channels=meta["channels"],
            lineage={
                "op": "pitch",
                "semitones": semitones,
                "formant": stem_type == "vocals",
                "engine": "rubberband-r3",
            },
        )
        mark_succeeded(job_id, [media_id])
        return {"media_id": media_id}
    except Exception as exc:
        mark_failed(job_id, "EXTRACTION_FAILED", str(exc))
        raise
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


@app.task(name="tasks.time_stretch_stems", bind=True, max_retries=1)
def time_stretch_stems(self, job_id: str) -> dict:
    params, media = _load_job(job_id)
    mark_running(job_id)
    work_dir = tempfile.mkdtemp(prefix="tempo_")
    try:
        local_src = os.path.join(work_dir, f"source.{media.mime_type.split('/')[-1]}")
        download_file(media.storage_key, local_src)
        wav_src = ensure_wav(local_src)

        mark_progress(job_id, 30, "time_stretching")
        ratio = float(params["ratio"])
        out_path = os.path.join(work_dir, "out.wav")
        time_stretch(wav_src, out_path, ratio)

        meta = probe(out_path)
        out_hash = content_hash(out_path)
        storage_key = f"processed/{out_hash}.wav"
        upload_file(out_path, storage_key, "audio/wav")

        media_id = register_media(
            kind="processed",
            source_type="derived",
            parent_id=media.id,
            content_hash=out_hash,
            storage_key=storage_key,
            mime_type="audio/wav",
            size_bytes=os.path.getsize(out_path),
            duration_sec=meta["duration_sec"],
            sample_rate=meta["sample_rate"],
            channels=meta["channels"],
            lineage={"op": "tempo", "ratio": ratio, "engine": "rubberband-r3"},
        )
        mark_succeeded(job_id, [media_id])
        return {"media_id": media_id}
    except Exception as exc:
        mark_failed(job_id, "EXTRACTION_FAILED", str(exc))
        raise
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


@app.task(name="tasks.mix_stems", bind=True, max_retries=1)
def mix_stems(self, job_id: str) -> dict:
    with session_scope() as db:
        job = db.get(Job, job_id)
        params = dict(job.params)
        media_rows = [db.get(Media, mid) for mid in params["media_ids"]]
        media_snapshots = [
            Media(**{c.name: getattr(m, c.name) for c in Media.__table__.columns}) for m in media_rows
        ]

    mark_running(job_id)
    work_dir = tempfile.mkdtemp(prefix="mix_")
    try:
        arrays = []
        sr = None
        for i, media in enumerate(media_snapshots):
            local_path = os.path.join(work_dir, f"stem_{i}.wav")
            download_file(media.storage_key, local_path)
            wav_path = ensure_wav(local_path)
            data, file_sr = sf.read(wav_path, always_2d=True)
            sr = sr or file_sr
            arrays.append(data)
        mark_progress(job_id, 50, "mixing")

        max_len = max(a.shape[0] for a in arrays)
        mixed = np.zeros((max_len, arrays[0].shape[1]), dtype=np.float32)
        for a in arrays:
            mixed[: a.shape[0]] += a
        peak = np.abs(mixed).max()
        if peak > 1.0:
            mixed = mixed / peak  # simple clip-safety normalization

        mixed_wav = os.path.join(work_dir, "mixed.wav")
        sf.write(mixed_wav, mixed, sr)

        output_format = params.get("output_format", "mp3-320")
        ext = "wav" if output_format == "wav" else "mp3"
        final_path = os.path.join(work_dir, f"final.{ext}")
        encode(mixed_wav, final_path, output_format)

        meta = probe(final_path)
        out_hash = content_hash(final_path)
        mime = "audio/wav" if ext == "wav" else "audio/mpeg"
        storage_key = f"processed/{out_hash}.{ext}"
        upload_file(final_path, storage_key, mime)

        media_id = register_media(
            kind="processed",
            source_type="derived",
            parent_id=media_snapshots[0].id,
            content_hash=out_hash,
            storage_key=storage_key,
            mime_type=mime,
            size_bytes=os.path.getsize(final_path),
            duration_sec=meta["duration_sec"],
            sample_rate=meta["sample_rate"],
            channels=meta["channels"],
            lineage={"op": "mix", "sources": params["media_ids"], "output_format": output_format},
        )
        mark_succeeded(job_id, [media_id])
        return {"media_id": media_id}
    except Exception as exc:
        mark_failed(job_id, "EXTRACTION_FAILED", str(exc))
        raise
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


@app.task(name="tasks.analyze_media", bind=True, max_retries=1)
def analyze_media(self, media_id: str) -> dict:
    """Async variant of the synchronous GET /analyze/{media_id} path (§7.1) —
    available for chained workflows; the API route calls analyze_file() inline
    since analysis usually finishes in a few seconds."""
    with session_scope() as db:
        media = db.get(Media, media_id)
        storage_key, source_hash = media.storage_key, media.content_hash

    cached = cache_get(l3_key(source_hash))
    if cached:
        return cached

    work_dir = tempfile.mkdtemp(prefix="analyze_")
    try:
        local_path = os.path.join(work_dir, "source")
        download_file(storage_key, local_path)
        result = analyze_file(local_path)

        with session_scope() as db:
            db.merge(
                Analysis(
                    content_hash=source_hash,
                    key_tonic=result["tonic"],
                    key_mode=result["mode"],
                    key_conf=result["confidence"],
                    bpm=result["bpm"],
                    beat_times=result["beat_times"],
                    lufs=result["lufs_integrated"],
                    true_peak_db=result["true_peak_db"],
                )
            )
        cache_set(l3_key(source_hash), result, L3_TTL)
        return result
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)
