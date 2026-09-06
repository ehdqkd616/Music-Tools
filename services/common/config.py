from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://app:app_pass@localhost:5432/studio"
    redis_url: str = "redis://localhost:6379/0"

    s3_endpoint: str = "http://localhost:9000"
    s3_public_endpoint: str = "http://localhost:9000"
    s3_access_key: str = "minioadmin"
    s3_secret_key: str = "minioadmin"
    s3_bucket: str = "studio-media"
    s3_region: str = "us-east-1"

    cors_origins: str = "http://localhost:3000"

    max_upload_mb: int = 100
    max_upload_duration_sec: int = 900
    max_youtube_duration_sec: int = 1200
    anon_daily_download_limit: int = 10
    anon_daily_separate_limit: int = 2
    media_ttl_hours: int = 24

    proxy_url: str = ""
    cookie_path: str = ""

    demucs_device: str = "cpu"
    demucs_fast_model: str = "htdemucs"
    demucs_hq_model: str = "htdemucs_ft"

    # Bootstrapped as an approved admin user on API startup if set and not already present.
    admin_email: str = ""
    admin_password: str = ""

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
