"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import JobProgress from "@/components/JobProgress";
import SourceInput from "@/components/SourceInput";
import StemPlayer, { Stem } from "@/components/StemPlayer";
import { api, ApiError, triggerDownload } from "@/lib/api-client";
import { useAuth } from "@/lib/auth-context";

type StemCount = 4 | 6;

// 스템 -> 채보 악기 (드럼은 음 높이가 없어 채보하지 않는다)
const STEM_INSTRUMENT: Record<string, string> = {
  vocals: "vocals",
  bass: "bass",
  guitar: "guitar",
  piano: "piano",
  other: "other",
};

// services/common/stems.py의 STEM_ORDER와 같은 순서여야 한다. 출력은 WAV N개 + 재생용 MP3 N개.
const STEM_ORDER: Record<StemCount, string[]> = {
  4: ["vocals", "drums", "bass", "other"],
  6: ["vocals", "drums", "bass", "guitar", "piano", "other"],
};

const STEM_LABEL: Record<string, string> = {
  vocals: "🎤 보컬",
  drums: "🥁 드럼",
  bass: "🎵 베이스",
  guitar: "🎸 기타",
  piano: "🎹 피아노",
  other: "🎼 나머지",
};

const COUNT_OPTIONS: { value: StemCount; title: string; detail: string }[] = [
  { value: 4, title: "4개로 나누기", detail: "보컬 · 드럼 · 베이스 · 나머지" },
  { value: 6, title: "6개로 나누기", detail: "+ 기타 · 피아노 (피아노는 다른 악기가 섞이기 쉬워요)" },
];

export default function StemsPage() {
  const { user, loading: authLoading } = useAuth();
  const autoStartedRef = useRef(false);

  const [count, setCount] = useState<StemCount>(4);
  // 진행 중인 작업이 몇 개로 나누는지 — 완료 콜백 참조를 고정하려고 ref로도 둔다.
  const activeCountRef = useRef<StemCount>(4);
  const [starting, setStarting] = useState(false);
  const [jobId, setJobId] = useState<string | null>(null);
  const [sourceTitle, setSourceTitle] = useState<string | null>(null);
  const [stems, setStems] = useState<Stem[]>([]);
  const [volumes, setVolumes] = useState<Record<string, number>>({});
  const [downloadingStem, setDownloadingStem] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleComplete = useCallback(async (outputs: string[]) => {
    const names = STEM_ORDER[activeCountRef.current];
    try {
      if (outputs.length < names.length * 2) throw new Error("unexpected outputs");
      const previews = await Promise.all(names.map((_, i) => api.mediaUrl(outputs[names.length + i])));
      setStems(
        names.map((name, i) => ({
          name,
          label: STEM_LABEL[name] ?? name,
          url: previews[i].url, // 재생은 가벼운 MP3로
          mediaId: outputs[i], // 다운로드는 원본 WAV로
        })),
      );
      setVolumes(Object.fromEntries(names.map((name) => [name, 1])));
    } catch {
      setError("분리한 트랙을 불러오지 못했습니다.");
    } finally {
      setJobId(null);
    }
  }, []);

  const handleError = useCallback((message: string) => {
    setJobId(null);
    setError(message);
  }, []);

  const startSeparate = useCallback(
    async (mediaId: string, stemCount: StemCount) => {
      setError(null);
      setStarting(true);
      activeCountRef.current = stemCount;
      try {
        const job = await api.separate(mediaId, "fast", stemCount);
        if (job.status === "succeeded" && job.cached) {
          const status = await api.jobStatus(job.job_id);
          await handleComplete(status.output_media ?? []);
        } else {
          setJobId(job.job_id);
        }
      } catch (e) {
        setError(e instanceof ApiError ? e.message : "분리를 시작하지 못했습니다.");
      } finally {
        setStarting(false);
      }
    },
    [handleComplete],
  );

  // 내 작업에서 "악기 분리"로 들어온 경우 (?media=...) 4개 분리로 바로 시작한다.
  useEffect(() => {
    if (authLoading || !user || autoStartedRef.current) return;
    const mediaId = new URLSearchParams(window.location.search).get("media");
    if (!mediaId) return;
    autoStartedRef.current = true; // 개발 모드의 effect 이중 실행으로 작업이 두 번 생기지 않게
    void startSeparate(mediaId, 4);
  }, [authLoading, user, startSeparate]);

  async function handleStemDownload(stem: Stem) {
    setDownloadingStem(stem.name);
    try {
      await triggerDownload(stem.mediaId);
    } catch {
      setError("다운로드에 실패했습니다.");
    } finally {
      setDownloadingStem(null);
    }
  }

  function reset() {
    setStems([]);
    setError(null);
    setSourceTitle(null);
    window.history.replaceState(null, "", "/stems");
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

  const choosing = stems.length === 0 && !jobId;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-lg font-semibold">악기별 분리</h1>
        <p className="text-sm text-white/60 mt-1">
          유튜브 링크나 음원 파일을 넣으면 악기별 트랙으로 나눠서 따로 듣고 받을 수 있어요.
        </p>
      </div>

      {error && <p className="text-sm text-red-400">{error}</p>}

      {choosing && (
        <>
          <div className="grid gap-2 sm:grid-cols-2">
            {COUNT_OPTIONS.map((option) => (
              <button
                key={option.value}
                onClick={() => setCount(option.value)}
                disabled={starting}
                aria-pressed={count === option.value}
                className={`rounded-lg border px-4 py-3 text-left disabled:opacity-40 ${
                  count === option.value ? "border-accent bg-accent/10" : "border-white/10 hover:border-white/30"
                }`}
              >
                <span className="block text-sm font-medium">{option.title}</span>
                <span className="block text-xs text-white/50 mt-0.5">{option.detail}</span>
              </button>
            ))}
          </div>
          <SourceInput
            disabled={starting}
            hint={starting ? "분리를 시작하는 중…" : "MP3 · WAV · M4A · FLAC, 보통 1~2분 걸려요."}
            onReady={(mediaId, title) => {
              setSourceTitle(title);
              void startSeparate(mediaId, count);
            }}
          />
        </>
      )}

      {sourceTitle && !choosing && <p className="text-sm text-white/70 truncate">🎵 {sourceTitle}</p>}

      {jobId && <JobProgress jobId={jobId} onComplete={handleComplete} onError={handleError} />}

      {stems.length > 0 && (
        <section className="rounded-lg border border-white/10 bg-panel p-4 space-y-4">
          <StemPlayer
            stems={stems}
            volumes={volumes}
            onVolumeChange={(name, value) => setVolumes((prev) => ({ ...prev, [name]: value }))}
            onDownload={handleStemDownload}
            downloadingName={downloadingStem}
            soloable
          />
          <p className="text-xs text-white/40">⬇ 버튼은 원본 음질(WAV)로 받아요.</p>
          <div className="space-y-2">
            <p className="text-xs text-white/50">트랙을 악보로 (새 탭에서 열려요)</p>
            <div className="flex flex-wrap gap-2">
              {stems
                .filter((stem) => STEM_INSTRUMENT[stem.name])
                .map((stem) => (
                  <a
                    key={stem.name}
                    href={`/transcribe?instrument=${STEM_INSTRUMENT[stem.name]}&media=${stem.mediaId}`}
                    target="_blank"
                    rel="noopener"
                    className="rounded-md border border-white/10 hover:border-white/30 px-3 py-1.5 text-xs"
                  >
                    {stem.label} 채보
                  </a>
                ))}
            </div>
          </div>
          <button onClick={reset} className="rounded-md bg-white/10 hover:bg-white/20 px-3 py-1.5 text-sm">
            다른 곡 분리하기
          </button>
        </section>
      )}
    </div>
  );
}
