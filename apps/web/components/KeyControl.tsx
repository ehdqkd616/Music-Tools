"use client";

import { useState } from "react";
import { shiftKeyLabel } from "@/lib/music";

interface Props {
  tonic: string;
  mode: string;
  onApply: (semitones: number) => void;
  applying?: boolean;
}

export default function KeyControl({ tonic, mode, onApply, applying }: Props) {
  const [semitones, setSemitones] = useState(0);
  const clamp = (n: number) => Math.max(-12, Math.min(12, n));

  return (
    <div className="flex items-center gap-3">
      <button
        onClick={() => setSemitones((s) => clamp(s - 1))}
        className="w-8 h-8 rounded-md border border-white/10 hover:border-white/30"
      >
        −
      </button>

      <div className="text-sm min-w-[11rem] text-center">
        <span className="text-white/50">{tonic} {mode.charAt(0).toUpperCase() + mode.slice(1)}</span>
        {" → "}
        <span className="font-medium">{shiftKeyLabel(tonic, mode, semitones)}</span>
        <div className="text-xs text-white/40">
          {semitones > 0 ? `+${semitones}` : semitones} 반음
          {Math.abs(semitones) > 7 && <span className="text-amber-400"> · 품질 저하 가능</span>}
        </div>
      </div>

      <button
        onClick={() => setSemitones((s) => clamp(s + 1))}
        className="w-8 h-8 rounded-md border border-white/10 hover:border-white/30"
      >
        +
      </button>

      <button
        onClick={() => onApply(semitones)}
        disabled={semitones === 0 || applying}
        className="ml-2 rounded-md bg-accent text-ink text-sm font-medium px-3 py-1.5 disabled:opacity-40"
      >
        {applying ? "적용 중…" : "적용하고 내보내기"}
      </button>
    </div>
  );
}
