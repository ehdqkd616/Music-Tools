import os
import tempfile

from fastapi import APIRouter, Depends

from common.cache import L3_TTL, cache_get, cache_set, l3_key
from common.db.models import Analysis, User
from common.db.session import SessionLocal
from common.storage import download_file

from ..deps import get_accessible_media, require_user
from ..schemas.process import AnalyzeResponse

router = APIRouter()


@router.get("/{media_id}", response_model=AnalyzeResponse)
def analyze(media_id: str, current_user: User = Depends(require_user)) -> AnalyzeResponse:
    db = SessionLocal()
    try:
        media = get_accessible_media(db, media_id, current_user)
        content_hash = media.content_hash

        cached = cache_get(l3_key(content_hash))
        if cached:
            return _response(content_hash, cached, cached=True)

        row = db.get(Analysis, content_hash)
        if row:
            payload = {
                "tonic": row.key_tonic,
                "mode": row.key_mode,
                "confidence": row.key_conf,
                "bpm": row.bpm,
                "lufs_integrated": row.lufs,
                "true_peak_db": row.true_peak_db,
            }
            cache_set(l3_key(content_hash), payload, L3_TTL)
            return _response(content_hash, payload, cached=True)

        storage_key = media.storage_key
    finally:
        db.close()

    # §5.2.4 — analysis is fast (seconds), so §7.1's "동기" GET runs it inline.
    from common.analysis import analyze_file  # heavy import kept local to this path

    work_dir = tempfile.mkdtemp(prefix="analyze_")
    try:
        local_path = os.path.join(work_dir, "source")
        download_file(storage_key, local_path)
        result = analyze_file(local_path)
    finally:
        import shutil

        shutil.rmtree(work_dir, ignore_errors=True)

    db = SessionLocal()
    try:
        db.merge(
            Analysis(
                content_hash=content_hash,
                key_tonic=result["tonic"],
                key_mode=result["mode"],
                key_conf=result["confidence"],
                bpm=result["bpm"],
                beat_times=result["beat_times"],
                lufs=result["lufs_integrated"],
                true_peak_db=result["true_peak_db"],
            )
        )
        db.commit()
    finally:
        db.close()

    cache_set(l3_key(content_hash), result, L3_TTL)
    return _response(content_hash, result, cached=False)


def _response(content_hash: str, data: dict, cached: bool) -> AnalyzeResponse:
    tonic, mode = data.get("tonic"), data.get("mode")
    key = f"{tonic} {mode.capitalize()}" if tonic and mode else None
    return AnalyzeResponse(
        content_hash=content_hash,
        key=key,
        key_tonic=tonic,
        key_mode=mode,
        key_confidence=data.get("confidence"),
        bpm=data.get("bpm"),
        lufs_integrated=data.get("lufs_integrated"),
        true_peak_db=data.get("true_peak_db"),
        cached=cached,
    )
