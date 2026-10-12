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

export type UserStatus = "pending" | "approved" | "rejected" | "suspended";

export interface User {
  id: string;
  username: string;
  name: string;
  status: UserStatus;
  is_approved: boolean;
  is_admin: boolean;
  tier: string;
  created_at: string;
  /** 비밀번호를 서버 .env(ADMIN_PASSWORD)로 관리하는 공통 관리자 계정 */
  password_managed: boolean;
}

export interface AdminUser extends User {
  signup_note: string | null;
  reject_reason: string | null;
  approved_at: string | null;
  last_login_at: string | null;
}

export interface AdminStats {
  users: { total: number; pending: number; by_status: Record<string, number> };
  today: { signups: number; logins: number; login_failures: number };
  week_signups: number;
}

export interface AuditLogItem {
  id: number;
  action: string;
  target_id: string | null;
  detail: Record<string, unknown> | null;
  ip: string | null;
  created_at: string;
  actor_username: string | null;
}

export interface SignupInput {
  username: string;
  name: string;
  password: string;
  signup_note?: string;
  agree_terms: boolean;
  agree_privacy: boolean;
}

export interface MeResponse {
  user: User | null;
}

export interface LibraryItem {
  media_id: string;
  title: string | null;
  artist: string | null;
  source_type: string;
  yt_video_id: string | null;
  thumbnail: string | null;
  duration_sec: number | null;
  has_stems: boolean;
  created_at: string;
}

export interface AdminJobItem {
  job_id: string;
  type: string;
  status: JobStatusResponse["status"];
  progress: number;
  user_id: string | null;
  user_email: string | null;
  media_id: string | null;
  title: string | null;
  params: Record<string, unknown>;
  output_media: string[] | null;
  error_code: string | null;
  error_message: string | null;
  cache_hit: boolean;
  queued_at: string;
  started_at: string | null;
  finished_at: string | null;
}
