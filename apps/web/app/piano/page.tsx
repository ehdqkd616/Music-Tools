"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import JobProgress from "@/components/JobProgress";
import ScoreViewer from "@/components/ScoreViewer";
import UrlInput from "@/components/UrlInput";
import { api, ApiError, triggerDownload } from "@/lib/api-client";
import { useAuth } from "@/lib/auth-context";

interface Result {
  midiId: string;
  musicxmlId: string;
  pdfId: string;
  scoreUrl: string;
}

const DOWNLOADS: { key: keyof Omit<Result, "scoreUrl">; label: string }[] = [
  { key: "pdfId", label: "⬇ PDF 악보" },
  { key: "musicxmlId", label: "⬇ MusicXML" },
  { key: "midiId", label: "⬇ MIDI" },
];

export default function PianoPage() {
  const { user, loading: authLoading } = useAuth();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const autoStartedRef = useRef(false);

  const [busy, setBusy] = useState<"fetching" | "uploading" | "starting" | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);
  // 유튜브는 오디오를 먼저 가져온(download) 다음 채보(transcribe)로 이어진다.
  const [jobKind, setJobKind] = useState<"download" | "transcribe">("transcribe");
  const [sourceTitle, setSourceTitle] = useState<string | null>(null);
  const [result, setResult] = useState<Result | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [downloading, setDownloading] = useState<string | null>(null);

  // JobProgress는 콜백이 바뀌면 진행 스트림을 다시 연결하므로 참조를 고정한다.
  const handleComplete = useCallback(async (outputs: string[]) => {
    const [midiId, musicxmlId, pdfId] = outputs;
    try {
      const { url } = await api.mediaUrl(musicxmlId);
      setResult({ midiId, musicxmlId, pdfId, scoreUrl: url });
    } catch {
      setError("채보 결과를 불러오지 못했습니다.");
    } finally {
      setJobId(null);
    }
  }, []);

  const handleError = useCallback((message: string) => {
    setJobId(null);
    setError(message);
  }, []);

  const startTranscribe = useCallback(
    async (mediaId: string) => {
      setBusy("starting");
      try {
        const job = await api.transcribe(mediaId);
        if (job.status === "succeeded" && job.cached) {
          const status = await api.jobStatus(job.job_id);
          await handleComplete(status.output_media ?? []);
        } else {
          setJobKind("transcribe");
          setJobId(job.job_id);
        }
      } catch (e) {
        setError(e instanceof ApiError ? e.message : "채보를 시작하지 못했습니다.");
      } finally {
        setBusy(null);
      }
    },
    [handleComplete],
  );

  const handleDownloaded = useCallback(
    async (outputs: string[]) => {
      setJobId(null);
      if (!outputs[0]) {
        setError("유튜브 오디오를 가져오지 못했습니다.");
        return;
      }
      await startTranscribe(outputs[0]);
    },
    [startTranscribe],
  );

  async function handleYoutube(url: string) {
    setError(null);
    setResult(null);
    setBusy("fetching");
    try {
      const info = await api.youtubeInfo(url);
      setSourceTitle(info.title);
      const job = await api.youtubeExtract(`https://www.youtube.com/watch?v=${info.video_id}`, "audio", "wav");
      if (job.status === "succeeded" && job.cached) {
        const status = await api.jobStatus(job.job_id);
        await handleDownloaded(status.output_media ?? []);
      } else {
        setJobKind("download");
        setJobId(job.job_id);
      }
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "유튜브에서 가져오지 못했습니다.");
    } finally {
      setBusy(null);
    }
  }

  // 내 작업에서 "채보"로 들어온 경우 (?media=...) 바로 시작한다.
  useEffect(() => {
    if (authLoading || !user || autoStartedRef.current) return;
    const mediaId = new URLSearchParams(window.location.search).get("media");
    if (!mediaId) return;
    autoStartedRef.current = true; // 개발 모드의 effect 이중 실행으로 작업이 두 번 생기지 않게
    void startTranscribe(mediaId);
  }, [authLoading, user, startTranscribe]);

  async function handleFile(file: File) {
    setError(null);
    setResult(null);
    setSourceTitle(file.name.replace(/\.[^.]+$/, ""));
    setBusy("uploading");
    try {
      const uploaded = await api.upload(file);
      await startTranscribe(uploaded.media_id);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "업로드에 실패했습니다.");
      setBusy(null);
    }
  }

  async function handleDownload(mediaId: string) {
    setDownloading(mediaId);
    try {
      await triggerDownload(mediaId);
    } catch {
      setError("다운로드에 실패했습니다.");
    } finally {
      setDownloading(null);
    }
  }

  function reset() {
    setResult(null);
    setError(null);
    setSourceTitle(null);
    window.history.replaceState(null, "", "/piano");
  }

  if (authLoading) return <p className="text-sm text-white/50">불러오는 중…</p>;

  if (!user) {
    return (
      <div className="space-y-4">
        <h1 className="text-lg font-semibold">로그인이 필요합니다</h1>
        <a href="/login" className="inline-block rounded-md bg-accent text-ink font-medium px-4 py-2 text-sm">
          로그인
        </a>
      </div>
    );
  }

  const working = busy !== null || jobId !== null;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-lg font-semibold">피아노 채보</h1>
        <p className="text-sm text-white/60 mt-1">
          피아노 독주 음원 파일을 올리거나 유튜브 링크를 붙여넣으면 MIDI, MusicXML, PDF 악보로 만들어 드려요.
        </p>
        <p className="text-xs text-white/40 mt-1">
          노래나 다른 악기가 섞인 곡은 정확도가 크게 떨어져요. 악보는 자동으로 박자를 맞춘 초안이라 MuseScore
          같은 프로그램에서 다듬어 쓰는 걸 권해요.
        </p>
      </div>

      {error && <p className="text-sm text-red-400">{error}</p>}

      {!result && !jobId && (
        <UrlInput onSubmit={(url) => void handleYoutube(url)} loading={busy === "fetching"} />
      )}

      {!result && !jobId && (
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
            disabled={working}
            className="rounded-md bg-accent text-ink font-medium px-4 py-2 text-sm disabled:opacity-40"
          >
            {busy === "uploading" ? "올리는 중…" : busy === "starting" ? "시작하는 중…" : "또는 파일 올리기"}
          </button>
          <span className="text-xs text-white/50">MP3 · WAV · M4A · FLAC, 곡 길이와 비슷한 시간이 걸려요.</span>
        </div>
      )}

      {sourceTitle && (jobId || result) && <p className="text-sm text-white/70 truncate">🎵 {sourceTitle}</p>}

      {jobId && (
        <JobProgress
          jobId={jobId}
          onComplete={jobKind === "download" ? handleDownloaded : handleComplete}
          onError={handleError}
        />
      )}

      {result && (
        <section className="space-y-4">
          <div className="flex flex-wrap items-center gap-2">
            {DOWNLOADS.map(({ key, label }) => (
              <button
                key={key}
                onClick={() => handleDownload(result[key])}
                disabled={downloading === result[key]}
                className="rounded-md border border-white/10 hover:border-white/30 px-3 py-1.5 text-sm disabled:opacity-40"
              >
                {downloading === result[key] ? "…" : label}
              </button>
            ))}
            <button onClick={reset} className="rounded-md bg-white/10 hover:bg-white/20 px-3 py-1.5 text-sm">
              다른 파일 채보하기
            </button>
          </div>
          <ScoreViewer url={result.scoreUrl} />
        </section>
      )}
    </div>
  );
}
