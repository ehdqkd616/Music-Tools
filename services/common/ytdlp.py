"""§5.1.2 / §5.1.3 — shared yt-dlp option base + bot-detection fallback chain."""

from .config import get_settings

# ios first: usually doesn't require a PO token. web_safari/android/tv as fallback
# if a client gets blocked (§5.1.3).
CLIENT_FALLBACK_CHAIN = ["ios", "web_safari", "android", "tv"]

ROTATING_UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1"
)


def base_opts(player_client: str | None = None) -> dict:
    settings = get_settings()
    opts: dict = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "extractor_args": {
            "youtube": {"player_client": [player_client] if player_client else CLIENT_FALLBACK_CHAIN}
        },
        "http_headers": {"User-Agent": ROTATING_UA},
        "retries": 3,
        "socket_timeout": 30,
    }
    if settings.proxy_url:
        opts["proxy"] = settings.proxy_url
    if settings.cookie_path:
        opts["cookiefile"] = settings.cookie_path
    return opts


def fetch_info(url: str) -> dict:
    """Metadata-only lookup (download=False), trying each client in the fallback chain."""
    from yt_dlp import DownloadError, YoutubeDL

    last_error: Exception | None = None
    for client in CLIENT_FALLBACK_CHAIN:
        try:
            with YoutubeDL(base_opts(client)) as ydl:
                return ydl.extract_info(url, download=False)
        except DownloadError as exc:  # try next client in the chain
            last_error = exc
            continue
    raise last_error or RuntimeError("yt-dlp extraction failed for all clients")
