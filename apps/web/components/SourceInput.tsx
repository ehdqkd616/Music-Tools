"use client";

import { useCallback, useRef, useState } from "react";
import JobProgress from "@/components/JobProgress";
import UrlInput from "@/components/UrlInput";
import { api, ApiError } from "@/lib/api-client";

interface Props {
  // 음원이 서버에 준비되면 호출된다 (업로드 완료, 또는 유튜브 오디오 가져오기 완료).
  onReady: (mediaId: string, title: string | null) => void;
  disabled?: boolean;
  hint?: string;
}

// 유튜브 링크 또는 파일 업로드로 음원을 받아 media id를 넘겨준다.
export default function SourceInput({ onReady, disabled, hint }: Props) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState<"fetching" | "uploading" | null>(null);
  const [downloadJobId, setDownloadJobId] = useState<string | null>(null);
  const [title, setTitle] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // JobProgress 콜백 참조를 고정하기 위해 최신 값은 ref로 읽는다.
  const onReadyRef = useRef(onReady);
  onReadyRef.current = onReady;
  const titleRef = useRef(title);
  titleRef.current = title;

  const handleDownloaded = useCallback((outputs: string[]) => {
    setDownloadJobId(null);
    if (outputs[0]) onReadyRef.current(outputs[0], titleRef.current);
    else setError("유튜브 오디오를 가져오지 못했습니다.");
  }, []);

  const handleDownloadError = useCallback((message: string) => {
    setDownloadJobId(null);
    setError(message);
  }, []);

  async function handleYoutube(url: string) {
    setError(null);
    setBusy("fetching");
    try {
      const info = await api.youtubeInfo(url);
      setTitle(info.title);
      titleRef.current = info.title;
      const job = await api.youtubeExtract(`https://www.youtube.com/watch?v=${info.video_id}`, "audio", "wav");
      if (job.status === "succeeded" && job.cached) {
        const status = await api.jobStatus(job.job_id);
        handleDownloaded(status.output_media ?? []);
      } else {
        setDownloadJobId(job.job_id);
      }
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "유튜브에서 가져오지 못했습니다.");
    } finally {
      setBusy(null);
    }
  }

  async function handleFile(file: File) {
    setError(null);
    setBusy("uploading");
    try {
      const uploaded = await api.upload(file);
      onReadyRef.current(uploaded.media_id, uploaded.title ?? file.name.replace(/\.[^.]+$/, ""));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "업로드에 실패했습니다.");
    } finally {
      setBusy(null);
    }
  }

  if (downloadJobId) {
    return (
      <div className="space-y-2">
        {title && <p className="text-sm text-white/70 truncate">🎵 {title}</p>}
        <JobProgress jobId={downloadJobId} onComplete={handleDownloaded} onError={handleDownloadError} />
      </div>
    );
  }

  const locked = disabled || busy !== null;

  return (
    <div className="space-y-3">
      <UrlInput onSubmit={(url) => void handleYoutube(url)} loading={busy === "fetching"} />
      <div className="flex flex-wrap items-center gap-3">
        <input
          ref={fileInputRef}
          type="file"
          accept="audio/*,.mp3,.wav,.m4a,.flac"
          className="hidden"
          onChange={(e) => {
            const file = e.target.files?.[0];
            e.target.value = "";
            if (file) void handleFile(file);
          }}
        />
        <button
          onClick={() => fileInputRef.current?.click()}
          disabled={locked}
          className="rounded-md border border-white/20 hover:border-white/40 px-4 py-2 text-sm disabled:opacity-40"
        >
          {busy === "uploading" ? "올리는 중…" : "또는 파일 올리기"}
        </button>
        {hint && <span className="text-xs text-white/50">{hint}</span>}
      </div>
      {error && <p className="text-sm text-red-400">{error}</p>}
    </div>
  );
}
