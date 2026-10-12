import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from common.config import get_settings
from common.storage import ensure_bucket
from .accounts import ADMIN_USERNAME, ensure_admin
from .errors import ApiError, api_error_handler
from .routers import admin, analyze, auth, jobs, library, media, process, upload, youtube

settings = get_settings()

app = FastAPI(title="Studio API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_exception_handler(ApiError, api_error_handler)

app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(admin.router, prefix="/api/v1/admin", tags=["admin"])
app.include_router(youtube.router, prefix="/api/v1/youtube", tags=["youtube"])
app.include_router(upload.router, prefix="/api/v1/upload", tags=["upload"])
app.include_router(process.router, prefix="/api/v1/process", tags=["process"])
app.include_router(analyze.router, prefix="/api/v1/analyze", tags=["analyze"])
app.include_router(jobs.router, prefix="/api/v1/jobs", tags=["jobs"])
app.include_router(media.router, prefix="/api/v1/media", tags=["media"])
app.include_router(library.router, prefix="/api/v1/library", tags=["library"])


@app.on_event("startup")
def on_startup() -> None:
    ensure_bucket()
    result = ensure_admin()
    if result:
        logging.getLogger(__name__).info("관리자 계정 %s: %s", "생성" if result == "created" else "동기화", ADMIN_USERNAME)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/api/v1/features")
def features() -> dict:
    """§11.2 — client-side feature flags. Web gets everything; a future
    native app build would flip youtube_extract to False."""
    return {
        "youtube_extract": True,
        "upload": True,
        "separate": True,
        "pitch_shift": True,
    }
