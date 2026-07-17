"""§5.3 caching strategy — L1 download cache, L2 separation cache, L3 analysis cache."""

import hashlib
import json

import numpy as np

from .redis_client import get_redis

L1_TTL = 60 * 60 * 24  # 24h — youtube download cache
L2_TTL = 60 * 60 * 24 * 7  # 7d — separation result cache
L3_TTL = 60 * 60 * 24 * 30  # 30d — key/BPM/loudness analysis cache
L4_TTL = 60 * 60 * 24 * 7  # 7d — pitch/tempo result cache


def content_hash(path: str) -> str:
    """Hash of the decoded PCM, normalized to 16kHz mono.

    Same song encoded as 320k MP3 vs WAV hashes identically, so uploads and
    youtube extracts of the same track share the L2/L3 cache regardless of
    source format.
    """
    import librosa

    y, _ = librosa.load(path, sr=16000, mono=True)
    y = np.round(y, 4)
    return hashlib.sha256(y.tobytes()).hexdigest()


def l1_key(video_id: str, fmt: str, quality: str) -> str:
    return f"media:{video_id}:{fmt}:{quality}"


def l2_key(content_hash_: str, model: str, stems: int) -> str:
    return f"sep:{content_hash_}:{model}:{stems}"


def l3_key(content_hash_: str) -> str:
    return f"analysis:{content_hash_}"


def pitch_key(content_hash_: str, semitones: float, stem_type: str) -> str:
    return f"pitch:{content_hash_}:{semitones}:{stem_type}"


def tempo_key(content_hash_: str, ratio: float) -> str:
    return f"tempo:{content_hash_}:{ratio}"


def cache_get(key: str) -> dict | None:
    raw = get_redis().get(key)
    return json.loads(raw) if raw else None


def cache_set(key: str, value: dict, ttl: int) -> None:
    get_redis().set(key, json.dumps(value), ex=ttl)


def publish_progress(job_id: str, payload: dict) -> None:
    get_redis().publish(f"progress:{job_id}", json.dumps(payload))
