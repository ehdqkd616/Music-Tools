from pydantic import BaseModel, Field


class SeparateRequest(BaseModel):
    media_id: str
    stems: int = 2  # MVP only supports 2 (§2.1); 4/6 are Phase 2
    quality: str = "fast"  # "fast"=htdemucs | "high"=htdemucs_ft


class PitchRequest(BaseModel):
    media_id: str
    semitones: float = Field(ge=-12, le=12)
    stem_type: str = "other"  # vocals | drums | bass | other — selects Rubber Band mode


class TempoRequest(BaseModel):
    media_id: str
    ratio: float = Field(ge=0.5, le=2.0)


class MixRequest(BaseModel):
    media_ids: list[str]
    output_format: str = "mp3-320"


class AnalyzeResponse(BaseModel):
    content_hash: str
    key: str | None = None
    key_tonic: str | None = None
    key_mode: str | None = None
    key_confidence: float | None = None
    bpm: float | None = None
    lufs_integrated: float | None = None
    true_peak_db: float | None = None
    cached: bool
