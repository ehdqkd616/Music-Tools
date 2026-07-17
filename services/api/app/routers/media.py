from datetime import timedelta

from fastapi import APIRouter

from common.db.models import Media
from common.db.session import SessionLocal
from common.storage import delete_object, presigned_get_url

from ..errors import ApiError
from ..schemas.media import MediaUrlResponse

router = APIRouter()

PRESIGN_EXPIRY = timedelta(hours=1)


@router.get("/{media_id}/url", response_model=MediaUrlResponse)
def get_media_url(media_id: str) -> MediaUrlResponse:
    db = SessionLocal()
    try:
        media = db.get(Media, media_id)
        if not media:
            raise ApiError("NOT_FOUND", "미디어를 찾을 수 없습니다.", {"media_id": media_id})
        url = presigned_get_url(media.storage_key, PRESIGN_EXPIRY)
        return MediaUrlResponse(media_id=media_id, url=url, expires_in_sec=int(PRESIGN_EXPIRY.total_seconds()))
    finally:
        db.close()


@router.delete("/{media_id}")
def delete_media(media_id: str) -> dict:
    db = SessionLocal()
    try:
        media = db.get(Media, media_id)
        if not media:
            raise ApiError("NOT_FOUND", "미디어를 찾을 수 없습니다.", {"media_id": media_id})
        delete_object(media.storage_key)
        db.delete(media)
        db.commit()
        return {"deleted": media_id}
    finally:
        db.close()
