import type { Metadata } from "next";
import "./globals.css";
import { AuthProvider } from "@/lib/auth-context";
import SiteHeader from "./site-header";

export const metadata: Metadata = {
  title: "Studio — 오디오 워크스테이션",
  description: "유튜브 추출 + 보컬/MR 분리 + 키/템포 조절",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko">
      <body className="min-h-screen">
        <AuthProvider>
          <SiteHeader />
          <main className="max-w-3xl mx-auto px-6 py-10">{children}</main>
          <footer className="max-w-3xl mx-auto px-6 pb-10 text-xs text-white/30">
            키/템포 변경에 Rubber Band Library(GPL v2)를 서버 사이드에서 사용합니다. 오픈소스 라이선스
            고지 전체는 저장소의 THIRD_PARTY_LICENSES.md를 참고하세요.
          </footer>
        </AuthProvider>
      </body>
    </html>
  );
}
