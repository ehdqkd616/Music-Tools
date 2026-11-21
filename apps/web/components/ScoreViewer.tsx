"use client";

import { useEffect, useRef, useState } from "react";

// MusicXML을 브라우저에서 바로 악보로 그린다 (OpenSheetMusicDisplay, BSD-3).
// PDF는 서버(Verovio)에서 따로 만들기 때문에 줄바꿈 위치는 서로 다를 수 있다.
export default function ScoreViewer({ url }: { url: string }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [status, setStatus] = useState<"loading" | "ready" | "error">("loading");

  useEffect(() => {
    let cancelled = false;
    setStatus("loading");

    (async () => {
      try {
        const [{ OpenSheetMusicDisplay }, xml] = await Promise.all([
          import("opensheetmusicdisplay"),
          fetch(url).then((res) => {
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            return res.text();
          }),
        ]);
        const container = containerRef.current;
        if (cancelled || !container) return;

        container.innerHTML = "";
        const osmd = new OpenSheetMusicDisplay(container, {
          autoResize: true,
          backend: "svg",
          drawTitle: true,
          drawComposer: false,
          drawPartNames: false,
        });
        await osmd.load(xml);
        if (cancelled) return;
        osmd.zoom = container.clientWidth < 640 ? 0.55 : 0.9;
        osmd.render();
        setStatus("ready");
      } catch {
        if (!cancelled) setStatus("error");
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [url]);

  return (
    <div className="space-y-2">
      {status === "loading" && <p className="text-sm text-white/50">악보를 그리는 중…</p>}
      {status === "error" && (
        <p className="text-sm text-red-400">악보를 화면에 그리지 못했어요. PDF나 MusicXML을 받아서 확인해주세요.</p>
      )}
      <div ref={containerRef} className="rounded-lg bg-white text-black overflow-x-auto" />
    </div>
  );
}
