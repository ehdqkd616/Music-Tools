"use client";

import { useEffect, useRef, useState } from "react";

export interface Stem {
  name: string;
  label: string;
  url: string;
}

interface Props {
  stems: Stem[];
}

// Each stem gets its own WaveSurfer instance. wavesurfer.js v7 has no public
// option to share a single AudioContext across instances, so sync instead
// follows the master track's `audioprocess` event and snaps any stem that
// has drifted more than 50ms (§10.2's intent, adapted to the actual API).
export default function StemPlayer({ stems }: Props) {
  const containerRefs = useRef<Record<string, HTMLDivElement | null>>({});
  const wsRefs = useRef<Record<string, any>>({});
  const [playing, setPlaying] = useState(false);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    let cancelled = false;

    (async () => {
      const { default: WaveSurfer } = await import("wavesurfer.js");
      if (cancelled) return;

      for (const stem of stems) {
        const container = containerRefs.current[stem.name];
        if (!container) continue;
        const ws = WaveSurfer.create({
          container,
          height: 56,
          normalize: true,
          waveColor: "#4b5563",
          progressColor: "#6ee7b7",
          url: stem.url,
          backend: "WebAudio",
        });
        wsRefs.current[stem.name] = ws;
      }

      const master = wsRefs.current[stems[0]?.name];
      master?.on("audioprocess", () => {
        const t = master.getCurrentTime();
        for (const name of Object.keys(wsRefs.current)) {
          if (name === stems[0]?.name) continue;
          const ws = wsRefs.current[name];
          if (Math.abs(ws.getCurrentTime() - t) > 0.05) ws.setTime(t);
        }
      });
      master?.on("ready", () => setReady(true));
    })();

    return () => {
      cancelled = true;
      Object.values(wsRefs.current).forEach((ws) => ws.destroy());
      wsRefs.current = {};
    };
  }, [stems]);

  function togglePlay() {
    const all = Object.values(wsRefs.current);
    if (playing) {
      all.forEach((ws) => ws.pause());
    } else {
      all.forEach((ws) => ws.play());
    }
    setPlaying(!playing);
  }

  function setVolume(name: string, value: number) {
    wsRefs.current[name]?.setVolume(value);
  }

  return (
    <div className="space-y-3">
      {stems.map((stem) => (
        <div key={stem.name} className="flex items-center gap-3">
          <span className="w-24 text-sm text-white/70 shrink-0">{stem.label}</span>
          <div ref={(el) => { containerRefs.current[stem.name] = el; }} className="flex-1" />
          <input
            type="range"
            min={0}
            max={1}
            step={0.05}
            defaultValue={1}
            onChange={(e) => setVolume(stem.name, parseFloat(e.target.value))}
            className="w-20"
          />
        </div>
      ))}

      <button
        onClick={togglePlay}
        disabled={!ready}
        className="rounded-md bg-white/10 hover:bg-white/20 px-4 py-1.5 text-sm disabled:opacity-40"
      >
        {playing ? "일시정지" : "재생"}
      </button>
    </div>
  );
}
