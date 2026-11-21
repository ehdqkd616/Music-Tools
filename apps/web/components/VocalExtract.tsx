"use client";

import { useCallback, useEffect, useState } from "react";
import JobProgress from "@/components/JobProgress";
import { api, ApiError, triggerDownload } from "@/lib/api-client";

interface Track {
  mediaId: string;
  url: string;
}

function TrackRow({ label, track }: { label: string; track: Track }) {
  const [downloading, setDownloading] = useState(false);
  const [failed, setFailed] = useState(false);

  async function download() {
    setDownloading(true);
    setFailed(false);
    try {
      await triggerDownload(track.mediaId);
    } catch {
      setFailed(true);
    } finally {
      setDownloading(false);
    }
  }

  return (
    <div className="flex flex-wrap items-center gap-3">
      <span className="w-28 text-sm text-white/70 shrink-0">{label}</span>
      <audio controls preload="none" src={track.url} className="h-9 min-w-0 flex-1 basis-48" />
      <button
        onClick={download}
        disabled={downloading}
        className="rounded-md border border-white/10 hover:border-white/30 px-3 py-1.5 text-xs disabled:opacity-40"
      >
        {downloading ? "…" : failed ? "다시 시도" : "⬇ WAV"}
      </button>
    </div>
  );
}

type Part = "lead" | "backing";

const PART_BUTTON: Record<Part, string> = {
  lead: "코러스 뺀 보컬만 추출",
  backing: "코러스만 추출",
};

export default function VocalExtract({ vocalsId }: { vocalsId: string }) {
  const [vocals, setVocals] = useState<Track | null>(null);
  const [lead, setLead] = useState<Track | null>(null);
  const [backing, setBacking] = useState<Track | null>(null);
  // 한 번의 분리로 두 트랙이 같이 나오지만, 화면에는 요청한 트랙만 보여준다.
  const [requested, setRequested] = useState<Record<Part, boolean>>({ lead: false, backing: false });
  const [starting, setStarting] = useState<Part | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    api
      .mediaUrl(vocalsId)
      .then(({ url }) => {
        if (!cancelled) setVocals({ mediaId: vocalsId, url });
      })
      .catch(() => {
        if (!cancelled) setError("보컬 파일을 불러오지 못했습니다.");
      });
    return () => {
      cancelled = true;
    };
  }, [vocalsId]);

  // JobProgress는 콜백이 바뀌면 진행 스트림을 다시 연결하므로 참조를 고정한다.
  const handleComplete = useCallback(async (outputs: string[]) => {
    const [leadId, backingId] = outputs;
    try {
      const [leadUrl, backingUrl] = await Promise.all([api.mediaUrl(leadId), api.mediaUrl(backingId)]);
      setLead({ mediaId: leadId, url: leadUrl.url });
      setBacking({ mediaId: backingId, url: backingUrl.url });
    } catch {
      setError("분리한 파일을 불러오지 못했습니다.");
    } finally {
      setJobId(null);
    }
  }, []);

  const handleError = useCallback((message: string) => {
    setJobId(null);
    setError(message);
  }, []);

  async function start(part: Part) {
    setError(null);
    setRequested((prev) => ({ ...prev, [part]: true }));
    if (lead && backing) return; // 이미 분리됐으면 다시 요청하지 않는다 (일일 한도 차감 방지)

    setStarting(part);
    try {
      const job = await api.splitVocals(vocalsId);
      if (job.status === "succeeded" && job.cached) {
        const status = await api.jobStatus(job.job_id);
        await handleComplete(status.output_media ?? []);
      } else {
        setJobId(job.job_id);
      }
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "분리를 시작하지 못했습니다.");
    } finally {
      setStarting(null);
    }
  }

  const showLead = requested.lead && lead;
  const showBacking = requested.backing && backing;
  const remaining = (["lead", "backing"] as Part[]).filter((part) => !(part === "lead" ? showLead : showBacking));

  return (
    <section className="rounded-lg border border-white/10 bg-panel p-4 space-y-3">
      <div>
        <h2 className="text-sm font-medium">보컬 추출</h2>
        <p className="text-xs text-white/50 mt-1">원곡 키 그대로, 각 트랙을 따로 듣고 받을 수 있어요.</p>
      </div>

      {error && <p className="text-sm text-red-400">{error}</p>}

      {vocals && <TrackRow label="🎤 보컬 전체" track={vocals} />}
      {showLead && lead && <TrackRow label="🗣 코러스 뺀 보컬" track={lead} />}
      {showBacking && backing && <TrackRow label="🎶 코러스" track={backing} />}

      {jobId && <JobProgress jobId={jobId} onComplete={handleComplete} onError={handleError} />}

      {remaining.length > 0 && !jobId && (
        <div className="flex flex-wrap items-center gap-3">
          {remaining.map((part) => (
            <button
              key={part}
              onClick={() => start(part)}
              disabled={starting !== null}
              className="rounded-md bg-white/10 hover:bg-white/20 px-4 py-1.5 text-sm disabled:opacity-40"
            >
              {starting === part ? "시작하는 중…" : PART_BUTTON[part]}
            </button>
          ))}
          {!(lead && backing) && (
            <span className="text-xs text-white/50">처음 추출할 때는 곡 길이의 절반 이상 걸릴 수 있어요.</span>
          )}
        </div>
      )}
    </section>
  );
}
