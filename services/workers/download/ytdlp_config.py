"""§5.1.2 download-time yt-dlp option builders."""

from common.cache import publish_progress
from common.ytdlp import base_opts

AUDIO_CODECS = {
    "mp3-320": ("mp3", "320"),
    "mp3-192": ("mp3", "192"),
    "wav": ("wav", None),
}

VIDEO_HEIGHTS = {
    "mp4-1080": 1080,
    "mp4-720": 720,
    "mp4-360": 360,
}


def make_progress_hook(job_id: str):
    def hook(d: dict) -> None:
        if d["status"] == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            done = d.get("downloaded_bytes", 0)
            percent = round(done / total * 100, 1) if total else 0.0
            publish_progress(job_id, {"stage": "downloading", "percent": percent})
        elif d["status"] == "finished":
            publish_progress(job_id, {"stage": "downloading", "percent": 100.0})

    return hook


def audio_opts(job_id: str, format_id: str, out_dir: str, player_client: str | None = None) -> dict:
    codec, quality = AUDIO_CODECS.get(format_id, ("mp3", "320"))
    postprocessor = {"key": "FFmpegExtractAudio", "preferredcodec": codec}
    if quality:
        postprocessor["preferredquality"] = quality

    opts = base_opts(player_client)
    opts.update(
        {
            "format": "bestaudio/best",
            "postprocessors": [
                postprocessor,
                {"key": "FFmpegMetadata", "add_metadata": True},
                {"key": "EmbedThumbnail"},
            ],
            "writethumbnail": True,
            "outtmpl": f"{out_dir}/%(id)s.%(ext)s",
            "progress_hooks": [make_progress_hook(job_id)],
        }
    )
    return opts


def video_opts(job_id: str, format_id: str, out_dir: str, player_client: str | None = None) -> dict:
    height = VIDEO_HEIGHTS.get(format_id, 1080)
    opts = base_opts(player_client)
    opts.update(
        {
            "format": f"bestvideo[height<=?{height}][ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
            "merge_output_format": "mp4",
            "postprocessors": [{"key": "FFmpegMetadata", "add_metadata": True}],
            "outtmpl": f"{out_dir}/%(id)s.%(ext)s",
            "progress_hooks": [make_progress_hook(job_id)],
        }
    )
    return opts
