"""§5.1.3 canary healthcheck + circuit breaker, §5.3/§15.2 TTL cleanup."""

from datetime import datetime, timezone

from sqlalchemy import delete

from common.db.models import Media
from common.db.session import session_scope
from common.media_registry import collect_descendants, delete_unreferenced_objects
from common.redis_client import get_redis
from common.ytdlp import fetch_info

from ..celery_app import app

# A short, stable Creative Commons video used purely to detect yt-dlp/bot-detection breakage.
CANARY_URL = "https://www.youtube.com/watch?v=jNQXAC9IVRw"
CANARY_FAIL_THRESHOLD = 3
CANARY_STREAK_KEY = "canary:fail_streak"
CIRCUIT_KEY = "circuit:download_disabled"


@app.task(name="tasks.canary_healthcheck")
def canary_healthcheck() -> dict:
    r = get_redis()
    try:
        fetch_info(CANARY_URL)
        r.set("canary:last_ok", datetime.now(timezone.utc).isoformat())
        r.delete(CANARY_STREAK_KEY)
        r.delete(CIRCUIT_KEY)
        return {"ok": True}
    except Exception as exc:
        streak = r.incr(CANARY_STREAK_KEY)
        r.expire(CANARY_STREAK_KEY, 3600)
        if streak >= CANARY_FAIL_THRESHOLD:
            # Circuit breaker (§5.1.3 item 4): downloads go dark, uploads/DSP stay up.
            r.set(CIRCUIT_KEY, "1", ex=1800)
        return {"ok": False, "error": str(exc), "streak": streak}


@app.task(name="tasks.purge_expired_media")
def purge_expired_media() -> dict:
    now = datetime.now(timezone.utc)
    deleted = 0
    with session_scope() as db:
        expired = db.query(Media).filter(Media.expires_at < now).all()
        # 부모가 지워지면 DB CASCADE로 자식 행도 사라지니 자식의 오브젝트 키도 미리 모아둔다.
        descendants = collect_descendants(db, [m.id for m in expired])
        storage_keys = {m.storage_key for m in [*expired, *descendants]}
        # 한 번에 지운다 — 부모와 자식이 같이 만료됐을 때 행 단위 delete는 CASCADE로 먼저
        # 사라진 자식을 다시 지우려다 StaleDataError가 난다.
        if expired:
            db.execute(delete(Media).where(Media.id.in_([m.id for m in expired])))
            deleted = len(expired)
        # 다른 사용자의 (아직 안 만료된) 행이 같은 파일을 쓰고 있으면 남겨둔다.
        delete_unreferenced_objects(db, storage_keys)
    return {"deleted": deleted}
