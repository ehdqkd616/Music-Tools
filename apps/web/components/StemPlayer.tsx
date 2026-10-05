"use client";

import { useEffect, useRef, useState } from "react";

export interface Stem {
  name: string;
  label: string;
  url: string;
  mediaId: string;
}

interface Props {
  stems: Stem[];
  // 스템 이름 -> 선형 볼륨(0~1). 부모가 들고 있어야 내보내기 믹스에도 같은 값이 들어간다.
  volumes: Record<string, number>;
  onVolumeChange: (name: string, value: number) => void;
  onDownload: (stem: Stem) => void;
  downloadingName?: string | null;
}

// Each stem gets its own WaveSurfer instance, all playing through ONE shared
// AudioContext (passed in via `media: new WebAudioPlayer(ctx)`). Sync still
// follows the master track's `audioprocess` event and snaps any stem that has
// drifted more than 50ms (§10.2's intent, adapted to the actual API).
//
// iOS Safari에서 소리가 안 나던 원인 세 가지를 여기서 막는다:
//  1. AudioContext가 사용자 터치 밖에서 만들어지면 "suspended"로 멈춰 있고,
//     wavesurfer는 resume()을 안 부른다 → 재생 버튼 핸들러 안에서 직접 resume().
//  2. Web Audio는 무음(벨소리) 스위치를 켜면 같이 음소거된다 → audioSession을
//     "playback"으로 바꿔 음악 앱처럼 무음 스위치를 무시하게 한다 (iOS 17+).
//  3. wavesurfer의 WebAudioPlayer는 destroy 때 AudioContext를 닫지 않아서, 미리듣기
//     때마다 컨텍스트가 쌓이다 iOS 개수 제한에 걸린다 → 하나만 만들어 공유하고
//     언마운트 때 닫는다.
export default function StemPlayer({ stems, volumes, onVolumeChange, onDownload, downloadingName }: Props) {
  const containerRefs = useRef<Record<string, HTMLDivElement | null>>({});
  const wsRefs = useRef<Record<string, any>>({});
  // 미리듣기로 스템이 바뀌어 WaveSurfer를 새로 만들 때도 현재 볼륨을 이어받도록 ref로 읽는다.
  const volumesRef = useRef(volumes);
  volumesRef.current = volumes;
  const [playing, setPlaying] = useState(false);
  const [ready, setReady] = useState(false);
  const audioCtxRef = useRef<AudioContext | null>(null);

  function getAudioContext(): AudioContext {
    if (!audioCtxRef.current || audioCtxRef.current.state === "closed") {
      audioCtxRef.current = new AudioContext();
    }
    return audioCtxRef.current;
  }

  useEffect(() => {
    return () => {
      void audioCtxRef.current?.close();
      audioCtxRef.current = null;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    setReady(false);
    setPlaying(false);

    (async () => {
      const [{ default: WaveSurfer }, { default: WebAudioPlayer }] = await Promise.all([
        import("wavesurfer.js"),
        import("wavesurfer.js/dist/webaudio.js"),
      ]);
      if (cancelled) return;
      const audioContext = getAudioContext();

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
          // HTMLMediaElement를 흉내 내는 플레이어라 타입만 맞춰준다.
          media: new WebAudioPlayer(audioContext) as unknown as HTMLMediaElement,
        });
        ws.setVolume(volumesRef.current[stem.name] ?? 1);
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
      Object.values(wsRefs.current).forEach((ws) => {
        ws.pause(); // 공유 컨텍스트라 멈추지 않으면 미리듣기 전 스템이 계속 울린다
        ws.destroy();
      });
      wsRefs.current = {};
    };
  }, [stems]);

  // 반드시 터치/클릭 핸들러 안에서 동기적으로 불러야 iOS가 오디오를 허용한다.
  function unlockAudio() {
    const nav = navigator as Navigator & { audioSession?: { type: string } };
    if (nav.audioSession) nav.audioSession.type = "playback";
    const ctx = audioCtxRef.current;
    if (ctx && ctx.state !== "running") void ctx.resume();
  }

  function togglePlay() {
    if (!playing) unlockAudio();
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
    onVolumeChange(name, value);
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
            value={volumes[stem.name] ?? 1}
            onChange={(e) => setVolume(stem.name, parseFloat(e.target.value))}
            className="w-20"
          />
          <button
            onClick={() => onDownload(stem)}
            disabled={downloadingName === stem.name}
            title={`${stem.label} 다운로드`}
            className="rounded-md border border-white/10 hover:border-white/30 px-2 py-1 text-xs disabled:opacity-40"
          >
            {downloadingName === stem.name ? "…" : "⬇"}
          </button>
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
