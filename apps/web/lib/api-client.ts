import type {
  AnalyzeResponse,
  ApiErrorBody,
  JobCreatedResponse,
  JobStatusResponse,
  LibraryItem,
  MediaUrlResponse,
  MeResponse,
  UploadResponse,
  User,
  YoutubeInfoResponse,
} from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

class ApiError extends Error {
  code: string;
  detail: Record<string, unknown>;
  retryable: boolean;

  constructor(body: ApiErrorBody["error"]) {
    super(body.message);
    this.code = body.code;
    this.detail = body.detail;
    this.retryable = body.retryable;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    credentials: "include",
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!res.ok) {
    const body = (await res.json()) as ApiErrorBody;
    throw new ApiError(body.error);
  }
  return res.json() as Promise<T>;
}

export const api = {
  youtubeInfo: (url: string) =>
    request<YoutubeInfoResponse>("/api/v1/youtube/info", {
      method: "POST",
      body: JSON.stringify({ url }),
    }),

  youtubeExtract: (url: string, kind: "audio" | "video", format_id: string) =>
    request<JobCreatedResponse>("/api/v1/youtube/extract", {
      method: "POST",
      body: JSON.stringify({ url, kind, format_id }),
    }),

  upload: async (file: File): Promise<UploadResponse> => {
    const form = new FormData();
    form.append("file", file);
    const res = await fetch(`${API_BASE}/api/v1/upload`, {
      method: "POST",
      body: form,
      credentials: "include",
    });
    if (!res.ok) {
      const body = (await res.json()) as ApiErrorBody;
      throw new ApiError(body.error);
    }
    return res.json();
  },

  separate: (media_id: string, quality: "fast" | "high" = "fast") =>
    request<JobCreatedResponse>("/api/v1/process/separate", {
      method: "POST",
      body: JSON.stringify({ media_id, stems: 2, quality }),
    }),

  pitch: (media_id: string, semitones: number, stem_type: string = "other", preview: boolean = false) =>
    request<JobCreatedResponse>("/api/v1/process/pitch", {
      method: "POST",
      body: JSON.stringify({ media_id, semitones, stem_type, preview }),
    }),

  mix: (media_ids: string[], output_format: string = "mp3-320", semitones?: number) =>
    request<JobCreatedResponse>("/api/v1/process/mix", {
      method: "POST",
      body: JSON.stringify({ media_ids, output_format, semitones }),
    }),

  analyze: (media_id: string) => request<AnalyzeResponse>(`/api/v1/analyze/${media_id}`),

  jobStatus: (job_id: string) => request<JobStatusResponse>(`/api/v1/jobs/${job_id}`),

  jobEventsUrl: (job_id: string) => `${API_BASE}/api/v1/jobs/${job_id}/events`,

  mediaUrl: (media_id: string) => request<MediaUrlResponse>(`/api/v1/media/${media_id}/url`),

  // Presigned URL with response-content-disposition=attachment — the browser
  // saves the file instead of opening an inline player (unlike mediaUrl above,
  // which stays undecorated so <audio>/WaveSurfer can stream it normally).
  downloadUrl: (media_id: string) => request<MediaUrlResponse>(`/api/v1/media/${media_id}/download`),

  signup: (email: string, password: string) =>
    request<User>("/api/v1/auth/signup", { method: "POST", body: JSON.stringify({ email, password }) }),

  login: (email: string, password: string) =>
    request<User>("/api/v1/auth/login", { method: "POST", body: JSON.stringify({ email, password }) }),

  logout: () => request<{ logged_out: boolean }>("/api/v1/auth/logout", { method: "POST" }),

  me: () => request<MeResponse>("/api/v1/auth/me"),

  adminListUsers: () => request<User[]>("/api/v1/admin/users"),

  adminApprove: (userId: string) =>
    request<User>(`/api/v1/admin/users/${userId}/approve`, { method: "POST" }),

  adminUnapprove: (userId: string) =>
    request<User>(`/api/v1/admin/users/${userId}/unapprove`, { method: "POST" }),

  adminDeleteUser: (userId: string) =>
    request<{ deleted: string }>(`/api/v1/admin/users/${userId}`, { method: "DELETE" }),

  library: () => request<LibraryItem[]>("/api/v1/library"),

  deleteMedia: (media_id: string) =>
    request<{ deleted: string; cascaded: number }>(`/api/v1/media/${media_id}`, { method: "DELETE" }),
};

export async function triggerDownload(media_id: string) {
  const { url } = await api.downloadUrl(media_id);
  const a = document.createElement("a");
  a.href = url;
  a.rel = "noopener";
  document.body.appendChild(a);
  a.click();
  a.remove();
}

export { ApiError };
