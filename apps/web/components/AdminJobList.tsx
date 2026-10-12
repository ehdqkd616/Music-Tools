"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ApiError, api, triggerDownload } from "@/lib/api-client";
import { translateError } from "@/lib/errors";
import type { AdminJobItem, User } from "@/lib/types";

const TYPE_LABEL: Record<string, string> = {
  extract: "유튜브 가져오기",
  separate: "보컬 분리",
  pitch: "키 변경",
  tempo: "템포 변경",
  mix: "믹스/내보내기",
};

const STATUS_LABEL: Record<AdminJobItem["status"], { text: string; className: string }> = {
  queued: { text: "대기", className: "text-white/60" },
  running: { text: "진행 중", className: "text-accent" },
  succeeded: { text: "완료", className: "text-green-400" },
  failed: { text: "실패", className: "text-red-400" },
  cancelled: { text: "취소", className: "text-white/40" },
};

function describeParams(job: AdminJobItem): string | null {
  const p = job.params;
  switch (job.type) {
    case "extract":
      return [p.kind === "video" ? "영상" : "오디오", p.format_id].filter(Boolean).join(" · ");
    case "separate":
      return p.quality === "high" ? "고품질" : "빠르게";
    case "pitch": {
      const st = Number(p.semitones ?? 0);
      return `${st > 0 ? "+" : ""}${st}키${p.preview ? " (미리듣기)" : ""}`;
    }
    case "tempo":
      return p.ratio != null ? `×${p.ratio}` : null;
    case "mix":
      return typeof p.output_format === "string" ? p.output_format : null;
    default:
      return null;
  }
}

function elapsed(job: AdminJobItem): string | null {
  if (!job.started_at || !job.finished_at) return null;
  const sec = (new Date(job.finished_at).getTime() - new Date(job.started_at).getTime()) / 1000;
  return sec < 60 ? `${sec.toFixed(1)}초` : `${Math.floor(sec / 60)}분 ${Math.round(sec % 60)}초`;
}

export default function AdminJobList({
  users,
  userId,
  onUserIdChange,
}: {
  users: User[] | null;
  userId: string;
  onUserIdChange: (id: string) => void;
}) {
  const router = useRouter();
  const [jobs, setJobs] = useState<AdminJobItem[] | null>(null);
  const [includePreviews, setIncludePreviews] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [downloadingId, setDownloadingId] = useState<string | null>(null);

  function load() {
    setError(null);
    api
      .adminListJobs({ userId: userId || undefined, includePreviews })
      .then(setJobs)
      .catch((e) => setError(e instanceof ApiError ? translateError(e.code, e.message) : "작업 기록을 불러오지 못했습니다."));
  }

  useEffect(() => {
    setJobs(null);
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [userId, includePreviews]);

  async function handleDownload(job: AdminJobItem, mediaId: string) {
    setDownloadingId(job.job_id);
    try {
      await triggerDownload(mediaId);
    } catch (e) {
      setError(e instanceof ApiError ? translateError(e.code, e.message) : "다운로드에 실패했습니다.");
    } finally {
      setDownloadingId(null);
    }
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <select
          value={userId}
          onChange={(e) => onUserIdChange(e.target.value)}
          className="min-w-0 max-w-full rounded-md border border-white/10 bg-panel px-2 py-1.5 text-sm"
        >
          <option value="">전체 회원</option>
          {users?.map((u) => (
            <option key={u.id} value={u.id}>
              {u.username}
            </option>
          ))}
        </select>
        <label className="flex items-center gap-1.5 text-xs text-white/60 whitespace-nowrap">
          <input type="checkbox" checked={includePreviews} onChange={(e) => setIncludePreviews(e.target.checked)} />
          키 미리듣기 포함
        </label>
        <button
          onClick={load}
          className="rounded-md border border-white/10 hover:border-white/30 px-3 py-1.5 text-xs whitespace-nowrap"
        >
          새로고침
        </button>
      </div>

      {error && <p className="text-sm text-red-400">{error}</p>}
      {jobs === null && !error && <p className="text-sm text-white/50">불러오는 중…</p>}
      {jobs?.length === 0 && <p className="text-sm text-white/50">작업 기록이 없습니다.</p>}

      <div className="space-y-2">
        {jobs?.map((job) => {
          const status = STATUS_LABEL[job.status] ?? { text: job.status, className: "text-white/60" };
          const detail = describeParams(job);
          const took = elapsed(job);
          const output = job.status === "succeeded" && job.output_media?.length ? job.output_media[0] : null;
          return (
            <div
              key={job.job_id}
              className="flex flex-col sm:flex-row sm:items-center gap-3 rounded-lg border border-white/10 bg-panel p-3"
            >
              <div className="flex-1 min-w-0">
                <p className="font-medium truncate">
                  <span className={`mr-2 text-xs whitespace-nowrap ${status.className}`}>
                    {status.text}
                    {job.status === "running" && ` ${Math.round(job.progress * 100)}%`}
                  </span>
                  {TYPE_LABEL[job.type] ?? job.type}
                  {detail && <span className="text-white/50 font-normal"> · {detail}</span>}
                </p>
                <p className="text-sm truncate">{job.title || (typeof job.params.url === "string" ? job.params.url : null) || job.media_id || "(제목 없음)"}</p>
                <p className="text-xs text-white/50 truncate">
                  {job.user_email ?? "(삭제된 회원)"} · {new Date(job.queued_at).toLocaleString("ko-KR")}
                  {took && ` · ${took}`}
                  {job.cache_hit && " · 캐시"}
                </p>
                {job.status === "failed" && (job.error_message || job.error_code) && (
                  <p className="text-xs text-red-400/80 break-words">{job.error_message || job.error_code}</p>
                )}
              </div>

              <div className="flex flex-wrap items-center gap-2 sm:shrink-0">
                {output && (
                  <button
                    onClick={() => handleDownload(job, output)}
                    disabled={downloadingId === job.job_id}
                    className="rounded-md border border-white/10 hover:border-white/30 px-3 py-1.5 text-xs whitespace-nowrap disabled:opacity-40"
                  >
                    {downloadingId === job.job_id ? "…" : "⬇ 결과물"}
                  </button>
                )}
                {job.media_id && (
                  <button
                    onClick={() => router.push(`/studio/${job.media_id}`)}
                    className="rounded-md border border-white/10 hover:border-white/30 px-3 py-1.5 text-xs whitespace-nowrap"
                  >
                    🎤 열기
                  </button>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
