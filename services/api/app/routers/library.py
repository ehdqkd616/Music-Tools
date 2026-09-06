"""내 작업(라이브러리) — 로그인한 사용자 본인의 source 미디어만 반환한다."""

from fastapi import APIRouter, Depends
from sqlalchemy import select

from common.db.models import Media, User
from common.db.session import SessionLocal

from ..deps import require_user
from ..schemas.media import LibraryItem

router = APIRouter()


@router.get("", response_model=list[LibraryItem])
def list_library(limit: int = 200, current_user: User = Depends(require_user)) -> list[LibraryItem]:
    db = SessionLocal()
    try:
        sources = (
            db.execute(
                select(Media)
                .where(Media.kind == "source", Media.user_id == current_user.id)
                .order_by(Media.created_at.desc())
                .limit(limit)
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
