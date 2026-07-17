"use client";

import { use, useEffect, useState } from "react";
import JobProgress from "@/components/JobProgress";
import KeyControl from "@/components/KeyControl";
import StemPlayer, { Stem } from "@/components/StemPlayer";
import { api, ApiError } from "@/lib/api-client";
import type { AnalyzeResponse } from "@/lib/types";

type Stage =
  | "separating"
  | "ready"
  | "pitching_vocals"
  | "pitching_instrumental"
  | "mixing"
  | "done";

export default function StudioPage({ params }: { params: Promise<{ id: string }> }) {
  const { id: sourceId } = use(params);

  const [analysis, setAnalysis] = useState<AnalyzeResponse | null>(null);
  const [stage, setStage] = useState<Stage>("separating");
  const [jobId, setJobId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [vocalsId, setVocalsId] = useState<string | null>(null);
  const [instrumentalId, setInstrumentalId] = useState<string | null>(null);
  const [stems, setStems] = useState<Stem[]>([]);
  const [pendingSemitones, setPendingSemitones] = useState(0);
  const [exportUrl, setExportUrl] = useState<string | null>(null);

  // Analysis is fast (§10.2 #2) — fetch it in parallel while separation runs.
  useEffect(() => {
    api.analyze(sourceId).then(setAnalysis).catch(() => {});
  }, [sourceId]);

  // Kick off separation as soon as the page loads.
  useEffect(() => {
    api
      .separate(sourceId, "fast")
      .then((job) => {
        if (job.status === "succeeded" && job.cached) {
          // Cache hit — job response alone doesn't carry output ids, re-poll once.
          api.jobStatus(job.job_id).then((s) => handleSeparated(s.output_media ?? []));
        } else {
          setJobId(job.job_id);
        }
      })
      .catch((e) => setError(e instanceof ApiError ? e.message : "분리를 시작하지 못했습니다."));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sourceId]);

  async function handleSeparated(outputs: string[]) {
    const [vocals, instrumental] = outputs;
    setVocalsId(vocals);
    setInstrumentalId(instrumental);
    setJobId(null);
    setStage("ready");

    const urls = await Promise.all(
      [
        { id: vocals, name: "vocals", label: "🎤 Vocals" },
        { id: instrumental, name: "instrumental", label: "🎸 MR" },
      ].map(async (s) => ({ ...s, url: (await api.mediaUrl(s.id)).url }))
    );
    setStems(urls.map(({ name, label, url }) => ({ name, label, url })));
  }

  async function applyKeyChange(semitones: number) {
    if (!vocalsId || !instrumentalId) return;
    setPendingSemitones(semitones);
    setExportUrl(null);
    setStage("pitching_vocals");
    try {
      const job = await api.pitch(vocalsId, semitones, "vocals");
      setJobId(job.job_id);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "키 변경을 시작하지 못했습니다.");
      setStage("ready");
    }
  }

  async function onVocalsPitched(outputs: string[]) {
    setJobId(null);
    const newVocals = outputs[0];
    setVocalsId(newVocals);
    setStage("pitching_instrumental");
    try {
      const job = await api.pitch(instrumentalId!, pendingSemitones, "other");
      setJobId(job.job_id);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "키 변경을 시작하지 못했습니다.");
      setStage("ready");
    }
  }

  async function onInstrumentalPitched(outputs: string[]) {
    setJobId(null);
    const newInstrumental = outputs[0];
    setInstrumentalId(newInstrumental);
    setStage("mixing");
    try {
      const job = await api.mix([vocalsId!, newInstrumental], "mp3-320");
      setJobId(job.job_id);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "믹스를 시작하지 못했습니다.");
      setStage("ready");
    }
  }

  async function onMixed(outputs: string[]) {
    setJobId(null);
    setStage("done");
    if (outputs[0]) {
      const media = await api.mediaUrl(outputs[0]);
      setExportUrl(media.url);
    }
  }

  const jobError = (msg: string) => {
    setError(msg);
    setJobId(null);
    setStage("ready");
  };

  return (
    <div className="space-y-6">
      {error && <p className="text-sm text-red-400">{error}</p>}

      {analysis && (
        <div className="flex gap-3 text-sm text-white/60">
          {analysis.key && <span>{analysis.key}</span>}
          {analysis.bpm && <span>{analysis.bpm} BPM</span>}
          {analysis.lufs_integrated != null && <span>{analysis.lufs_integrated} LUFS</span>}
        </div>
      )}

      {stage === "separating" && jobId && (
        <JobProgress jobId={jobId} onComplete={handleSeparated} onError={jobError} />
      )}

      {stems.length > 0 && (
        <section className="rounded-lg border border-white/10 bg-panel p-4 space-y-4">
          <StemPlayer stems={stems} />

          {analysis?.key_tonic && analysis?.key_mode && (
            <KeyControl
              tonic={analysis.key_tonic}
              mode={analysis.key_mode}
              onApply={applyKeyChange}
              applying={stage !== "ready" && stage !== "done"}
            />
          )}

          {stage === "pitching_vocals" && jobId && (
            <JobProgress jobId={jobId} onComplete={onVocalsPitched} onError={jobError} />
          )}
          {stage === "pitching_instrumental" && jobId && (
            <JobProgress jobId={jobId} onComplete={onInstrumentalPitched} onError={jobError} />
          )}
          {stage === "mixing" && jobId && (
            <JobProgress jobId={jobId} onComplete={onMixed} onError={jobError} />
          )}

          {exportUrl && (
            <a
              href={exportUrl}
              className="inline-block rounded-md bg-accent text-ink font-medium px-4 py-2 text-sm"
            >
              ⬇ 내보낸 파일 다운로드
            </a>
          )}
        </section>
      )}
    </div>
  );
}
