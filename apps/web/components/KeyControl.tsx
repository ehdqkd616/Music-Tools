"use client";

import { shiftKeyLabel } from "@/lib/music";

interface Props {
  tonic: string;
  mode: string;
  semitones: number;
  onChange: (semitones: number) => void;
  onPreview: () => void;
  onApply: () => void;
  previewing?: boolean;
  applying?: boolean;
  previewReady?: boolean; // 현재 semitones가 이미 미리듣기된 상태인지
}

export default function KeyControl({
  tonic,
  mode,
  semitones,
  onChange,
  onPreview,
  onApply,
  previewing,
  applying,
  previewReady,
}: Props) {
  const clamp = (n: number) => Math.max(-12, Math.min(12, n));
  const busy = previewing || applying;

  return (
    <div className="flex flex-wrap items-center gap-3">
      <button
        onClick={() => onChange(clamp(semitones - 1))}
        disabled={busy}
        className="w-8 h-8 rounded-md border border-white/10 hover:border-white/30 disabled:opacity-40"
      >
        −
      </button>

      <div className="text-sm min-w-[11rem] text-center">
        <span className="text-white/50">
          {tonic} {mode.charAt(0).toUpperCase() + mode.slice(1)}
        </span>
        {" → "}
        <span className="font-medium">{shiftKeyLabel(tonic, mode, semitones)}</span>
        <div className="text-xs text-white/40">
          {semitones > 0 ? `+${semitones}` : semitones} 반음
          {Math.abs(semitones) > 7 && <span className="text-amber-400"> · 품질 저하 가능</span>}
        </div>
      </div>

      <button
        onClick={() => onChange(clamp(semitones + 1))}
        disabled={busy}
        className="w-8 h-8 rounded-md border border-white/10 hover:border-white/30 disabled:opacity-40"
      >
        +
      </button>

      <button
        onClick={onPreview}
        disabled={busy || previewReady}
        className="ml-2 rounded-md bg-white/10 hover:bg-white/20 text-sm px-3 py-1.5 disabled:opacity-40"
      >
        {previewing ? "미리듣기 준비 중…" : previewReady ? "✓ 미리듣기 중" : "🔊 미리듣기"}
      </button>

      <button
        onClick={onApply}
        disabled={busy}
        className="rounded-md bg-accent text-ink text-sm font-medium px-3 py-1.5 disabled:opacity-40"
      >
        {applying ? "내보내는 중…" : "적용하고 내보내기"}
      </button>
    </div>
  );
}
