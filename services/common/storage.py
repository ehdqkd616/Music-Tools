from datetime import timedelta
from functools import lru_cache
from pathlib import Path

import boto3
from botocore.client import Config

from .config import get_settings


@lru_cache
def _client():
    settings = get_settings()
    return boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
        region_name=settings.s3_region,
        config=Config(signature_version="s3v4"),
    )


@lru_cache
def _public_client():
    """Client whose presigned URLs are signed for the endpoint a browser can reach."""
    settings = get_settings()
    return boto3.client(
        "s3",
        endpoint_url=settings.s3_public_endpoint,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
        region_name=settings.s3_region,
        config=Config(signature_version="s3v4"),
    )


def ensure_bucket() -> None:
    settings = get_settings()
    s3 = _client()
    existing = {b["Name"] for b in s3.list_buckets().get("Buckets", [])}
    if settings.s3_bucket not in existing:
        s3.create_bucket(Bucket=settings.s3_bucket)


def upload_file(local_path: str | Path, key: str, content_type: str | None = None) -> str:
    settings = get_settings()
    extra = {"ContentType": content_type} if content_type else {}
    _client().upload_file(str(local_path), settings.s3_bucket, key, ExtraArgs=extra)
    return key


def download_file(key: str, local_path: str | Path) -> str:
    settings = get_settings()
    Path(local_path).parent.mkdir(parents=True, exist_ok=True)
    _client().download_file(settings.s3_bucket, key, str(local_path))
    return str(local_path)


def delete_object(key: str) -> None:
    settings = get_settings()
    _client().delete_object(Bucket=settings.s3_bucket, Key=key)


def object_exists(key: str) -> bool:
    settings = get_settings()
    try:
        _client().head_object(Bucket=settings.s3_bucket, Key=key)
        return True
    except Exception:
        return False


def presigned_get_url(key: str, expires: timedelta = timedelta(hours=1)) -> str:
    settings = get_settings()
    return _public_client().generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.s3_bucket, "Key": key},
        ExpiresIn=int(expires.total_seconds()),
    )
