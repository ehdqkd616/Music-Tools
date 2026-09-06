"use client";

import { use, useEffect, useState } from "react";
import JobProgress from "@/components/JobProgress";
import KeyControl from "@/components/KeyControl";
import StemPlayer, { Stem } from "@/components/StemPlayer";
import { api, ApiError, triggerDownload } from "@/lib/api-client";
import { useAuth } from "@/lib/auth-context";
import { waitForJob } from "@/lib/jobs";
import type { AnalyzeResponse } from "@/lib/types";

type Stage = "separating" | "ready" | "previewing" | "exporting";

export default function StudioPage({ params }: { params: Promise<{ id: string }> }) {
  const { id: sourceId } = use(params);
  const { user, loading: authLoading } = useAuth();

  const [analysis, setAnalysis] = useState<AnalyzeResponse | null>(null);
  const [stage, setStage] = useState<Stage>("separating");
  const [separateJobId, setSeparateJobId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // 분리 직후 원본 스템 — 이후로는 절대 덮어쓰지 않는다 (미리듣기/내보내기 모두
  // 항상 여기서부터 다시 피치를 적용해야 이중으로 키가 밀리지 않는다).
  const [originalVocalsId, setOriginalVocalsId] = useState<string | null>(null);
  const [originalInstrumentalId, setOriginalInstrumentalId] = useState<string | null>(null);

  const [semitones, setSemitones] = useState(0);
  const [previewSemitones, setPreviewSemitones] = useState<number | null>(null);

  // 미리듣기(R2/fast)와는 별개로 최종 내보내기(R3/fine) 결과를 캐시해둔다 — 품질이
  // 달라서 미리듣기 결과를 내보내기에 재사용할 수 없으니, 같은 반음으로 내보내기를
  // 두 번 누르는 경우를 위한 캐시가 따로 필요하다.
  const [finalSemitones, setFinalSemitones] = useState<number | null>(null);
  const [finalVocalsId, setFinalVocalsId] = useState<string | null>(null);
  const [finalInstrumentalId, setFinalInstrumentalId] = useState<string | null>(null);

  const [stems, setStems] = useState<Stem[]>([]);
  const [downloadingStem, setDownloadingStem] = useState<string | null>(null);
  const [exportUrl, setExportUrl] = useState<string | null>(null);

  // 분석은 몇 초면 끝나니 분리와 병렬로 먼저 보여준다 (§10.2).
  useEffect(() => {
    if (authLoading || !user) return;
    api.analyze(sourceId).then(setAnalysis).catch(() => {});
  }, [authLoading, user, sourceId]);

  useEffect(() => {
    if (authLoading || !user) return;
    api
      .separate(sourceId, "fast")
      .then(async (job) => {
        if (job.status === "succeeded" && job.cached) {
          const s = await api.jobStatus(job.job_id);
          await handleSeparated(s.output_media ?? []);
        } else {
          setSeparateJobId(job.job_id);
        }
      })
      .catch((e) => setError(e instanceof ApiError ? e.message : "분리를 시작하지 못했습니다."));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [authLoading, user, sourceId]);

  async function loadStems(vocalsId: string, instrumentalId: string) {
    const [vUrl, iUrl] = await Promise.all([api.mediaUrl(vocalsId), api.mediaUrl(instrumentalId)]);
    setStems([
      { name: "vocals", label: "🎤 Vocals", url: vUrl.url, mediaId: vocalsId },
      { name: "instrumental", label: "🎸 MR", url: iUrl.url, mediaId: instrumentalId },
    ]);
  }

  async function handleSeparated(outputs: string[]) {
    const [vocals, instrumental] = outputs;
    setOriginalVocalsId(vocals);
    setOriginalInstrumentalId(instrumental);
    setPreviewSemitones(0); // 처음 보여주는 건 원본(0반음) 그대로이므로 "미리들은 상태"로 취급
    setSeparateJobId(null);
    setStage("ready");
    await loadStems(vocals, instrumental);
  }

  async function handlePreview() {
    if (!originalVocalsId || !originalInstrumentalId) return;
    setError(null);

    if (semitones === 0) {
      setPreviewSemitones(0);
      await loadStems(originalVocalsId, originalInstrumentalId);
      return;
    }

    setStage("previewing");
    try {
      const [[newVocals], [newInstrumental]] = await Promise.all([
        api.pitch(originalVocalsId, semitones, "vocals", true).then((job) => waitForJob(job.job_id)),
        api.pitch(originalInstrumentalId, semitones, "other", true).then((job) => waitForJob(job.job_id)),
      ]);

      setPreviewSemitones(semitones);
      await loadStems(newVocals, newInstrumental);
    } catch (e) {
      setError(e instanceof Error ? e.message : "미리듣기를 만들지 못했습니다.");
    } finally {
      setStage("ready");
    }
  }

  async function handleApply() {
    if (!originalVocalsId || !originalInstrumentalId) return;
    setError(null);
    setExportUrl(null);
    setStage("exporting");
    try {
      let finalVocals: string;
      let finalInstrumental: string;

      if (semitones === 0) {
        finalVocals = originalVocalsId;
        finalInstrumental = originalInstrumentalId;
      } else if (finalSemitones === semitones && finalVocalsId && finalInstrumentalId) {
        // 같은 반음으로 이미 고품질(R3) 내보내기를 해뒀으면 재사용 — 미리듣기(R2)
        // 결과는 품질이 달라서 여기 재사용하면 안 된다.
        finalVocals = finalVocalsId;
        finalInstrumental = finalInstrumentalId;
      } else {
        const [[newVocals], [newInstrumental]] = await Promise.all([
          api.pitch(originalVocalsId, semitones, "vocals", false).then((job) => waitForJob(job.job_id)),
          api.pitch(originalInstrumentalId, semitones, "other", false).then((job) => waitForJob(job.job_id)),
        ]);
        finalVocals = newVocals;
        finalInstrumental = newInstrumental;
        setFinalSemitones(semitones);
        setFinalVocalsId(newVocals);
        setFinalInstrumentalId(newInstrumental);
      }

      const mixJob = await api.mix([finalVocals, finalInstrumental], "mp3-320", semitones);
      const [finalId] = await waitForJob(mixJob.job_id);
      const { url } = await api.downloadUrl(finalId);
      setExportUrl(url);
    } catch (e) {
      setError(e instanceof Error ? e.message : "내보내기에 실패했습니다.");
    } finally {
      setStage("ready");
    }
  }

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

  function jobError(msg: string) {
    setError(msg);
    setSeparateJobId(null);
    setStage("ready");
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

      {stage === "separating" && separateJobId && (
        <JobProgress jobId={separateJobId} onComplete={handleSeparated} onError={jobError} />
      )}

      {stems.length > 0 && (
        <section className="rounded-lg border border-white/10 bg-panel p-4 space-y-4">
          <StemPlayer stems={stems} onDownload={handleStemDownload} downloadingName={downloadingStem} />

          {analysis?.key_tonic && analysis?.key_mode && (
            <KeyControl
              tonic={analysis.key_tonic}
              mode={analysis.key_mode}
              semitones={semitones}
              onChange={setSemitones}
              onPreview={handlePreview}
              onApply={handleApply}
              previewing={stage === "previewing"}
              applying={stage === "exporting"}
              previewReady={previewSemitones === semitones}
            />
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
