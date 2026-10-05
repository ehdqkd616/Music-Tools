import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select

from common.db.models import Job, Media, User
from common.db.session import SessionLocal

from ..deps import require_admin
from ..errors import ApiError
from ..schemas.auth import UserResponse
from ..schemas.jobs import AdminJobItem

router = APIRouter()


def _to_user_response(user: User) -> UserResponse:
    return UserResponse(
        id=str(user.id),
        email=user.email,
        tier=user.tier,
        is_approved=user.is_approved,
        is_admin=user.is_admin,
        created_at=user.created_at,
    )


def _get_user(db, user_id: str) -> User:
    user = db.get(User, user_id)
    if not user:
        raise ApiError("NOT_FOUND", "사용자를 찾을 수 없습니다.", {"user_id": user_id})
    return user


@router.get("/users", response_model=list[UserResponse], dependencies=[Depends(require_admin)])
def list_users() -> list[UserResponse]:
    db = SessionLocal()
    try:
        users = db.execute(select(User).order_by(User.created_at.desc())).scalars().all()
        return [_to_user_response(u) for u in users]
    finally:
        db.close()


@router.post("/users/{user_id}/approve", response_model=UserResponse)
def approve_user(user_id: str, current_user: User = Depends(require_admin)) -> UserResponse:
    db = SessionLocal()
    try:
        user = _get_user(db, user_id)
        user.is_approved = True
        db.commit()
        db.refresh(user)
        return _to_user_response(user)
    finally:
        db.close()


@router.post("/users/{user_id}/unapprove", response_model=UserResponse)
def unapprove_user(user_id: str, current_user: User = Depends(require_admin)) -> UserResponse:
    db = SessionLocal()
    try:
        user = _get_user(db, user_id)
        if user.id == current_user.id:
            raise ApiError("VALIDATION_ERROR", "본인 계정은 승인 취소할 수 없습니다.")
        user.is_approved = False
        db.commit()
        db.refresh(user)
        return _to_user_response(user)
    finally:
        db.close()


@router.delete("/users/{user_id}")
def delete_user(user_id: str, current_user: User = Depends(require_admin)) -> dict:
    db = SessionLocal()
    try:
        user = _get_user(db, user_id)
        if user.id == current_user.id:
            raise ApiError("VALIDATION_ERROR", "본인 계정은 삭제할 수 없습니다.")
        db.delete(user)
        db.commit()
        return {"deleted": user_id}
    finally:
        db.close()


def _resolve_sources(db, media_ids: set[str]) -> dict[str, Media]:
    """media_id -> 그 미디어가 파생된 원본(source) Media. stem/processed는 parent_id를 따라 올라간다."""
    resolved: dict[str, Media] = {}
    loaded: dict[str, Media] = {}
    pending = set(media_ids)
    # 파생 깊이는 source -> stem -> processed 정도라 몇 번이면 끝나지만, 순환 방지로 상한을 둔다.
    for _ in range(5):
        missing = pending - loaded.keys()
        if not missing:
            break
        for m in db.execute(select(Media).where(Media.id.in_(missing))).scalars():
            loaded[m.id] = m
        pending = {m.parent_id for m in loaded.values() if m.parent_id and m.parent_id not in loaded}
        if not pending:
            break

    for media_id in media_ids:
        m = loaded.get(media_id)
        for _ in range(5):
            if m is None or m.parent_id is None or m.parent_id not in loaded:
                break
            m = loaded[m.parent_id]
        if m is not None:
            resolved[media_id] = m
    return resolved


@router.get("/jobs", response_model=list[AdminJobItem], dependencies=[Depends(require_admin)])
def list_jobs(
    user_id: uuid.UUID | None = None,
    include_previews: bool = False,
    limit: int = Query(default=200, ge=1, le=1000),
) -> list[AdminJobItem]:
    """전체 회원의 작업 기록 (최신순). user_id로 특정 회원만 필터링할 수 있다."""
    db = SessionLocal()
    try:
        stmt = select(Job, User.email).outerjoin(User, Job.user_id == User.id)
        if user_id:
            stmt = stmt.where(Job.user_id == user_id)
        if not include_previews:
            # 키 미리듣기(pitch preview)는 슬라이더를 움직일 때마다 생겨서 기록을 도배한다.
            stmt = stmt.where(Job.params["preview"].astext.is_distinct_from("true"))
        rows = db.execute(stmt.order_by(Job.queued_at.desc()).limit(limit)).all()

        def ref_media(job: Job) -> str | None:
            return job.input_media or (job.output_media[0] if job.output_media else None)

        sources = _resolve_sources(db, {mid for job, _ in rows if (mid := ref_media(job))})

        items = []
        for job, email in rows:
            mid = ref_media(job)
            source = sources.get(mid) if mid else None
            items.append(
                AdminJobItem(
                    job_id=job.id,
                    type=job.type,
                    status=job.status,
                    progress=job.progress,
                    user_id=str(job.user_id) if job.user_id else None,
                    user_email=email,
                    media_id=source.id if source else None,
                    title=source.title if source else None,
                    params=job.params or {},
                    output_media=job.output_media,
                    error_code=job.error_code,
                    error_message=job.error_message,
                    cache_hit=job.cache_hit,
                    queued_at=job.queued_at,
                    started_at=job.started_at,
                    finished_at=job.finished_at,
                )
            )
        return items
    finally:
        db.close()
