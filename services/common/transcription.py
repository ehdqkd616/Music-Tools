"""Instruments the transcription feature supports, shared by the API and worker."""

INSTRUMENTS = ("piano", "guitar", "bass", "vocals", "strings", "winds", "other")


def pipeline_version(instrument: str) -> str:
    """Cache/storage version tag. Bump the number when an engine's output changes."""
    if instrument == "piano":
        return "piano-v1"
    return f"basicpitch-v1-{instrument}"
