"use client";

import type { FormatOption } from "@/lib/types";

interface Props {
  audio: FormatOption[];
  video: FormatOption[];
  selected: string;
  onSelect: (formatId: string) => void;
}

export default function FormatPicker({ audio, video, selected, onSelect }: Props) {
  return (
    <div className="flex flex-wrap gap-2">
      {[...audio, ...video].map((f) => (
        <button
          key={f.id}
          onClick={() => onSelect(f.id)}
          className={`rounded-md border px-3 py-1.5 text-xs ${
            selected === f.id
              ? "border-accent text-accent bg-accent/10"
              : "border-white/10 text-white/70 hover:border-white/30"
          }`}
        >
          {f.label} · {f.est_size_mb}MB
        </button>
      ))}
    </div>
  );
}
