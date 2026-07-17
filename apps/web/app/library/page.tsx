"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, triggerDownload } from "@/lib/api-client";
import type { LibraryItem } from "@/lib/types";

function formatDuration(sec: number | null): string {
  if (sec == null) return "";
  const m = Math.floor(sec / 60);
  const s = Math.floor(sec % 60);
  return `${m}:${String(s).padStart(2, "0")}`;
}

export default function LibraryPage() {
  const router = useRouter();
  const [items, setItems] = useState<LibraryItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [downloadingId, setDownloadingId] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  useEffect(() => {
    api
      .library()
      .then(setItems)
      .catch(() => setError("작업 기록을 불러오지 못했습니다."));
  }, []);

  async function handleDownload(id: string) {
    setDownloadingId(id);
    try {
      await triggerDownload(id);
    } finally {
      setDownloadingId(null);
    }
  }

  async function handleDelete(item: LibraryItem) {
    const ok = window.confirm(
      `"${item.title || item.media_id}"를 삭제할까요? 분리·키변경 결과물도 함께 지워지고 되돌릴 수 없습니다.`
    );
    if (!ok) return;

    setDeletingId(item.media_id);
    try {
      await api.deleteMedia(item.media_id);
      setItems((prev) => prev?.filter((i) => i.media_id !== item.media_id) ?? prev);
    } catch {
      setError("삭제에 실패했습니다.");
    } finally {
      setDeletingId(null);
    }
  }

  return (
    <div className="space-y-4">
      <h1 className="text-lg font-semibold">내 작업</h1>
      <p className="text-sm text-white/50">
        가져온 적 있는 곡은 여기서 바로 다운로드하거나 이어서 편집할 수 있어요. 이미 분리해둔 곡은
        &quot;이어하기&quot;를 눌러도 다시 분리하지 않고 캐시된 결과를 바로 씁니다.
      </p>

      {error && <p className="text-sm text-red-400">{error}</p>}
      {items === null && !error && <p className="text-sm text-white/50">불러오는 중…</p>}
      {items?.length === 0 && <p className="text-sm text-white/50">아직 처리한 곡이 없어요.</p>}

      <div className="space-y-2">
        {items?.map((item) => (
          <div
            key={item.media_id}
            className="flex items-center gap-3 rounded-lg border border-white/10 bg-panel p-3"
          >
            {item.thumbnail ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={item.thumbnail} alt="" className="w-20 h-12 object-cover rounded-md shrink-0" />
            ) : (
              <div className="w-20 h-12 rounded-md bg-white/5 shrink-0 flex items-center justify-center text-white/30 text-xs">
                {item.source_type === "upload" ? "파일" : "YT"}
              </div>
            )}

            <div className="flex-1 min-w-0">
              <p className="font-medium truncate">{item.title || item.media_id}</p>
              <p className="text-xs text-white/50">
                {item.artist && <span>{item.artist} · </span>}
                {formatDuration(item.duration_sec)}
                {item.has_stems && <span className="text-accent"> · 분리됨</span>}
              </p>
            </div>

            <button
              onClick={() => handleDownload(item.media_id)}
              disabled={downloadingId === item.media_id}
              className="rounded-md border border-white/10 hover:border-white/30 px-3 py-1.5 text-xs disabled:opacity-40"
            >
              {downloadingId === item.media_id ? "…" : "⬇ 다운로드"}
            </button>
            <button
              onClick={() => router.push(`/studio/${item.media_id}`)}
              className="rounded-md bg-accent text-ink font-medium px-3 py-1.5 text-xs"
            >
              🎤 이어하기
            </button>
            <button
              onClick={() => handleDelete(item)}
              disabled={deletingId === item.media_id}
              title="삭제"
              className="rounded-md border border-white/10 hover:border-red-400 hover:text-red-400 px-2 py-1.5 text-xs disabled:opacity-40"
            >
              {deletingId === item.media_id ? "…" : "🗑"}
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
