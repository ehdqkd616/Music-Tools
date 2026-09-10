"use client";

import { useRouter } from "next/navigation";
import { useRef, useState } from "react";
import FormatPicker from "@/components/FormatPicker";
import JobProgress from "@/components/JobProgress";
import UrlInput from "@/components/UrlInput";
import { api, ApiError, triggerDownload } from "@/lib/api-client";
import { useAuth } from "@/lib/auth-context";
import type { YoutubeInfoResponse } from "@/lib/types";

type Mode = "idle" | "downloading" | "importing";

export default function Home() {
  const router = useRouter();
  const { user, loading: authLoading } = useAuth();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [info, setInfo] = useState<YoutubeInfoResponse | null>(null);
  const [loadingInfo, setLoadingInfo] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [format, setFormat] = useState("mp3-320");
  const [mode, setMode] = useState<Mode>("idle");
  const [jobId, setJobId] = useState<string | null>(null);
  const [downloadUrl, setDownloadUrl] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);

  async function handleUrlSubmit(url: string) {
    setError(null);
    setInfo(null);
    setDownloadUrl(null);
    setLoadingInfo(true);
    try {
      const result = await api.youtubeInfo(url);
      setInfo(result);
      setFormat(result.available_formats.audio[0]?.id ?? "mp3-320");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "정보를 가져오지 못했습니다.");
    } finally {
      setLoadingInfo(false);
    }
  }

  async function startDownload() {
    if (!info) return;
    setError(null);
    setDownloadUrl(null);
    const kind = format.startsWith("mp4") ? "video" : "audio";
    try {
      const job = await api.youtubeExtract(`https://www.youtube.com/watch?v=${info.video_id}`, kind, format);
      setMode("downloading");
      setJobId(job.job_id);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "다운로드를 시작하지 못했습니다.");
    }
  }

  async function startImport() {
    if (!info) return;
    setError(null);
    try {
      const job = await api.youtubeExtract(
        `https://www.youtube.com/watch?v=${info.video_id}`,
        "audio",
        "wav"
      );
      setMode("importing");
      setJobId(job.job_id);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "가져오기를 시작하지 못했습니다.");
    }
  }

  async function handleFile(file: File) {
    setError(null);
    setUploading(true);
    try {
      const result = await api.upload(file);
      router.push(`/studio/${result.media_id}`);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "업로드에 실패했습니다.");
    } finally {
      setUploading(false);
    }
  }

  async function onDownloadComplete(outputs: string[]) {
    setJobId(null);
    if (outputs[0]) {
      const media = await api.downloadUrl(outputs[0]);
      setDownloadUrl(media.url);
      await triggerDownload(outputs[0]); // 바로 저장되도록 — 아래 링크는 실패했을 때를 위한 대비
    }
    setMode("idle");
  }

  async function onImportComplete(outputs: string[]) {
    setJobId(null);
    if (outputs[0]) router.push(`/studio/${outputs[0]}`);
  }

  if (authLoading) return <p className="text-sm text-white/50">불러오는 중…</p>;

  if (!user) {
    return (
      <div className="space-y-4">
        <h1 className="text-xl font-semibold">로그인이 필요합니다</h1>
        <p className="text-sm text-white/50">
          유튜브 추출, 파일 업로드, 보컬/MR 분리, 키·템포 조절은 로그인한 계정만 이용할 수 있어요.
        </p>
        <div className="flex flex-wrap gap-2">
          <a
            href="/login"
            className="rounded-md bg-accent text-ink font-medium px-4 py-2 text-sm whitespace-nowrap"
          >
            로그인
          </a>
          <a
            href="/signup"
            className="rounded-md bg-white/10 hover:bg-white/20 px-4 py-2 text-sm whitespace-nowrap"
          >
            회원가입
          </a>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <section className="space-y-3">
        <h1 className="text-xl font-semibold">🔗 유튜브 링크 붙여넣기 또는 파일 드래그</h1>
        <UrlInput onSubmit={handleUrlSubmit} loading={loadingInfo} />

        <div
          onDragOver={(e) => e.preventDefault()}
          onDrop={(e) => {
            e.preventDefault();
            const file = e.dataTransfer.files?.[0];
            if (file) handleFile(file);
          }}
          onClick={() => fileInputRef.current?.click()}
          className="rounded-lg border border-dashed border-white/20 px-4 py-6 text-center text-sm text-white/50 cursor-pointer hover:border-white/40"
        >
          {uploading ? "업로드 중…" : "또는 MP3/WAV/M4A/FLAC 파일을 여기로 드래그 (최대 1GB / 1시간)"}
          <input
            ref={fileInputRef}
            type="file"
            accept=".mp3,.wav,.m4a,.flac,audio/*"
            className="hidden"
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) handleFile(file);
            }}
          />
        </div>
        {error && <p className="text-sm text-red-400">{error}</p>}
      </section>

      {info && (
        <section className="rounded-lg border border-white/10 bg-panel p-4 space-y-4">
          <div className="flex gap-3">
            {info.thumbnail && (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={info.thumbnail}
                alt=""
                className="w-28 h-16 object-cover rounded-md shrink-0"
              />
            )}
            <div className="flex-1 min-w-0">
              <p className="font-medium truncate">{info.title}</p>
              <p className="text-sm text-white/50 truncate">
                {info.channel} · {Math.floor(info.duration_sec / 60)}:
                {String(info.duration_sec % 60).padStart(2, "0")}
              </p>
            </div>
          </div>

          <div className="space-y-2">
            <p className="text-sm text-white/70">무엇을 할까요?</p>
            <FormatPicker
              audio={info.available_formats.audio}
              video={info.available_formats.video}
              selected={format}
              onSelect={setFormat}
            />
            <div className="flex flex-wrap gap-2 pt-1">
              <button
                onClick={startDownload}
                disabled={mode !== "idle"}
                className="rounded-md bg-white/10 hover:bg-white/20 px-4 py-2 text-sm whitespace-nowrap disabled:opacity-40"
              >
                📥 그냥 다운로드
              </button>
              <button
                onClick={startImport}
                disabled={mode !== "idle"}
                className="rounded-md bg-accent text-ink font-medium px-4 py-2 text-sm whitespace-nowrap disabled:opacity-40"
              >
                🎤 MR 만들기 / 키 바꾸기
              </button>
            </div>
          </div>

          {jobId && mode === "downloading" && (
            <JobProgress
              jobId={jobId}
              onComplete={onDownloadComplete}
              onError={(msg) => {
                setError(msg);
                setMode("idle");
                setJobId(null);
              }}
            />
          )}
          {jobId && mode === "importing" && (
            <JobProgress
              jobId={jobId}
              onComplete={onImportComplete}
              onError={(msg) => {
                setError(msg);
                setMode("idle");
                setJobId(null);
              }}
            />
          )}

          {downloadUrl && (
            <a
              href={downloadUrl}
              className="inline-block rounded-md bg-accent text-ink font-medium px-4 py-2 text-sm"
            >
              ⬇ 다운로드 받기
            </a>
          )}
        </section>
      )}
    </div>
  );
}
