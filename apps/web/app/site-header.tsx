"use client";

import { useAuth } from "@/lib/auth-context";

export default function SiteHeader() {
  const { user, loading, logout } = useAuth();

  return (
    <header className="border-b border-white/10 px-6 py-4 flex items-center justify-between">
      <a href="/" className="font-semibold tracking-tight text-lg">
        Studio
      </a>
      <nav className="text-sm text-white/60 flex items-center gap-4">
        <a href="/library" className="hover:text-white">
          내 작업
        </a>
        <a href="/dmca" className="hover:text-white">
          DMCA
        </a>
        {!loading &&
          (user ? (
            <>
              {user.is_admin && (
                <a href="/admin" className="hover:text-white">
                  관리자
                </a>
              )}
              <span className="text-white/40 truncate max-w-[10rem]">{user.email}</span>
              <button onClick={logout} className="hover:text-white">
                로그아웃
              </button>
            </>
          ) : (
            <>
              <a href="/login" className="hover:text-white">
                로그인
              </a>
              <a href="/signup" className="hover:text-white">
                회원가입
              </a>
            </>
          ))}
      </nav>
    </header>
  );
}
