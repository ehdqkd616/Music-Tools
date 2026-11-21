"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import JobProgress from "@/components/JobProgress";
import ScoreViewer from "@/components/ScoreViewer";
import SourceInput from "@/components/SourceInput";
import { api, ApiError, triggerDownload } from "@/lib/api-client";
import { useAuth } from "@/lib/auth-context";
import { INSTRUMENTS, isInstrument, type Instrument } from "@/lib/instruments";

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

export default function TranscribePage() {
  const { user, loading: authLoading } = useAuth();
  const autoStartedRef = useRef(false);

  const [instrument, setInstrument] = useState<Instrument>("piano");
  // 내 작업·악기별 분리에서 넘어온 곡 (?media=...)
  const [presetMediaId, setPresetMediaId] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);
  const [jobId, setJobId] = useState<string | null>(null);
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
    async (mediaId: string, chosen: Instrument) => {
      setError(null);
      setStarting(true);
      try {
        const job = await api.transcribe(mediaId, chosen);
        if (job.status === "succeeded" && job.cached) {
          const status = await api.jobStatus(job.job_id);
          await handleComplete(status.output_media ?? []);
        } else {
          setJobId(job.job_id);
        }
      } catch (e) {
        setError(e instanceof ApiError ? e.message : "채보를 시작하지 못했습니다.");
      } finally {
        setStarting(false);
      }
    },
    [handleComplete],
  );

  // ?instrument=...&media=... — 둘 다 있으면(악기별 분리의 트랙 채보) 바로 시작하고,
  // 곡만 있으면(내 작업) 악기를 고른 뒤 시작한다.
  useEffect(() => {
    if (authLoading || !user || autoStartedRef.current) return;
    autoStartedRef.current = true; // 개발 모드의 effect 이중 실행으로 작업이 두 번 생기지 않게
    const params = new URLSearchParams(window.location.search);
    const requested = params.get("instrument");
    const mediaId = params.get("media");
    const chosen = isInstrument(requested) ? requested : "piano";
    setInstrument(chosen);
    if (!mediaId) return;
    setPresetMediaId(mediaId);
    if (isInstrument(requested)) void startTranscribe(mediaId, chosen);
  }, [authLoading, user, startTranscribe]);

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
    setPresetMediaId(null);
    window.history.replaceState(null, "", "/transcribe");
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

  const choosing = !result && !jobId;
  const selected = INSTRUMENTS.find((i) => i.value === instrument) ?? INSTRUMENTS[0];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-lg font-semibold">채보</h1>
        <p className="text-sm text-white/60 mt-1">
          악기 하나만 연주한 음원을 올리거나 유튜브 링크를 붙여넣으면 MIDI, MusicXML, PDF 악보로 만들어 드려요.
        </p>
        <p className="text-xs text-white/40 mt-1">
          여러 악기가 섞인 곡은 &quot;악기별 분리&quot;로 먼저 나눈 뒤 트랙을 채보하세요. 드럼은 음 높이가 없어
          채보하지 않아요. 악보는 자동으로 박자를 맞춘 초안이라 MuseScore 같은 프로그램에서 다듬어 쓰는 걸 권해요.
        </p>
      </div>

      {error && <p className="text-sm text-red-400">{error}</p>}

      {choosing && (
        <>
          <div className="grid gap-2 grid-cols-2 sm:grid-cols-4">
            {INSTRUMENTS.map((option) => (
              <button
                key={option.value}
                onClick={() => setInstrument(option.value)}
                disabled={starting}
                aria-pressed={instrument === option.value}
                className={`rounded-lg border px-3 py-2.5 text-left disabled:opacity-40 ${
                  instrument === option.value ? "border-accent bg-accent/10" : "border-white/10 hover:border-white/30"
                }`}
              >
                <span className="block text-sm font-medium">{option.label}</span>
                <span className="block text-xs text-white/50 mt-0.5">{option.detail}</span>
              </button>
            ))}
          </div>

          {presetMediaId ? (
            <div className="flex flex-wrap items-center gap-3">
              <button
                onClick={() => void startTranscribe(presetMediaId, instrument)}
                disabled={starting}
                className="rounded-md bg-accent text-ink font-medium px-4 py-2 text-sm disabled:opacity-40"
              >
                {starting ? "시작하는 중…" : `내 작업에서 고른 곡을 ${selected.label}로 채보하기`}
              </button>
              <button onClick={reset} className="text-sm text-white/50 hover:text-white">
                다른 곡 고르기
              </button>
            </div>
          ) : (
            <SourceInput
              disabled={starting}
              hint={starting ? "채보를 시작하는 중…" : `MP3 · WAV · M4A · FLAC, ${selected.duration}`}
              onReady={(mediaId, title) => {
                setSourceTitle(title);
                void startTranscribe(mediaId, instrument);
              }}
            />
          )}
        </>
      )}

      {!choosing && (
        <p className="text-sm text-white/70 truncate">
          {selected.label}
          {sourceTitle && ` · ${sourceTitle}`}
        </p>
      )}

      {jobId && <JobProgress jobId={jobId} onComplete={handleComplete} onError={handleError} />}

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
              다른 곡 채보하기
            </button>
          </div>
          <ScoreViewer url={result.scoreUrl} />
        </section>
      )}
    </div>
  );
}
