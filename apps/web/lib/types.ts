// Mirrors services/api/app/schemas/*.py. Hand-kept in sync for the MVP —
// see §10.3's packages/shared-types: a real OpenAPI->TS codegen step is a
// natural follow-up once the API is stable enough to be worth generating from.

export interface FormatOption {
  id: string;
  label: string;
  est_size_mb: number;
}

export interface YoutubeInfoResponse {
  video_id: string;
  title: string;
  channel: string;
  duration_sec: number;
  thumbnail: string | null;
  available_formats: { audio: FormatOption[]; video: FormatOption[] };
  cached: boolean;
}

export interface JobCreatedResponse {
  job_id: string;
  status: string;
  queue_position?: number | null;
  eta_sec?: number | null;
  cached: boolean;
}

export interface JobStatusResponse {
  job_id: string;
  type: string;
  status: "queued" | "running" | "succeeded" | "failed" | "cancelled";
  progress: number;
  output_media: string[] | null;
  error_code: string | null;
  error_message: string | null;
  cache_hit: boolean;
  queued_at: string;
  started_at: string | null;
  finished_at: string | null;
}

export interface AnalyzeResponse {
  content_hash: string;
  key: string | null;
  key_tonic: string | null;
  key_mode: string | null;
  key_confidence: number | null;
  bpm: number | null;
  lufs_integrated: number | null;
  true_peak_db: number | null;
  cached: boolean;
}

export interface UploadResponse {
  media_id: string;
  title: string | null;
  duration_sec: number | null;
  content_hash: string;
}

export interface MediaUrlResponse {
  media_id: string;
  url: string;
  expires_in_sec: number;
}

export interface ApiErrorBody {
  error: { code: string; message: string; detail: Record<string, unknown>; retryable: boolean };
}
