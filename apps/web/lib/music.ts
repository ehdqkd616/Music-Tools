const PITCHES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"];

export function shiftKeyLabel(tonic: string, mode: string, semitones: number): string {
  const idx = PITCHES.indexOf(tonic);
  if (idx === -1) return `${tonic} ${capitalize(mode)}`;
  const shifted = PITCHES[(((idx + semitones) % 12) + 12) % 12];
  return `${shifted} ${capitalize(mode)}`;
}

function capitalize(s: string): string {
  return s.charAt(0).toUpperCase() + s.slice(1);
}
