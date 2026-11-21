"""Stem layouts shared by the API and the separation worker.

A separation job's outputs are always in output_names(stems) order, which is
how the frontend knows which media id is which instrument. 4/6-stem jobs also
get an MP3 preview per stem after the WAVs: the WAVs are float32 (~85MB each
for a 4-minute song), too heavy for a browser to play six of at once.
"""

from .config import Settings

STEM_ORDER: dict[int, list[str]] = {
    2: ["vocals", "instrumental"],
    4: ["vocals", "drums", "bass", "other"],
    6: ["vocals", "drums", "bass", "guitar", "piano", "other"],
}


def separation_model(settings: Settings, stems: int, quality: str) -> str:
    # Only htdemucs_6s knows guitar and piano, so 6 stems ignores the quality tier.
    if stems == 6:
        return settings.demucs_6s_model
    return settings.demucs_hq_model if quality == "high" else settings.demucs_fast_model


def has_previews(stems: int) -> bool:
    return stems in (4, 6)


def output_names(stems: int) -> list[str]:
    names = STEM_ORDER[stems]
    return names + [f"{name}_preview" for name in names] if has_previews(stems) else names


def cached_output_ids(cached: dict, stems: int) -> list[str | None]:
    return [cached.get(f"{name}_media_id") for name in output_names(stems)]
