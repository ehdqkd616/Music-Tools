import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Studio — 오디오 워크스테이션",
  description: "유튜브 추출 + 보컬/MR 분리 + 키/템포 조절",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko">
      <body className="min-h-screen">
        <header className="border-b border-white/10 px-6 py-4 flex items-center justify-between">
          <a href="/" className="font-semibold tracking-tight text-lg">
            Studio
          </a>
          <nav className="text-sm text-white/60 flex gap-4">
            <a href="/library" className="hover:text-white">
              내 작업
            </a>
            <a href="/dmca" className="hover:text-white">
              DMCA
            </a>
          </nav>
        </header>
        <main className="max-w-3xl mx-auto px-6 py-10">{children}</main>
        <footer className="max-w-3xl mx-auto px-6 pb-10 text-xs text-white/30">
          키/템포 변경에 Rubber Band Library(GPL v2)를 서버 사이드에서 사용합니다. 오픈소스 라이선스
          고지 전체는 저장소의 THIRD_PARTY_LICENSES.md를 참고하세요.
        </footer>
      </body>
    </html>
  );
}
