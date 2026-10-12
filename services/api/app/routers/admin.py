import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select

from common.db.models import AuditLog, Job, Media, User
from common.db.session import SessionLocal

from ..accounts import audit, client_ip, is_managed_admin, temp_password
from ..deps import require_admin
from ..errors import ApiError
from ..schemas.auth import AdminUserResponse
from ..schemas.jobs import AdminJobItem
from ..security import hash_password
from ..session_store import revoke_user_sessions

router = APIRouter()

USER_STATUSES = ("pending", "approved", "rejected", "suspended")


class RejectBody(BaseModel):
    reason: str | None = Field(default=None, max_length=500)


class BulkBody(BaseModel):
    user_ids: list[str] = Field(max_length=200)


def _to_admin_user(user: User) -> AdminUserResponse:
    return AdminUserResponse(
        id=str(user.id),
        username=user.username,
        name=user.name,
        status=user.status,
        is_approved=user.is_approved,
        is_admin=user.is_admin,
        tier=user.tier,
        created_at=user.created_at,
        password_managed=is_managed_admin(user),
        signup_note=user.signup_note,
        reject_reason=user.reject_reason,
        approved_at=user.approved_at,
        last_login_at=user.last_login_at,
    )


def _get_user(db, user_id: str) -> User:
    try:
        user = db.get(User, uuid.UUID(user_id))
    except ValueError:
        user = None
    if not user:
        raise ApiError("NOT_FOUND", "회원을 찾을 수 없습니다.", {"user_id": user_id})
    return user


def _change_status(db, admin: User, user: User, new_status: str, ip: str | None, reason: str | None = None) -> User:
    if user.id == admin.id:
        raise ApiError("INVALID_STATE", "자기 자신의 상태는 바꿀 수 없습니다.")
    if user.is_admin and new_status != "approved":
        raise ApiError("INVALID_STATE", "관리자 계정은 거절·정지할 수 없습니다.")
    old = user.status
    user.status = new_status
    if new_status == "approved":
        user.approved_at = datetime.now(timezone.utc)
        user.reject_reason = None
    elif new_status == "rejected":
        user.reject_reason = reason
    action = {"approved": "unsuspend" if old == "suspended" else "approve", "rejected": "reject", "suspended": "suspend"}[new_status]
    audit(db, f"admin.user.{action}", actor_id=admin.id, target_id=user.id,
          detail={"from": old, "to": new_status, **({"reason": reason} if reason else {})}, ip=ip)
    db.commit()
    db.refresh(user)
    if new_status in ("rejected", "suspended"):
        revoke_user_sessions(str(user.id))  # 즉시 로그아웃
    return user


def _status_route(allowed_from: tuple[str, ...], new_status: str, message: str):
    def handler(user_id: str, request: Request, body: RejectBody | None = None,
                admin: User = Depends(require_admin)) -> AdminUserResponse:
        db = SessionLocal()
        try:
            user = _get_user(db, user_id)
            if user.status not in allowed_from:
                raise ApiError("INVALID_STATE", message)
            reason = (body.reason or "").strip() or None if body and new_status == "rejected" else None
            return _to_admin_user(_change_status(db, admin, user, new_status, client_ip(request), reason))
        finally:
            db.close()
    handler.__name__ = f"set_status_{new_status}_from_{'_'.join(allowed_from)}"
    return handler


@router.get("/stats")
def stats(admin: User = Depends(require_admin)) -> dict:
    db = SessionLocal()
    try:
        by_status = dict(db.execute(select(User.status, func.count()).group_by(User.status)).all())
        today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        count = lambda *conds: db.scalar(select(func.count()).select_from(AuditLog).where(*conds)) or 0  # noqa: E731
        return {
            "users": {"total": sum(by_status.values()), "by_status": by_status, "pending": by_status.get("pending", 0)},
            "today": {
                "signups": count(AuditLog.action == "user.signup", AuditLog.created_at >= today),
                "logins": count(AuditLog.action == "login.success", AuditLog.created_at >= today),
                "login_failures": count(AuditLog.action == "login.failure", AuditLog.created_at >= today),
            },
            "week_signups": count(AuditLog.action == "user.signup", AuditLog.created_at >= today - timedelta(days=6)),
        }
    finally:
        db.close()


@router.get("/users", response_model=list[AdminUserResponse])
def list_users(status: str | None = None, q: str | None = None, admin: User = Depends(require_admin)) -> list[AdminUserResponse]:
    db = SessionLocal()
    try:
        stmt = select(User)
        if status in USER_STATUSES:
            stmt = stmt.where(User.status == status)
        if q:
            stmt = stmt.where(or_(User.username.ilike(f"%{q}%"), User.name.ilike(f"%{q}%")))
        stmt = stmt.order_by((User.status == "pending").desc(), User.created_at.desc()).limit(500)
        return [_to_admin_user(u) for u in db.execute(stmt).scalars().all()]
    finally:
        db.close()


@router.get("/users/{user_id}")
def get_user(user_id: str, admin: User = Depends(require_admin)) -> dict:
    db = SessionLocal()
    try:
        user = _get_user(db, user_id)
        logins = db.execute(
            select(AuditLog).where(AuditLog.target_id == str(user.id), AuditLog.action.like("login.%"))
            .order_by(AuditLog.id.desc()).limit(20)
        ).scalars().all()
        return {
            "user": _to_admin_user(user),
            "logins": [{"action": a.action, "ip": a.ip, "created_at": a.created_at} for a in logins],
        }
    finally:
        db.close()


router.post("/users/{user_id}/approve", response_model=AdminUserResponse)(
    _status_route(("pending", "rejected"), "approved", "대기 또는 거절 상태의 회원만 승인할 수 있습니다."))
router.post("/users/{user_id}/reject", response_model=AdminUserResponse)(
    _status_route(("pending",), "rejected", "승인 대기 중인 회원만 거절할 수 있습니다."))
router.post("/users/{user_id}/suspend", response_model=AdminUserResponse)(
    _status_route(("approved",), "suspended", "승인된 회원만 정지할 수 있습니다."))
router.post("/users/{user_id}/unsuspend", response_model=AdminUserResponse)(
    _status_route(("suspended",), "approved", "정지된 회원만 해제할 수 있습니다."))


@router.post("/users/bulk-approve")
def bulk_approve(body: BulkBody, request: Request, admin: User = Depends(require_admin)) -> dict:
    if not body.user_ids:
        raise ApiError("VALIDATION_ERROR", "승인할 회원을 선택하세요.")
    db = SessionLocal()
    try:
        approved = 0
        for user_id in body.user_ids:
            user = _get_user(db, user_id)
            if user.status == "pending":
                _change_status(db, admin, user, "approved", client_ip(request))
                approved += 1
        return {"approved": approved}
    finally:
        db.close()


@router.post("/users/{user_id}/temp-password")
def issue_temp_password(user_id: str, request: Request, admin: User = Depends(require_admin)) -> dict:
    """임시 비밀번호 발급 — 응답으로 한 번만 보여 준다. 그 회원의 세션은 모두 끊는다."""
    db = SessionLocal()
    try:
        user = _get_user(db, user_id)
        if user.id == admin.id:
            raise ApiError("INVALID_STATE", "본인 비밀번호는 내 정보에서 변경하세요.")
        if is_managed_admin(user):
            raise ApiError("ADMIN_PASSWORD_MANAGED", "관리자 비밀번호는 서버 .env의 ADMIN_PASSWORD로 관리합니다.")
        pw = temp_password()
        user.password_hash = hash_password(pw)
        audit(db, "admin.user.temp_password", actor_id=admin.id, target_id=user.id, ip=client_ip(request))
        db.commit()
    finally:
        db.close()
    revoke_user_sessions(user_id)
    return {"temp_password": pw}


@router.delete("/users/{user_id}")
def delete_user(user_id: str, request: Request, admin: User = Depends(require_admin)) -> dict:
    db = SessionLocal()
    try:
        user = _get_user(db, user_id)
        if user.id == admin.id or is_managed_admin(user):
            raise ApiError("INVALID_STATE", "이 계정은 삭제할 수 없습니다.")
        audit(db, "admin.user.delete", actor_id=admin.id, target_id=user.id, detail={"username": user.username}, ip=client_ip(request))
        db.delete(user)
        db.commit()
    finally:
        db.close()
    revoke_user_sessions(user_id)
    return {"deleted": user_id}


@router.get("/audit-logs")
def audit_logs(action: str | None = None, limit: int = 200, admin: User = Depends(require_admin)) -> dict:
    db = SessionLocal()
    try:
        actor = User.__table__.alias("actor")
        stmt = (select(AuditLog, actor.c.username).outerjoin(actor, actor.c.id == AuditLog.actor_id)
                .order_by(AuditLog.id.desc()).limit(min(max(limit, 1), 500)))
        if action:
            stmt = stmt.where(AuditLog.action.like(f"{action}%"))
        return {"items": [
            {"id": a.id, "action": a.action, "target_id": a.target_id, "detail": a.detail, "ip": a.ip,
             "created_at": a.created_at, "actor_username": username}
            for a, username in db.execute(stmt).all()
        ]}
    finally:
        db.close()


# --- 작업 기록 -----------------------------------------------------------------

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
        stmt = select(Job, User.username).outerjoin(User, Job.user_id == User.id)
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
        for job, username in rows:
            mid = ref_media(job)
            source = sources.get(mid) if mid else None
            items.append(
                AdminJobItem(
                    job_id=job.id,
                    type=job.type,
                    status=job.status,
                    progress=job.progress,
                    user_id=str(job.user_id) if job.user_id else None,
                    user_email=username,
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
