"""§로컬 전용 확장: 처리했던 곡 기록.

인증이 없는 개인용 인스턴스라 별도 user_id 필터 없이 전체 source 미디어를
반환한다 — 외부에 노출하지 않는 로컬 도구라는 전제하에서만 안전한 단순화다.
"""

from fastapi import APIRouter
from sqlalchemy import select

from common.db.models import Media
from common.db.session import SessionLocal

from ..schemas.media import LibraryItem

router = APIRouter()


@router.get("", response_model=list[LibraryItem])
def list_library(limit: int = 200) -> list[LibraryItem]:
    db = SessionLocal()
    try:
        sources = (
            db.execute(
                select(Media).where(Media.kind == "source").order_by(Media.created_at.desc()).limit(limit)
            )
            .scalars()
            .all()
        )

        stem_parent_ids = set(
            db.execute(
                select(Media.parent_id).where(Media.kind == "stem", Media.parent_id.isnot(None)).distinct()
            )
            .scalars()
            .all()
        )

        items = []
        for media in sources:
            thumbnail = (
                f"https://i.ytimg.com/vi/{media.yt_video_id}/hqdefault.jpg" if media.yt_video_id else None
            )
            items.append(
                LibraryItem(
                    media_id=media.id,
                    title=media.title,
                    artist=media.artist,
                    source_type=media.source_type,
                    yt_video_id=media.yt_video_id,
                    thumbnail=thumbnail,
                    duration_sec=media.duration_sec,
                    has_stems=media.id in stem_parent_ids,
                    created_at=media.created_at,
                )
            )
        return items
    finally:
        db.close()
