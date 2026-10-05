"""Shared `media` table writer — used by both the API (uploads) and workers (§8)."""

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import get_settings
from .db.models import Media
from .db.session import session_scope
from .ids import new_id
from .storage import delete_object


def register_media(
    *,
    media_id: str | None = None,
    kind: str,
    source_type: str,
    parent_id: str | None,
    content_hash: str,
    storage_key: str,
    mime_type: str,
    size_bytes: int,
    duration_sec: float | None = None,
    sample_rate: int | None = None,
    channels: int | None = None,
    yt_video_id: str | None = None,
    title: str | None = None,
    artist: str | None = None,
    lineage: dict | None = None,
    user_id: uuid.UUID | None = None,
) -> str:
    media_id = media_id or new_id("med")
    ttl = timedelta(hours=get_settings().media_ttl_hours)
    with session_scope() as db:
        media = Media(
            id=media_id,
            user_id=user_id,
            kind=kind,
            source_type=source_type,
            parent_id=parent_id,
            content_hash=content_hash,
            storage_key=storage_key,
            mime_type=mime_type,
            size_bytes=size_bytes,
            duration_sec=duration_sec,
            sample_rate=sample_rate,
            channels=channels,
            yt_video_id=yt_video_id,
            title=title,
            artist=artist,
            lineage=lineage or {},
            expires_at=datetime.now(timezone.utc) + ttl,
        )
        db.merge(media)
    return media_id


def clone_media_for_user(
    db: Session, media_id: str, user_id: uuid.UUID | None, parent_id: str | None
) -> str | None:
    """캐시 적중 시 다른 사람이 만든 결과물을 요청한 사용자 명의로 복제한다.

    저장소 오브젝트는 내용 기반 키라 그대로 공유하고 DB 행만 새로 만든다 — 그래야
    "내 작업"에 보이고, 소유권 검사를 통과하고, 원래 주인이 지워도 살아남는다.
    원본 행이 이미 지워졌으면 None (호출부는 캐시 미스로 취급해야 한다).
    """
    media = db.get(Media, media_id)
    if media is None:
        return None
    if media.user_id == user_id and media.parent_id == parent_id:
        return media.id

    # 같은 사용자가 같은 결과를 다시 요청한 경우(스튜디오 재진입 등) 행을 또 만들지 않는다.
    existing = db.execute(
        select(Media.id).where(
            Media.user_id == user_id,
            Media.storage_key == media.storage_key,
            Media.parent_id.is_(None) if parent_id is None else Media.parent_id == parent_id,
        )
    ).scalar()
    if existing:
        return existing

    ttl = timedelta(hours=get_settings().media_ttl_hours)
    clone = Media(
        **{c.name: getattr(media, c.name) for c in Media.__table__.columns if c.name not in ("created_at",)}
    )
    clone.id = new_id("med")
    clone.user_id = user_id
    clone.parent_id = parent_id
    clone.expires_at = datetime.now(timezone.utc) + ttl
    db.add(clone)
    db.flush()
    return clone.id


def collect_descendants(db: Session, media_ids: list[str]) -> list[Media]:
    """분리/피치/믹스로 파생된 모든 하위 미디어를 재귀적으로 모은다 — DB 행은
    parent_id의 ON DELETE CASCADE가 지우지만, 저장소 오브젝트는 그 전에 각자의
    storage_key를 알아둬야 정리할 수 있다."""
    found: list[Media] = []
    frontier = list(media_ids)
    while frontier:
        children = db.execute(select(Media).where(Media.parent_id.in_(frontier))).scalars().all()
        if not children:
            break
        found.extend(children)
        frontier = [c.id for c in children]
    return found


def delete_unreferenced_objects(db: Session, storage_keys: set[str]) -> int:
    """행을 지운 *뒤에* 호출 — 더 이상 어떤 media 행도 가리키지 않는 오브젝트만 지운다.
    저장소 키가 내용 기반이라 여러 사용자의 행이 같은 파일을 공유하기 때문."""
    if not storage_keys:
        return 0
    still_used = set(
        db.execute(select(Media.storage_key).where(Media.storage_key.in_(storage_keys))).scalars().all()
    )
    removed = 0
    for key in storage_keys - still_used:
        delete_object(key)
        removed += 1
    return removed
