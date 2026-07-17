import type {
  AnalyzeResponse,
  ApiErrorBody,
  JobCreatedResponse,
  JobStatusResponse,
  MediaUrlResponse,
  UploadResponse,
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
    const res = await fetch(`${API_BASE}/api/v1/upload`, { method: "POST", body: form });
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

  pitch: (media_id: string, semitones: number, stem_type: string = "other") =>
    request<JobCreatedResponse>("/api/v1/process/pitch", {
      method: "POST",
      body: JSON.stringify({ media_id, semitones, stem_type }),
    }),

  mix: (media_ids: string[], output_format: string = "mp3-320") =>
    request<JobCreatedResponse>("/api/v1/process/mix", {
      method: "POST",
      body: JSON.stringify({ media_ids, output_format }),
    }),

  analyze: (media_id: string) => request<AnalyzeResponse>(`/api/v1/analyze/${media_id}`),

  jobStatus: (job_id: string) => request<JobStatusResponse>(`/api/v1/jobs/${job_id}`),

  jobEventsUrl: (job_id: string) => `${API_BASE}/api/v1/jobs/${job_id}/events`,

  mediaUrl: (media_id: string) => request<MediaUrlResponse>(`/api/v1/media/${media_id}/url`),
};

export { ApiError };
