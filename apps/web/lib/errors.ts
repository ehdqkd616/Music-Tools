// §7.2 error codes → user-facing Korean text. Falls back to the raw
// (often English, yt-dlp-sourced) message for codes not listed here.
const ERROR_MESSAGES: Record<string, string> = {
  DRM_PROTECTED: "이 영상은 DRM으로 보호되어 있어 다운로드할 수 없습니다.",
  VIDEO_UNAVAILABLE: "더 이상 볼 수 없는 영상입니다 (비공개 처리되었거나 삭제됨).",
  AGE_RESTRICTED: "연령 제한이 걸린 영상이라 처리할 수 없습니다.",
  GEO_BLOCKED: "현재 지역에서는 볼 수 없는 영상입니다.",
  LIVE_STREAM_UNSUPPORTED: "라이브 스트림은 처리할 수 없습니다.",
  VIDEO_TOO_LONG: "영상이 너무 깁니다.",
  INVALID_URL: "유효한 유튜브 URL이 아닙니다.",
  RATE_LIMITED: "일일 사용 한도를 초과했습니다. 잠시 후 다시 시도해주세요.",
  DOWNLOAD_TEMPORARILY_DISABLED: "유튜브 다운로드 기능이 일시적으로 비활성화되었습니다.",
  EXTRACTION_FAILED: "추출에 실패했습니다. 다른 영상으로 시도하거나 잠시 후 다시 시도해주세요.",
  GPU_OOM: "처리 중 메모리 부족이 발생했습니다. 잠시 후 다시 시도해주세요.",
};

export function translateError(code: string | undefined | null, fallback?: string | null): string {
  if (code && ERROR_MESSAGES[code]) return ERROR_MESSAGES[code];
  return fallback ?? "작업이 실패했습니다.";
}
