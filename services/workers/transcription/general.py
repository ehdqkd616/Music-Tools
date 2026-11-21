"""Pitched-instrument transcription (anything but piano and drums) with Spotify's
Basic Pitch (Apache-2.0), run through its bundled ONNX model on CPU.

Basic Pitch is instrument-agnostic; the presets narrow the pitch range to the
instrument and, for single-line instruments, keep one note at a time — that
removes most octave/harmonic ghost notes.
"""

from dataclasses import dataclass

MIN_NOTE_MS = 80.0


@dataclass(frozen=True)
class Preset:
    min_hz: float | None
    max_hz: float | None
    monophonic: bool
    midi_program: int  # General MIDI program for the output .mid
    onset_threshold: float = 0.6
    frame_threshold: float = 0.4
    min_note_ms: float = 80.0


# Thresholds were picked with a sweep on synthesized test pieces (note F1 with a
# 50ms onset tolerance): flute .91, violin .91, voice .94, bass .77, guitar
# chords .84; overlapping string ensembles stay weak (~.4).
PRESETS: dict[str, Preset] = {
    "guitar": Preset(75, 1400, False, 25, 0.6, 0.4, 120),  # acoustic guitar (steel)
    "bass": Preset(30, 330, True, 33, 0.7, 0.3, 80),  # electric bass (finger), up to E4
    "vocals": Preset(75, 1100, True, 53, 0.6, 0.2, 120),  # voice oohs
    "strings": Preset(60, 3500, False, 40, 0.7, 0.4, 80),  # violin
    "winds": Preset(100, 2500, True, 73, 0.6, 0.4, 80),  # flute
    "other": Preset(None, None, False, 0),
}

_MODEL = None


def _model():
    global _MODEL
    if _MODEL is None:
        from basic_pitch import ICASSP_2022_MODEL_PATH
        from basic_pitch.inference import Model

        _MODEL = Model(ICASSP_2022_MODEL_PATH)
    return _MODEL


def _keep_one_line(notes: list[dict]) -> list[dict]:
    """Single-line instruments: among notes starting together keep the loudest,
    and end each note where the next one starts."""
    notes = sorted(notes, key=lambda n: (n["onset_time"], -n["velocity"]))
    line: list[dict] = []
    for note in notes:
        if line and note["onset_time"] - line[-1]["onset_time"] < 0.05:
            continue  # quieter duplicate (usually an octave or harmonic)
        if line and line[-1]["offset_time"] > note["onset_time"]:
            line[-1]["offset_time"] = note["onset_time"]
        line.append(dict(note))
    return [n for n in line if (n["offset_time"] - n["onset_time"]) * 1000 >= MIN_NOTE_MS / 2]


def transcribe(audio_path: str, instrument: str, midi_path: str) -> list[dict]:
    """Writes a MIDI file and returns note events
    ({onset_time, offset_time, midi_note, velocity}, times in seconds)."""
    import pretty_midi
    from basic_pitch.inference import predict

    preset = PRESETS[instrument]
    _, _, raw_events = predict(
        audio_path,
        _model(),
        onset_threshold=preset.onset_threshold,
        frame_threshold=preset.frame_threshold,
        minimum_note_length=preset.min_note_ms,
        minimum_frequency=preset.min_hz,
        maximum_frequency=preset.max_hz,
        multiple_pitch_bends=False,
        melodia_trick=True,
    )
    notes = [
        {
            "onset_time": float(start),
            "offset_time": float(end),
            "midi_note": int(pitch),
            "velocity": max(1, min(127, int(round(float(amplitude) * 127)))),
        }
        for start, end, pitch, amplitude, _ in raw_events
    ]
    if preset.monophonic:
        notes = _keep_one_line(notes)
    notes.sort(key=lambda n: n["onset_time"])

    midi = pretty_midi.PrettyMIDI()
    track = pretty_midi.Instrument(program=preset.midi_program)
    for n in notes:
        track.notes.append(pretty_midi.Note(n["velocity"], n["midi_note"], n["onset_time"], n["offset_time"]))
    midi.instruments.append(track)
    midi.write(midi_path)
    return notes
