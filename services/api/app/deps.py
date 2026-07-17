"""§14.1 usage quota + request identity helpers."""

import hashlib
from datetime import date

from fastapi import Request

from common.config import get_settings
from common.redis_client import get_redis
from .errors import ApiError


def client_subject(request: Request) -> str:
    """ip:{hash} — no auth yet, so every anonymous caller is IP-scoped (§14.1)."""
    ip = request.client.host if request.client else "unknown"
    digest = hashlib.sha256(ip.encode()).hexdigest()[:16]
    return f"ip:{digest}"


def check_quota(subject: str, action: str, limit: int) -> None:
    key = f"quota:{subject}:{action}:{date.today().isoformat()}"
    r = get_redis()
    pipe = r.pipeline()
    pipe.incr(key)
    pipe.expire(key, 86400)
    count, _ = pipe.execute()
    if count > limit:
        raise ApiError(
            "RATE_LIMITED",
            f"{action} 일일 한도({limit}회)를 초과했습니다.",
            {"action": action, "limit": limit},
        )


def enforce_download_quota(request: Request) -> None:
    settings = get_settings()
    check_quota(client_subject(request), "download", settings.anon_daily_download_limit)


def enforce_separate_quota(request: Request) -> None:
    settings = get_settings()
    check_quota(client_subject(request), "separate", settings.anon_daily_separate_limit)
