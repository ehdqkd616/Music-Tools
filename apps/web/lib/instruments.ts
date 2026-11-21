// services/common/transcription.py의 INSTRUMENTS와 같은 값이어야 한다.
export type Instrument = "piano" | "guitar" | "bass" | "vocals" | "strings" | "winds" | "other";

export const INSTRUMENTS: { value: Instrument; label: string; detail: string; duration: string }[] = [
  { value: "piano", label: "🎹 피아노", detail: "두 단 악보 · 전용 모델", duration: "곡 길이와 비슷한 시간이 걸려요." },
  { value: "guitar", label: "🎸 기타", detail: "화음까지", duration: "보통 1분 안에 끝나요." },
  { value: "bass", label: "🎵 베이스", detail: "한 음씩", duration: "보통 1분 안에 끝나요." },
  { value: "vocals", label: "🎤 노래", detail: "멜로디 한 줄", duration: "보통 1분 안에 끝나요." },
  { value: "strings", label: "🎻 현악기", detail: "바이올린 · 첼로 등", duration: "보통 1분 안에 끝나요." },
  { value: "winds", label: "🎷 관악기", detail: "플루트 · 색소폰 등", duration: "보통 1분 안에 끝나요." },
  { value: "other", label: "🎼 그 밖의 악기", detail: "음 높이가 있는 악기", duration: "보통 1분 안에 끝나요." },
];

export function isInstrument(value: string | null): value is Instrument {
  return INSTRUMENTS.some((i) => i.value === value);
}
